"""File system watcher using watchdog."""

import logging
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from watchdog.observers import Observer
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileModifiedEvent,
    FileDeletedEvent,
)

from gemvis.config import WATCH_DIRS, ALL_EXTENSIONS, SUPPORTED_EXTENSIONS, ensure_dirs, is_ignored_path
from gemvis.insight import generate_insight, GemInsight
from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.event_log import EventLog
from gemvis.schedule import WorkSchedule

IMAGE_EXTENSIONS = SUPPORTED_EXTENSIONS["image"]

logger = logging.getLogger(__name__)


class GemvisHandler(FileSystemEventHandler):
    # Debounce window before regenerating a daily summary after a batch of
    # files for the same (date, period) finish analyzing. Coalesces dozens
    # of historical files into a single LLM call. Tunable via env var so
    # CPU-only users (analysis ~60s/file) can stretch it; GPU users can
    # shrink it.
    SUMMARY_DEBOUNCE_SEC = float(os.environ.get("GEMVIS_SUMMARY_DEBOUNCE_SEC", "10"))

    def __init__(
        self,
        graph: KnowledgeGraph,
        on_file_processed: Callable[[GemInsight], None] | None = None,
        event_log: EventLog | None = None,
        schedule: WorkSchedule | None = None,
    ):
        super().__init__()
        self.graph = graph
        self.on_file_processed = on_file_processed
        self.event_log = event_log
        self.schedule = schedule
        self._processed: set[str] = set()
        self._lock = threading.Lock()
        # Pending summary regeneration timers keyed by (YYYY-MM-DD, period)
        # — used by the live watcher path (one-off drops).
        self._summary_timers: dict[tuple[str, str], threading.Timer] = {}
        # Deferred keys collected during a bulk scan. Flushed at scan end
        # so we don't trigger an LLM call per file during the scan itself.
        self._deferred_keys: set[tuple[str, str]] = set()
        self._summary_lock = threading.Lock()

    def _should_process(self, path: Path) -> bool:
        if is_ignored_path(path):
            return False
        return path.suffix.lower() in ALL_EXTENSIONS and path.is_file()

    def _matches_extension(self, path: Path) -> bool:
        if is_ignored_path(path):
            return False
        return path.suffix.lower() in ALL_EXTENSIONS

    def _log_event(self, action: str, path: Path):
        if not self.event_log:
            return
        now = datetime.now()
        period = self.schedule.period_for(now) if self.schedule else None
        try:
            self.event_log.record(action, str(path.resolve()), timestamp=now, period=period)
        except Exception as e:
            logger.error("Failed to record event: %s", e)

    def on_created(self, event: FileCreatedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._should_process(path):
            self._log_event("created", path)
            self._process_file(path)

    def on_modified(self, event: FileModifiedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        if self._should_process(path):
            self._log_event("modified", path)
            # v2 Stage 3: 파일 변경 감지 시 analysis_status를 pending으로 되돌리고 재분석
            resolved = str(path.resolve())
            self.graph.update_status(resolved, "pending")
            with self._lock:
                self._processed.discard(resolved)
            self._process_file(path)

    def on_deleted(self, event: FileDeletedEvent):
        if event.is_directory:
            return
        path = Path(event.src_path)
        # Note: path.is_file() is False because file is gone — check extension only
        if not self._matches_extension(path):
            return
        self._log_event("deleted", path)

        node_id = f"file:{path.resolve()}"
        if self.graph.has_node(node_id):
            self.graph.remove_node(node_id)
            logger.info("Removed from graph: %s", path.name)

        # Also forget it from the "already processed" cache so a re-created file gets re-analyzed
        with self._lock:
            self._processed.discard(str(path.resolve()))

    def _process_file(self, path: Path):
        """v2 2-stage hydration:

        Stage 1 (Fast): upsert skeleton file node with physical metadata and
                        analysis_status="pending" — makes the file visible in
                        the UI immediately.
        Stage 2 (Slow): run Gemma 4, flip status processing → completed/failed.
        """
        resolved = path.resolve()
        key = str(resolved)
        with self._lock:
            if key in self._processed:
                return
            self._processed.add(key)

        # Stage 1: Skeleton with physical metadata
        try:
            stat = resolved.stat()
            self.graph.upsert_skeleton(
                key,
                size_bytes=stat.st_size,
                file_mtime=stat.st_mtime,
                file_ctime=stat.st_ctime,
            )
        except Exception as e:
            logger.warning("Skeleton stage failed for %s: %s", path.name, e)

        # Stage 2: LLM analysis (skip images when analyze_images is off)
        from gemvis.preferences import prefs
        if path.suffix.lower() in IMAGE_EXTENSIONS and not prefs.analyze_images:
            logger.info("Skipping image analysis (disabled): %s", path.name)
            result = GemInsight(file_path=key, analysis_status="pending")
            if self.on_file_processed:
                self.on_file_processed(result)
            return

        self.graph.update_status(key, "processing")
        logger.info("Analyzing file: %s", path)
        try:
            result = generate_insight(path)
        except Exception as e:
            logger.error("Analysis raised for %s: %s", path.name, e)
            self.graph.update_status(key, "failed", error=str(e))
            result = GemInsight(file_path=key, error=str(e), analysis_status="failed")
            if self.on_file_processed:
                self.on_file_processed(result)
            return

        if result.error:
            self.graph.update_status(key, "failed", error=result.error)
            logger.error("Analysis failed: %s", result.error)
        else:
            # add_insight writes raw_insight + refreshes all attributes
            self.graph.add_insight(result)
            logger.info("Added to graph: %s (%s)", path.name, result.category)
            # Auto-regenerate the daily summary for the file's *original*
            # creation date (not "now"). Lets historical files imported from
            # an existing folder show up on the right day in the Calendar.
            self._trigger_daily_summary_for(result)

        if self.on_file_processed:
            self.on_file_processed(result)

    # ── Auto daily-summary regeneration (file_ctime → Calendar) ──

    def _trigger_daily_summary_for(self, insight: GemInsight, defer: bool = False):
        """Record the file's original creation time as an event and either
        schedule (debounced) or defer the daily-summary regeneration for
        that date+period.

        Why ctime, not now: the user's schedule (work/personal hours) is meant
        to classify when the file was *actually* created on disk, so the
        Calendar reflects the user's life, not Gemvis discovery time.

        defer=True: only record the event + remember the key. Used during
            bulk scans so we don't kick off an LLM call per file mid-scan.
            Call ``flush_deferred_summaries()`` at the end of the scan.
        defer=False: also start a debounce timer for that key (live drop
            of one or two files via on_created).
        """
        if self.event_log is None or self.schedule is None or insight.file_ctime is None:
            return
        try:
            ctime_dt = datetime.fromtimestamp(insight.file_ctime)
            period = self.schedule.period_for(ctime_dt)  # 'work' | 'personal'
            # Distinct action name so it doesn't collide with watcher's
            # "created" event (which marks Gemvis discovery time).
            self.event_log.record(
                "original_created",
                insight.file_path,
                timestamp=ctime_dt,
                period=period,
            )
        except Exception as e:
            logger.warning("Failed to record original_created event for %s: %s", insight.file_path, e)
            return

        date_str = ctime_dt.date().isoformat()
        # Regenerate the work/personal slot for that day AND the all-day
        # 'daily' one-sentence summary that the calendar cells render.
        keys = [(date_str, period), (date_str, "daily")]

        if defer:
            # Bulk scan path: just remember the keys. Flushed at scan end.
            with self._summary_lock:
                for k in keys:
                    self._deferred_keys.add(k)
            return

        # Live path: debounce the regeneration so a small batch of files
        # arriving back-to-back coalesces into one LLM call.
        with self._summary_lock:
            for k in keys:
                existing = self._summary_timers.get(k)
                if existing is not None:
                    existing.cancel()
                timer = threading.Timer(
                    self.SUMMARY_DEBOUNCE_SEC,
                    self._regenerate_summary,
                    args=(ctime_dt, k[1]),
                )
                timer.daemon = True
                self._summary_timers[k] = timer
                timer.start()

    def flush_deferred_summaries(self):
        """Generate summaries for every (date, period) key collected during
        a bulk scan. Called once at scan completion.

        Each key triggers exactly one ``generate_summary`` call — the LLM
        sees the full EventLog so newly recorded ``original_created`` events
        for that day are all included.
        """
        with self._summary_lock:
            keys = list(self._deferred_keys)
            self._deferred_keys.clear()
        if not keys:
            return
        logger.info("Flushing %d deferred daily-summary key(s) post-scan", len(keys))
        for date_str, period in keys:
            try:
                date_dt = datetime.fromisoformat(date_str)
            except Exception:
                continue
            self._regenerate_summary(date_dt, period)

    def _regenerate_summary(self, date: datetime, period: str):
        """Generate (or overwrite) the daily summary for date+period using
        the user's currently selected language.

        Today's data is intentionally skipped: the day is still in progress,
        so a mid-day auto summary would only describe a half-finished period
        and confuses users who never asked for it. SummaryScheduler picks
        today up after work hours / midnight; the user can also press the
        "생성/재생성" button explicitly.
        """
        if date.date() == datetime.now().date():
            logger.info(
                "Skip auto summary for today (%s/%s) — wait for scheduler or manual trigger",
                date.date(),
                period,
            )
            with self._summary_lock:
                self._summary_timers.pop((date.date().isoformat(), period), None)
            return
        key = (date.date().isoformat(), period)
        try:
            # Imported lazily to avoid a circular dependency at module load.
            from gemvis.summary import generate_summary
            from gemvis.preferences import prefs
            result = generate_summary(
                date,
                period,  # type: ignore[arg-type]
                graph=self.graph,
                event_log=self.event_log,
                schedule=self.schedule,
                skip_if_empty=True,
                lang=prefs.analyze_lang,
            )
            if result:
                logger.info("Auto-generated daily summary: %s %s", key[0], period)
        except Exception as e:
            logger.warning("Auto daily-summary generation failed for %s: %s", key, e)
        finally:
            with self._summary_lock:
                self._summary_timers.pop(key, None)

    def cancel_pending_summaries(self):
        """Cancel all pending debounced summary timers (called on watcher stop)."""
        with self._summary_lock:
            for timer in self._summary_timers.values():
                timer.cancel()
            self._summary_timers.clear()


class ScanProgress:
    """Tracks the progress of a background scan."""

    def __init__(self):
        self.status: str = "idle"  # idle | scanning | paused | done | error
        self.total: int = 0
        self.processed: int = 0
        self.current_file: str = ""
        self.error: str = ""
        # Mode of the most recent scan ('all'|'documents'|'images'|'skeleton'|'').
        # Lets the UI render a contextual label in the monitor panel.
        self.mode: str = ""
        # Wall-clock start of the most recent scan (ISO string, "" = never started).
        self.started_at_iso: str = ""
        # Mode of the most recent scan that found nothing to do
        # (everything already analyzed / no new files). The UI reads this once
        # to surface "추가 분석할 항목 없음", then clears it via clear_no_op().
        self.last_no_op_mode: str = ""
        self._started_at: float = 0.0
        self._elapsed_before_pause: float = 0.0
        self._pause_event = threading.Event()
        self._pause_event.set()
        self._lock = threading.Lock()

    def start(self, total: int, mode: str = ""):
        with self._lock:
            self.status = "scanning"
            self.total = total
            self.processed = 0
            self.current_file = ""
            self.error = ""
            self.mode = mode
            self.started_at_iso = datetime.now().isoformat(timespec="seconds")
            self._started_at = time.monotonic()
            self._elapsed_before_pause = 0.0
            self._pause_event.set()
            # Starting a real run clears any pending no-op flag.
            self.last_no_op_mode = ""

    def mark_no_op(self, mode: str):
        """The most recent scan request had nothing to do (no new pending or
        failed files matched). UI surfaces this once."""
        with self._lock:
            self.last_no_op_mode = mode

    def clear_no_op(self):
        with self._lock:
            self.last_no_op_mode = ""

    def update(self, file_name: str):
        with self._lock:
            self.processed += 1
            self.current_file = file_name

    def finish(self):
        with self._lock:
            self.status = "done"
            self.current_file = ""

    def fail(self, error: str):
        with self._lock:
            self.status = "error"
            self.error = error

    def pause(self):
        with self._lock:
            if self.status == "scanning":
                self.status = "paused"
                self._elapsed_before_pause += time.monotonic() - self._started_at
                self._pause_event.clear()

    def resume(self):
        with self._lock:
            if self.status == "paused":
                self.status = "scanning"
                self._started_at = time.monotonic()
                self._pause_event.set()

    def wait_if_paused(self):
        self._pause_event.wait()

    def to_dict(self) -> dict:
        with self._lock:
            elapsed = self._elapsed_before_pause
            if self.status == "scanning" and self._started_at > 0:
                elapsed += time.monotonic() - self._started_at
            avg_sec = elapsed / self.processed if self.processed > 0 else 0.0
            remaining = self.total - self.processed
            eta_sec = avg_sec * remaining if avg_sec > 0 else 0.0
            return {
                "status": self.status,
                "total": self.total,
                "processed": self.processed,
                "current_file": self.current_file,
                "error": self.error,
                "elapsed_sec": round(elapsed, 1),
                "avg_sec_per_file": round(avg_sec, 1),
                "eta_sec": round(eta_sec, 1),
                "mode": self.mode,
                "started_at": self.started_at_iso,
                "last_no_op_mode": self.last_no_op_mode,
            }


class FileWatcher:
    def __init__(
        self,
        graph: KnowledgeGraph,
        watch_dirs: list[str | Path] | None = None,
        on_file_processed: Callable[[GemInsight], None] | None = None,
        event_log: EventLog | None = None,
        schedule: WorkSchedule | None = None,
        scan_progress: ScanProgress | None = None,
    ):
        if watch_dirs is None:
            self.watch_dirs: list[Path] = list(WATCH_DIRS)
        else:
            self.watch_dirs = [Path(d) for d in watch_dirs]
        self.graph = graph
        self.on_file_processed = on_file_processed
        self.event_log = event_log
        self.schedule = schedule
        self.observer: Observer | None = None
        self._results: list[GemInsight] = []
        # Reuse an injected ScanProgress so the UI doesn't lose progress
        # across watcher restarts (e.g. after /api/config reconfiguration).
        self.scan_progress = scan_progress if scan_progress is not None else ScanProgress()
        # Handler is created upfront (not only on start) so background scans
        # — which may run before observer.start() — can reuse the same
        # debounce queue for the auto daily-summary regeneration.
        self._handler = GemvisHandler(
            self.graph,
            on_file_processed=self._callback,
            event_log=self.event_log,
            schedule=self.schedule,
        )

    def _callback(self, result: GemInsight):
        self._results.append(result)
        if self.on_file_processed:
            self.on_file_processed(result)

    def start(self):
        """Start watching all configured directories."""
        ensure_dirs()
        self.observer = Observer()
        scheduled_count = 0
        for d in self.watch_dirs:
            if d.exists() and d.is_dir():
                self.observer.schedule(self._handler, str(d), recursive=True)
                logger.info("Watching directory: %s", d)
                scheduled_count += 1
            else:
                logger.warning("Skipping non-existent directory: %s", d)
        self.observer.start()
        if scheduled_count == 0:
            logger.warning("No valid watch directories configured")

    def stop(self):
        """Stop watching."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Stopped watching")
        if getattr(self, "_handler", None) is not None:
            self._handler.cancel_pending_summaries()

    def is_running(self) -> bool:
        return self.observer is not None and self.observer.is_alive()

    def get_results(self) -> list[GemInsight]:
        return list(self._results)

    # Scan modes — what work the user wants done.
    # • skeleton:  Stage 1 only (disk → graph file nodes), no LLM
    # • documents: Stage 1 + LLM extract for non-image files only
    # • images:    Stage 1 + LLM extract (Vision) for image files only
    # • all:       Stage 1 + LLM extract for everything
    SCAN_MODES = ("skeleton", "documents", "images", "all")
    BATCH_SAVE_EVERY = 10

    def scan_existing(self, mode: str = "all"):
        """Scan existing files in all watch directories (blocking)."""
        self._run_scan(mode=mode)

    def scan_existing_async(self, mode: str = "all"):
        """Scan existing files in a background thread (non-blocking)."""
        if self.scan_progress.status == "scanning":
            return
        thread = threading.Thread(
            target=self._run_scan, kwargs={"mode": mode}, name=f"scan-{mode}", daemon=True
        )
        thread.start()

    def scan_images_only_async(self):
        """Backwards-compat alias for the new mode-aware scan."""
        self.scan_existing_async(mode="images")

    def _run_scan(self, mode: str = "all", *, images_only: bool | None = None):
        """Internal scan implementation with progress tracking.

        v2: every target goes through the same 2-stage hydration — Stage 1
        skeleton first (so the file appears in the UI immediately), then
        Stage 2 LLM analysis with status transitions.

        ``mode`` controls Stage 2 scope:
          - skeleton:  no LLM at all
          - documents: skip images
          - images:    only images
          - all:       everything

        ``images_only`` is a legacy keyword preserved so older callers
        (and tests) don't break; it maps to mode="images".
        """
        if images_only is True:
            mode = "images"
        if mode not in self.SCAN_MODES:
            logger.warning("Unknown scan mode %r — defaulting to 'all'", mode)
            mode = "all"

        from gemvis.preferences import prefs

        ensure_dirs()
        targets: list[Path] = []
        # Honor the user preference toggle when running a generic scan, but
        # let an explicit images-mode override it (the user just clicked
        # "extract images" and expects images to be analyzed).
        skip_image_analysis = (
            mode == "documents"
            or (mode == "all" and not prefs.analyze_images)
        )

        for watch_dir in self.watch_dirs:
            if not (watch_dir.exists() and watch_dir.is_dir()):
                logger.warning("Skipping scan for non-existent directory: %s", watch_dir)
                continue
            for path in watch_dir.rglob("*"):
                if is_ignored_path(path):
                    continue
                if not (path.is_file() and path.suffix.lower() in ALL_EXTENSIONS):
                    continue
                is_image = path.suffix.lower() in IMAGE_EXTENSIONS
                if mode == "images" and not is_image:
                    continue
                if mode == "documents" and is_image:
                    continue
                node_id = f"file:{path}"
                # Skip files that are already fully analyzed; pick up
                # everything else (no node yet, or stuck in pending/processing/failed).
                # Without this, the live watcher's skeleton pass would mark every
                # file as "has_node" and the explicit "Extract …" command would
                # find nothing to do.
                if not self.graph.has_node(node_id):
                    targets.append(path)
                elif self.graph.get_status(node_id) != "completed":
                    targets.append(path)

        # Stage 1: bulk skeleton pass — makes every discovered file visible
        # as "pending" before any LLM calls.
        for path in targets:
            try:
                stat = path.stat()
                self.graph.upsert_skeleton(
                    str(path.resolve()),
                    size_bytes=stat.st_size,
                    file_mtime=stat.st_mtime,
                    file_ctime=stat.st_ctime,
                    save=False,
                )
            except Exception as e:
                logger.warning("Skeleton stage failed for %s: %s", path.name, e)
        if targets:
            self.graph.save()

        # Skeleton-only mode stops here.
        if mode == "skeleton":
            self.scan_progress.start(0, mode=mode)
            self.scan_progress.finish()
            if not targets:
                self.scan_progress.mark_no_op(mode)
            logger.info("Skeleton scan complete: %d files registered", len(targets))
            return

        # Separate images from non-images for conditional analysis
        analyze_targets = []
        skipped_images = 0
        for path in targets:
            is_image = path.suffix.lower() in IMAGE_EXTENSIONS
            if is_image and skip_image_analysis:
                skipped_images += 1
            else:
                analyze_targets.append(path)

        if skipped_images:
            logger.info("Skipping %d image files (image analysis disabled)", skipped_images)

        # Nothing to analyze — surface a "no-op" hint so the UI can toast
        # "추가 분석할 항목 없음" instead of falsely claiming a scan ran.
        if not analyze_targets:
            self.scan_progress.start(0, mode=mode)
            self.scan_progress.finish()
            self.scan_progress.mark_no_op(mode)
            logger.info("Scan no-op (%s): nothing new to analyze", mode)
            return

        self.scan_progress.start(len(analyze_targets), mode=mode)
        logger.info("Scan started (%s): %d files to analyze", mode, len(analyze_targets))

        errors = 0
        for path in analyze_targets:
            self.scan_progress.wait_if_paused()
            self.scan_progress.update(path.name)
            key = str(path.resolve())
            self.graph.update_status(key, "processing", save=False)
            try:
                logger.info("Scanning existing file: %s", path)
                result = generate_insight(path)
                if not result.error:
                    self.graph.add_insight(result, save=False)
                    if self.event_log:
                        # Discovery event: use mtime so the timestamp is
                        # anchored to the file, not the scan moment.
                        file_mtime = datetime.fromtimestamp(path.stat().st_mtime)
                        period = self.schedule.period_for(file_mtime) if self.schedule else None
                        self.event_log.record(
                            "created", key, timestamp=file_mtime, period=period
                        )
                    # defer=True: collect keys during scan, flush after loop
                    self._handler._trigger_daily_summary_for(result, defer=True)
                else:
                    self.graph.update_status(key, "failed", error=result.error, save=False)
                    errors += 1
                self._results.append(result)
            except Exception as e:
                errors += 1
                self.graph.update_status(key, "failed", error=str(e), save=False)
                logger.error("Failed to process %s: %s", path.name, e)
            if self.scan_progress.processed % self.BATCH_SAVE_EVERY == 0:
                self.graph.save()
        self.graph.save()
        self.scan_progress.finish()
        logger.info("Scan complete: %d files processed, %d errors", len(analyze_targets), errors)
        try:
            self._handler.flush_deferred_summaries()
        except Exception as e:
            logger.warning("flush_deferred_summaries failed: %s", e)
