"""Background scheduler for automatic daily summary generation.

Rules (per user requirements):
- Work summary: auto-generated at the end of each day's scheduled work hours.
- Personal summary: auto-generated at 00:00 for the previous day.

Strategy:
- One background thread wakes up every 60 seconds.
- Tracks the last time each trigger fired (in-memory + persisted as a marker
  file so restarts don't re-trigger).
- Runs summary generation in the same thread (short, non-blocking for HTTP).
"""

import json
import logging
import threading
from datetime import datetime, timedelta, time as dtime
from pathlib import Path

from gemvis.event_log import EventLog
from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.schedule import WorkSchedule, WEEKDAYS
from gemvis.summary import generate_summary

logger = logging.getLogger(__name__)

STATE_PATH = Path.home() / ".gemvis" / "scheduler_state.json"
POLL_INTERVAL = 60  # seconds


class SummaryScheduler:
    def __init__(
        self,
        graph: KnowledgeGraph,
        event_log: EventLog,
        schedule: WorkSchedule,
        state_path: str | Path | None = None,
    ):
        self.graph = graph
        self.event_log = event_log
        self.schedule = schedule
        self.state_path = Path(state_path) if state_path else STATE_PATH
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        # State: which (date, period) combos have already been auto-triggered
        self._triggered: set[str] = set()
        self._load_state()

    # ── persistence ───────────────────────────────────────────────

    def _load_state(self):
        if not self.state_path.exists():
            return
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._triggered = set(data.get("triggered", []))
        except Exception as e:
            logger.warning("Failed to load scheduler state: %s", e)

    def _save_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump({"triggered": sorted(self._triggered)}, f, indent=2)
        except Exception as e:
            logger.warning("Failed to save scheduler state: %s", e)

    # ── trigger logic ─────────────────────────────────────────────

    def _trigger_key(self, date: str, period: str) -> str:
        return f"{date}:{period}"

    def _should_trigger_work(self, now: datetime) -> bool:
        """True if today's work end time has passed and we haven't triggered yet."""
        window = self.schedule.work_window(now)
        if window is None:
            return False
        _, end_dt = window
        date_str = now.date().isoformat()
        if now < end_dt:
            return False
        if self._trigger_key(date_str, "work") in self._triggered:
            return False
        return True

    def _should_trigger_personal(self, now: datetime) -> bool:
        """True if it's past midnight and yesterday's personal summary isn't done."""
        # Trigger only if we've entered a new day
        yesterday = (now - timedelta(days=1)).date()
        yesterday_str = yesterday.isoformat()
        if self._trigger_key(yesterday_str, "personal") in self._triggered:
            return False
        # Only after 00:05 to give any lingering events time to land
        if now.time() < dtime(0, 5):
            return False
        return True

    def _run_generation(self, date: datetime, period: str):
        try:
            logger.info("Scheduler: generating %s summary for %s", period, date.date())
            generate_summary(
                date, period, self.graph, self.event_log, self.schedule,  # type: ignore[arg-type]
                skip_if_empty=True,
            )
            self._triggered.add(self._trigger_key(date.date().isoformat(), period))
            self._save_state()
        except Exception as e:
            logger.error("Scheduler: summary generation failed: %s", e)

    def _tick(self):
        now = datetime.now()

        if self._should_trigger_work(now):
            self._run_generation(now, "work")

        if self._should_trigger_personal(now):
            yesterday = datetime.combine(
                (now - timedelta(days=1)).date(), dtime(12, 0)
            )  # midday of yesterday as anchor
            self._run_generation(yesterday, "personal")

    # ── thread control ────────────────────────────────────────────

    def _loop(self):
        logger.info("SummaryScheduler: started (poll every %ds)", POLL_INTERVAL)
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                logger.exception("Scheduler tick failed: %s", e)
            self._stop.wait(POLL_INTERVAL)
        logger.info("SummaryScheduler: stopped")

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._loop, name="summary-scheduler", daemon=True
        )
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
