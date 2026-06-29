"""FastAPI backend for Gemvis."""

import os
import sys
import shutil
import subprocess
import threading
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
import json as _json_module
from pydantic import BaseModel

import gemvis.config as config
from gemvis.i18n import t, extract_lang
from gemvis.preferences import prefs, SUPPORTED_LANGS as PREF_SUPPORTED_LANGS


def get_lang(accept_language: str | None = Header(None)) -> str:
    """FastAPI dependency that resolves the request language from Accept-Language."""
    return extract_lang(accept_language)


from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.watcher import FileWatcher
from gemvis.search import SearchEngine
from gemvis.insight import GemInsight
from gemvis.insight_service import InsightService
from gemvis.event_log import EventLog
from gemvis.schedule import WorkSchedule
from gemvis.summary import (
    generate_summary,
    get_summary,
    delete_summary,
    list_summaries,
)
from gemvis.scheduler import SummaryScheduler
from gemvis.chat import ChatEngine
from gemvis import tasks as tasks_store
from gemvis.graph_analytics import GraphAnalytics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Global state
graph: KnowledgeGraph | None = None
watcher: FileWatcher | None = None
search_engine: SearchEngine | None = None
chat_engine: ChatEngine | None = None
analytics: GraphAnalytics | None = None
insight_service: InsightService | None = None
event_log: EventLog | None = None
work_schedule: WorkSchedule | None = None
scheduler: SummaryScheduler | None = None
recent_insights: list[GemInsight] = []


def _warmup_embedding_model(graph_ref: KnowledgeGraph):
    """Pre-load the sentence-transformer model so the first search is fast."""
    try:
        import time
        t0 = time.monotonic()
        graph_ref.embeddings._get_model()
        # Encode a dummy string to trigger any lazy initialization deeper in the model
        graph_ref.embeddings.encode("warmup")
        logger.info("Embedding model warm-up complete (%.2fs)", time.monotonic() - t0)
    except Exception as e:
        logger.warning("Embedding model warm-up failed: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph, watcher, search_engine, chat_engine, analytics, insight_service, event_log, work_schedule, scheduler
    config.ensure_dirs()
    graph = KnowledgeGraph()
    # v2 crash recovery: any file nodes stuck in "processing" from a prior
    # run (e.g. Gemma 4 crashed mid-analysis) are flipped back to "pending"
    # so the watcher picks them up on next scan.
    try:
        rolled = graph.rollback_processing_to_pending()
        if rolled:
            logger.info("Startup rollback: %d node(s) processing → pending", rolled)
    except Exception as e:
        logger.warning("Startup rollback failed: %s", e)
    event_log = EventLog()
    work_schedule = WorkSchedule()
    search_engine = SearchEngine(graph)
    chat_engine = ChatEngine(search_engine)
    analytics = GraphAnalytics(graph)
    insight_service = InsightService(graph, event_log, work_schedule)
    watcher = FileWatcher(
        graph,
        on_file_processed=lambda r: recent_insights.append(r),
        event_log=event_log,
        schedule=work_schedule,
    )
    # Auto-start the file watcher so users don't need to click a button
    try:
        watcher.start()
        logger.info("File watcher auto-started (watching: %s)", [str(d) for d in config.WATCH_DIRS])
    except Exception as e:
        logger.warning("Failed to auto-start watcher: %s", e)
    scheduler = SummaryScheduler(graph, event_log, work_schedule)
    scheduler.start()
    # Warm up embedding model in background (non-blocking startup)
    threading.Thread(
        target=_warmup_embedding_model,
        args=(graph,),
        daemon=True,
        name="embedding-warmup",
    ).start()
    logger.info("Gemvis initialized")
    yield
    if scheduler:
        scheduler.stop()
    if watcher and watcher.is_running():
        watcher.stop()
    logger.info("Gemvis shutdown")


app = FastAPI(title="Gemvis", lifespan=lifespan)


# ── Pydantic Models ──────────────────────────────────────────────

class SearchRequest(BaseModel):
    question: str
    prev_context: dict | None = None


class ChatRequest(BaseModel):
    messages: list[dict]  # [{role: user|assistant, content: str}, ...]
    search_context: dict | None = None  # {query, files} sent by the frontend (unused in stream)


class ConfigRequest(BaseModel):
    watch_dirs: list[str] | None = None
    watch_dir: str | None = None  # legacy single-folder field; folded into watch_dirs


class OpenRequest(BaseModel):
    path: str


class ScheduleRequest(BaseModel):
    schedule: dict  # {monday: {start, end} | null, ...}


class PreferencesUpdate(BaseModel):
    analyze_lang: str | None = None
    analyze_images: bool | None = None
    web_search_enabled: bool | None = None
    llm_temperature: float | None = None
    llm_max_tokens: int | None = None
    llm_top_p: float | None = None
    llm_top_k: int | None = None


# ── Tasks (calendar to-do) ──────────────────────────────────────

class TaskCreateRequest(BaseModel):
    text: str
    date: str


class TaskUpdateRequest(BaseModel):
    completed: bool | None = None
    text: str | None = None


class TaskOut(BaseModel):
    id: str
    text: str
    date: str
    original_date: str
    created_at: str
    completed: bool
    completed_at: str | None = None
    related_files: list[str] = []
    evidence: str | None = None
    rollover_count: int = 0
    locked_by_user: bool = False


# ── v2: Unified FileRecord (Master Record for each file) ─────────

class FileRecord(BaseModel):
    """v2 unified file master record — mirrors frontend `FileRecord` interface.

    Every file in Gemvis has exactly one FileRecord. Any UI feature reads
    this and this alone. Fields are null when analysis_status != "completed".
    """
    # Identity
    file_id: str            # absolute path
    file_name: str
    extension: str

    # Physical
    size_bytes: int | None = None
    file_mtime: str         # ISO datetime
    file_ctime: str         # ISO datetime
    added_at: str           # ISO datetime

    # Analytical (null until completed)
    category: str | None = None
    summary: str | None = None
    tags: list[str] = []
    risk_level: str | None = None
    entities: dict[str, list[str]] = {}
    relations: list[dict] = []

    # State machine
    analysis_status: str = "pending"   # pending | processing | completed | failed
    last_analyzed_at: str | None = None
    error: str | None = None


class FileListResponse(BaseModel):
    files: list[FileRecord]
    pagination: dict
    stats: dict | None = None
    # Whole-dataset status distribution so the UI doesn't have to re-aggregate
    # from the current page (which would undercount on pages after the first).
    status_counts: dict[str, int] = {}


_ENTITY_KEYS = ("people", "places", "projects", "dates", "events")


def _normalize_entities(raw) -> dict[str, list[str]]:
    """Coerce a possibly-malformed entities dict into the canonical shape.

    Real-world GemInsights occasionally have stray scalar keys (e.g. an LLM
    output that put `risk_level` inside `entities` instead of at the top level).
    Pydantic's strict list[str] validation would reject the entire response, so
    we drop unknown keys and any non-list values rather than failing.
    """
    out: dict[str, list[str]] = {k: [] for k in _ENTITY_KEYS}
    if not isinstance(raw, dict):
        return out
    for k, v in raw.items():
        if k not in _ENTITY_KEYS:
            continue
        if isinstance(v, list):
            out[k] = [str(x) for x in v if x]
    return out


def _normalize_relations(raw) -> list[dict]:
    if not isinstance(raw, list):
        return []
    return [r for r in raw if isinstance(r, dict)]


def _insight_to_record(insight, node_dict: dict | None = None) -> FileRecord:
    """Convert a GemInsight (+ optional raw node_dict for physical timestamps)
    into a FileRecord for the v2 API.

    node_dict is the flat KG node representation (`graph._node_to_dict`).
    When provided we prefer its ISO strings for file_mtime/ctime and added_at
    since those are already in display format.
    """
    path = Path(insight.file_path)
    nd = node_dict or {}

    def _iso(epoch: float | None, fallback: str) -> str:
        if epoch:
            return datetime.fromtimestamp(epoch).isoformat()
        return fallback

    return FileRecord(
        file_id=insight.file_path,
        file_name=path.name,
        extension=path.suffix,
        size_bytes=insight.size_bytes,
        file_mtime=nd.get("file_mtime") or _iso(insight.file_mtime, ""),
        file_ctime=nd.get("file_ctime") or _iso(insight.file_ctime, ""),
        added_at=nd.get("added_at") or insight.added_at or "",
        category=insight.category if insight.analysis_status == "completed" else None,
        summary=insight.summary if insight.analysis_status == "completed" else None,
        tags=insight.tags or [],
        risk_level=insight.risk_level if insight.analysis_status == "completed" else None,
        entities=_normalize_entities(insight.entities),
        relations=_normalize_relations(insight.relations),
        analysis_status=insight.analysis_status or "pending",
        last_analyzed_at=insight.last_analyzed_at,
        error=insight.error,
    )


# ── API Endpoints ────────────────────────────────────────────────

@app.get("/api/dashboard", deprecated=True)
def dashboard(
    page: int = 1,
    limit: int = 50,
    sort_by: str = "added_at",  # added_at, file_mtime, file_ctime
    order: str = "desc"  # desc, asc
):
    """[DEPRECATED v2] Use GET /api/files?include_stats=true instead.

    Dashboard with pagination and sorting.

    Args:
        page: Page number (1-indexed)
        limit: Items per page
        sort_by: Sort field (added_at=Gemvis추가일, file_mtime=수정일, file_ctime=생성일)
        order: Sort order (desc/asc)
    """
    stats = graph.get_stats()
    all_files = graph.get_file_nodes()

    # Sort files
    reverse = (order == "desc")
    all_files.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

    # Pagination
    total = len(all_files)
    start = (page - 1) * limit
    end = start + limit
    page_files = all_files[start:end]

    file_list = []
    for f in page_files:
        file_list.append({
            "name": Path(f.get("name", "")).name,
            "path": f.get("name", ""),
            "category": f.get("category", "-"),
            "summary": f.get("summary", "-"),
            "risk_level": f.get("risk_level", "-"),
            "added_at": f.get("added_at", ""),           # Gemvis 추가일
            "file_mtime": f.get("file_mtime", ""),       # 파일 수정일
            "file_ctime": f.get("file_ctime", ""),       # 파일 생성일
        })

    return {
        "stats": stats,
        "files": file_list,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
            "sort_by": sort_by,
            "order": order,
        }
    }


@app.get("/api/graph/data")
def graph_data():
    return graph.get_graph_data()


@app.get("/api/graph/insights/{node_id:path}")
def node_insights(node_id: str):
    return analytics.compute_insights(node_id)


@app.post("/api/search")
def search(req: SearchRequest, lang: str = Depends(get_lang)):
    return search_engine.search(req.question, prev_context=req.prev_context, lang=lang)


@app.post("/api/chat")
def chat(req: ChatRequest, lang: str = Depends(get_lang)):
    return chat_engine.chat(req.messages, lang=lang)


@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, lang: str = Depends(get_lang)):
    def generate():
        for event in chat_engine.stream(req.messages, lang=lang, search_context=req.search_context):
            yield f"data: {_json_module.dumps(event, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _format_dirs(dirs: list) -> str:
    return ", ".join(str(d) for d in dirs) if dirs else ""


@app.post("/api/watcher/start")
def watcher_start():
    dirs = _format_dirs(config.WATCH_DIRS)
    if watcher.is_running():
        return {
            "status": "already_running",
            "message": f"이미 실행 중입니다. 감시 폴더: {dirs}",
            "message_key": "api.watcher.alreadyRunning",
            "message_params": {"dirs": dirs},
        }
    watcher.start()
    return {
        "status": "started",
        "message": f"파일 감시 시작. 감시 폴더: {dirs}",
        "message_key": "api.watcher.started",
        "message_params": {"dirs": dirs},
    }


@app.post("/api/watcher/stop")
def watcher_stop():
    if not watcher.is_running():
        return {
            "status": "not_running",
            "message": "감시가 실행 중이 아닙니다.",
            "message_key": "api.watcher.notRunning",
        }
    watcher.stop()
    return {
        "status": "stopped",
        "message": "파일 감시 중지됨.",
        "message_key": "api.watcher.stopped",
    }


def _count_watched_files(dirs: list[Path]) -> int:
    """Count supported files physically present in watch directories.

    Uses the shared ``config.is_ignored_path`` so this matches exactly
    which files the watcher would actually pick up.
    """
    from gemvis.config import ALL_EXTENSIONS, is_ignored_path
    total = 0
    for d in dirs:
        if not (d.exists() and d.is_dir()):
            continue
        try:
            for path in d.rglob("*"):
                if is_ignored_path(path):
                    continue
                if path.is_file() and path.suffix.lower() in ALL_EXTENSIONS:
                    total += 1
        except OSError:
            continue
    return total


@app.get("/api/watcher/status")
def watcher_status():
    # 실제 감시 중인 모든 폴더 (watcher가 실행 중일 때의 실제 상태)
    actual_watch_dirs = [Path(d) for d in watcher.watch_dirs] if watcher else []

    # 그래프에 저장된 전체 파일 수 (file 타입 노드 개수)
    from rdflib import RDF
    from gemvis.knowledge_graph import GV_TYPE
    file_type_uri = str(GV_TYPE) + "file"
    total_files_in_graph = sum(1 for s, p, o in graph.rdf.triples((None, RDF.type, None))
                                if str(o) == file_type_uri)

    # 감시 폴더 내 물리적으로 존재하는 지원 파일 수 (node_modules 등 제외)
    watched_files_total = _count_watched_files(actual_watch_dirs)

    return {
        "running": watcher.is_running(),
        "watch_dirs": [str(d) for d in actual_watch_dirs],
        "default_dirs": [str(d) for d in config.DEFAULT_WATCH_DIRS],
        "processed_count": total_files_in_graph,  # 그래프 내 전체 파일 수
        "watched_files_total": watched_files_total,  # 감시 폴더 내 지원 파일 총 수
    }


_SCAN_MESSAGE_KEYS = {
    "skeleton":  ("api.watcher.scanSkeletonStarted",  "디스크 스캔(파일 등록)을 시작했습니다."),
    "documents": ("api.watcher.scanDocumentsStarted", "문서 파일 인사이트 추출을 시작했습니다."),
    "images":    ("api.watcher.scanImagesStarted",    "이미지 파일 분석을 시작했습니다."),
    "all":       ("api.watcher.scanStarted",          "전체 인사이트 추출을 시작했습니다."),
}


@app.post("/api/watcher/scan")
def watcher_scan(mode: str = "all"):
    """Trigger a background scan.

    ``mode`` query param picks the scope (default = ``all``):
      • skeleton  — only register file nodes, no LLM
      • documents — extract insights for non-image files only
      • images    — extract insights for image files only
      • all       — extract insights for everything
    """
    if mode not in watcher.SCAN_MODES:
        raise HTTPException(status_code=400, detail=f"unknown scan mode: {mode}")
    if mode == "images":
        prefs.analyze_images = True  # explicit user intent overrides the toggle
    watcher.scan_existing_async(mode=mode)
    key, msg = _SCAN_MESSAGE_KEYS[mode]
    return {
        "status": "started",
        "message": msg,
        "message_key": key,
        "mode": mode,
    }


@app.post("/api/watcher/scan/images")
def watcher_scan_images():
    """Backwards-compat wrapper — prefer ``POST /api/watcher/scan?mode=images``."""
    return watcher_scan(mode="images")


@app.get("/api/watcher/progress")
def watcher_progress():
    return watcher.scan_progress.to_dict()


@app.post("/api/watcher/scan/pause")
def watcher_scan_pause():
    watcher.scan_progress.pause()
    return {"status": "paused"}


@app.post("/api/watcher/scan/resume")
def watcher_scan_resume():
    watcher.scan_progress.resume()
    return {"status": "resumed"}


@app.post("/api/watcher/scan/ack-noop")
def watcher_scan_ack_noop():
    """UI calls this after surfacing the 'nothing to analyze' toast so the
    flag doesn't trigger again on the next poll."""
    watcher.scan_progress.clear_no_op()
    return {"status": "cleared"}


@app.get("/api/watcher/files", deprecated=True)
def watcher_files():
    """감시 중인 모든 파일 목록과 분석 상태 조회.

    Returns:
        {
            "total": int,  # 전체 파일 수
            "analyzed": int,  # 분석 완료된 파일 수
            "files": [
                {
                    "path": str,
                    "name": str,
                    "extension": str,
                    "size": int,
                    "modified_at": str,
                    "analyzed": bool,  # GemInsight 존재 여부
                    "category": str | None,  # 분석된 경우 카테고리
                    "error": str | None  # 에러 발생 시
                }
            ]
        }
    """
    from gemvis.config import ALL_EXTENSIONS

    files = []
    for watch_dir in watcher.watch_dirs:
        if not (watch_dir.exists() and watch_dir.is_dir()):
            continue
        for path in watch_dir.rglob("*"):
            if path.is_file() and path.suffix.lower() in ALL_EXTENSIONS:
                node_id = f"file:{path}"
                analyzed = graph.has_node(node_id)

                file_info = {
                    "path": str(path),
                    "name": path.name,
                    "extension": path.suffix,
                    "size": path.stat().st_size if path.exists() else 0,
                    "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat() if path.exists() else None,
                    "analyzed": analyzed,
                    "category": None,
                    "error": None,
                }

                if analyzed and graph.has_node(node_id):
                    # KnowledgeGraph에서 카테고리 조회 (direct RDF query)
                    from rdflib import Literal, URIRef
                    from gemvis.knowledge_graph import GV_ATTR
                    node_type, name = node_id.split(":", 1)
                    node_uri = graph._node_uri(node_type, name)
                    category_attr = URIRef(str(GV_ATTR) + "category")
                    for obj in graph.rdf.objects(node_uri, category_attr):
                        if isinstance(obj, Literal):
                            file_info["category"] = str(obj)
                            break

                files.append(file_info)

    analyzed_count = sum(1 for f in files if f["analyzed"])

    return {
        "total": len(files),
        "analyzed": analyzed_count,
        "files": files,
    }


@app.post("/api/config")
def save_config(req: ConfigRequest):
    global watcher

    new_dirs: list[Path] | None = None
    if req.watch_dirs is not None:
        new_dirs = []
        for d in req.watch_dirs:
            normalized = config._resolve_dir(d)
            if normalized and normalized not in new_dirs:
                new_dirs.append(normalized)
    elif req.watch_dir:
        normalized = config._resolve_dir(req.watch_dir)
        new_dirs = [normalized] if normalized else []

    if new_dirs is not None:
        config.WATCH_DIRS = new_dirs
        config.WATCH_DIR = new_dirs[0] if new_dirs else Path.home() / "gemvis_watch"
        # Persist to disk so this list survives backend restart. Empty list is
        # also persisted (= "user explicitly cleared everything"). To restore
        # the OS defaults, the user can delete the watch_dirs key from the
        # prefs file or pick the suggestions in the UI again.
        try:
            prefs.watch_dirs = [str(p) for p in new_dirs]
        except Exception as e:
            logger.warning("Failed to persist watch_dirs: %s", e)

    # Preserve the ScanProgress instance across restarts so the UI
    # (ScanToast) keeps showing the correct status after reconfiguration.
    preserved_progress = watcher.scan_progress if watcher else None

    if watcher and watcher.is_running():
        watcher.stop()

    config.ensure_dirs()
    watcher = FileWatcher(
        graph,
        watch_dirs=config.WATCH_DIRS,
        on_file_processed=lambda r: recent_insights.append(r),
        event_log=event_log,
        schedule=work_schedule,
        scan_progress=preserved_progress,
    )
    try:
        watcher.start()
    except Exception as e:
        logger.warning("Failed to start watcher after config change: %s", e)

    # Auto-trigger a background scan so newly-added directories are
    # ingested without the user having to click "기존 파일 스캔".
    try:
        watcher.scan_existing_async()
    except Exception as e:
        logger.warning("Failed to auto-start scan after config change: %s", e)

    dirs = _format_dirs(config.WATCH_DIRS)
    return {
        "status": "saved",
        "message": f"설정 저장 완료. 감시 폴더: {dirs}",
        "message_key": "api.config.saved",
        "message_params": {"dirs": dirs},
    }


@app.delete("/api/graph")
def clear_graph():
    """모든 분석 데이터 초기화 (KnowledgeGraph + EventLog).

    원본 파일은 삭제되지 않으며, 분석 데이터만 초기화됩니다.
    데이터 저장 위치: ~/.gemvis/
    - graph.ttl: 지식그래프 (노드 + 엣지)
    - events.ttl: 이벤트 로그 (파일 생성/수정/삭제 타임라인)
    """
    graph.clear()
    recent_insights.clear()

    # EventLog도 초기화
    if event_log:
        event_log.clear()

    # Tasks도 초기화 (UI 라벨이 "모든 데이터 초기화"이므로 일관성 유지)
    tasks_store.clear_all()

    return {
        "status": "cleared",
        "message": "모든 분석 데이터가 초기화되었습니다. 원본 파일은 그대로 유지됩니다.",
        "message_key": "api.graph.cleared",
    }


@app.get("/api/preferences")
def get_preferences():
    return {
        "analyze_lang": prefs.analyze_lang,
        "analyze_images": prefs.analyze_images,
        "web_search_enabled": prefs.web_search_enabled,
        "llm_temperature": prefs.llm_temperature,
        "llm_max_tokens": prefs.llm_max_tokens,
        "llm_top_p": prefs.llm_top_p,
        "llm_top_k": prefs.llm_top_k,
    }


@app.post("/api/preferences")
def update_preferences(req: PreferencesUpdate):
    if req.analyze_lang and req.analyze_lang in PREF_SUPPORTED_LANGS:
        prefs.analyze_lang = req.analyze_lang
    if req.analyze_images is not None:
        prefs.analyze_images = req.analyze_images
    if req.web_search_enabled is not None:
        prefs.web_search_enabled = req.web_search_enabled
    if req.llm_temperature is not None:
        prefs.llm_temperature = req.llm_temperature
    if req.llm_max_tokens is not None:
        prefs.llm_max_tokens = req.llm_max_tokens
    if req.llm_top_p is not None:
        prefs.llm_top_p = req.llm_top_p
    if req.llm_top_k is not None:
        prefs.llm_top_k = req.llm_top_k
    return {
        "analyze_lang": prefs.analyze_lang,
        "analyze_images": prefs.analyze_images,
        "web_search_enabled": prefs.web_search_enabled,
        "llm_temperature": prefs.llm_temperature,
        "llm_max_tokens": prefs.llm_max_tokens,
        "llm_top_p": prefs.llm_top_p,
        "llm_top_k": prefs.llm_top_k,
    }


@app.get("/api/schedule")
def get_schedule():
    return {"schedule": work_schedule.as_dict()}


@app.post("/api/schedule")
def set_schedule(req: ScheduleRequest, lang: str = Depends(get_lang)):
    try:
        work_schedule.update(req.schedule)
    except Exception as e:
        raise HTTPException(status_code=400, detail=t("api.errors.scheduleFormat", lang=lang, error=str(e)))
    return {"status": "saved", "schedule": work_schedule.as_dict()}


# ── Daily Summary ────────────────────────────────────────────────

def _parse_date(date_str: str, lang: str = "ko") -> datetime:
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail=t("api.errors.dateFormat", lang=lang, date=date_str))


def _validate_period(period: str) -> str:
    if period not in ("work", "personal", "daily"):
        raise HTTPException(status_code=400, detail="period must be 'work', 'personal', or 'daily'")
    return period


@app.get("/api/summary")
def summary_list(date_from: str | None = None, date_to: str | None = None):
    """List all daily summaries, optionally filtered by date range."""
    return {"summaries": list_summaries(graph, date_from=date_from, date_to=date_to)}


@app.get("/api/summary/{date}")
def summary_get_day(date: str, lang: str = Depends(get_lang)):
    """Get work + personal + daily summaries for a given date."""
    _parse_date(date, lang)  # validation
    return {
        "date": date,
        "work": get_summary(date, "work", graph),
        "personal": get_summary(date, "personal", graph),
        "daily": get_summary(date, "daily", graph),
    }


@app.get("/api/summary/{date}/{period}")
def summary_get(date: str, period: str, lang: str = Depends(get_lang)):
    _parse_date(date, lang)
    _validate_period(period)
    result = get_summary(date, period, graph)  # type: ignore[arg-type]
    if result is None:
        raise HTTPException(status_code=404, detail=t("api.errors.summaryNotFound", lang=lang))
    return result


@app.post("/api/summary/{date}/{period}")
def summary_generate(date: str, period: str, lang: str = Depends(get_lang)):
    """Generate (or regenerate) a daily summary. Overwrites existing.

    Side-effect: auto-evaluates user tasks for the same date. Failure of the
    task pass must not fail the summary itself, so we swallow exceptions.
    """
    dt = _parse_date(date, lang)
    _validate_period(period)
    result = generate_summary(
        dt,
        period,  # type: ignore[arg-type]
        graph=graph,
        event_log=event_log,
        schedule=work_schedule,
        lang=lang,
    )
    try:
        file_meta = _gather_file_meta_for_date(date)
        tasks_store.evaluate_tasks_for_date(date, file_meta)
    except Exception as e:
        logger.warning("Auto task evaluation skipped: %s", e)
    return result


@app.delete("/api/summary/{date}/{period}")
def summary_delete(date: str, period: str, lang: str = Depends(get_lang)):
    _parse_date(date, lang)
    _validate_period(period)
    removed = delete_summary(date, period, graph)  # type: ignore[arg-type]
    return {"status": "deleted" if removed else "not_found"}


# ── Tasks (calendar to-do) ──────────────────────────────────────

def _gather_file_meta_for_date(date_str: str) -> list[dict]:
    """Collect lightweight metadata for files active on the given date.

    Used by the task evaluator. Pulls one event_log scan + one graph node
    read per distinct file, plus the cached GemInsight for tags/entities.
    """
    try:
        dt = datetime.fromisoformat(date_str)
    except ValueError:
        return []
    if not event_log or not graph:
        return []

    start = datetime.combine(dt.date(), dtime.min)
    end = datetime.combine(dt.date() + timedelta(days=1), dtime.min)
    events = event_log.events_in_range(start, end)
    paths = list({e.get("file_path", "") for e in events if e.get("file_path")})

    out: list[dict] = []
    for path in paths:
        node_id = f"file:{path}"
        if not graph.has_node(node_id):
            continue
        nd = graph._node_to_dict(graph._node_uri("file", path)) or {}
        ins = insight_service.get_insight(path) if insight_service else None
        out.append(
            {
                "path": path,
                "name": Path(path).name,
                "category": nd.get("category", "") or "",
                "summary": nd.get("summary", "") or "",
                "tags": list(ins.tags) if ins and ins.tags else [],
                "entities": dict(ins.entities) if ins and ins.entities else {},
            }
        )
    return out


def _task_out(t) -> TaskOut:
    return TaskOut(**asdict(t))


@app.get("/api/tasks")
def tasks_list(date: str, lang: str = Depends(get_lang)):
    """List tasks for a date. Rollover-on-read when date == today."""
    _parse_date(date, lang)
    today_str = datetime.now().date().isoformat()
    if date == today_str:
        tasks_store.rollover_to_today()
    items = tasks_store.list_for_date(date)
    return {"date": date, "tasks": [_task_out(t) for t in items]}


@app.post("/api/tasks")
def tasks_create(req: TaskCreateRequest, lang: str = Depends(get_lang)):
    _parse_date(req.date, lang)
    try:
        task = tasks_store.add_task(req.text, req.date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _task_out(task)


@app.patch("/api/tasks/{task_id}")
def tasks_update(task_id: str, req: TaskUpdateRequest):
    try:
        task = tasks_store.update_task(task_id, completed=req.completed, text=req.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return _task_out(task)


@app.delete("/api/tasks/{task_id}")
def tasks_delete(task_id: str):
    if not tasks_store.delete_task(task_id):
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


@app.get("/api/tasks/progress")
def tasks_progress(date_from: str | None = None, date_to: str | None = None, lang: str = Depends(get_lang)):
    """Per-date task progress for a calendar range — feeds the donut gauges."""
    if date_from:
        _parse_date(date_from, lang)
    if date_to:
        _parse_date(date_to, lang)
    return {"progress": tasks_store.progress_in_range(date_from, date_to)}


@app.post("/api/tasks/evaluate")
def tasks_evaluate(date: str, lang: str = Depends(get_lang)):
    """Manually trigger LLM evaluation against the day's files.

    Manual recheck is always ``refresh_all=True`` so the user gets a
    response even when every task is already completed — the LLM refreshes
    evidence / related_files. Completion downgrade is still forbidden.
    """
    _parse_date(date, lang)
    file_meta = _gather_file_meta_for_date(date)
    updated = tasks_store.evaluate_tasks_for_date(date, file_meta, refresh_all=True)
    items = tasks_store.list_for_date(date)
    return {
        "date": date,
        "updated": updated,
        "tasks": [_task_out(t) for t in items],
        "checked_count": sum(1 for t in items if t.date == date),
        "file_count": len(file_meta),
    }


def _is_wsl() -> bool:
    if sys.platform != "linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text().lower()
    except OSError:
        return False


def _to_windows_path(p: Path) -> str | None:
    """Convert WSL /mnt/c/... path to Windows C:\\... path."""
    parts = p.parts
    if len(parts) >= 3 and parts[0] == "/" and parts[1] == "mnt" and len(parts[2]) == 1:
        drive = parts[2].upper()
        rest = "\\".join(parts[3:])
        return f"{drive}:\\{rest}"
    return None


def _to_wsl_unc(p: Path) -> str | None:
    """Convert WSL-local path to \\\\wsl.localhost\\<distro>\\... UNC path."""
    distro = os.environ.get("WSL_DISTRO_NAME")
    if not distro:
        # Fallback: try to read from /etc/os-release or default to 'Ubuntu'
        try:
            for line in Path("/etc/os-release").read_text().splitlines():
                if line.startswith("NAME="):
                    distro = line.split("=", 1)[1].strip().strip('"').split()[0]
                    break
        except OSError:
            pass
    if not distro:
        return None
    rest = "\\".join(p.parts[1:])  # strip leading '/'
    return f"\\\\wsl.localhost\\{distro}\\{rest}"


# ── GemInsight API ───────────────────────────────────────────────

@app.get("/api/insights", deprecated=True)
def list_insights(
    limit: int = 100,
    offset: int = 0,
    category: str | None = None,
    tag: str | None = None,
):
    """GemInsight 목록 조회 (페이징 + 필터).

    Args:
        limit: 최대 반환 개수 (기본: 100)
        offset: 시작 오프셋 (페이징용, 기본: 0)
        category: 카테고리 필터 (선택)
        tag: 태그 필터 (선택)

    Returns:
        {
            "total": int,
            "insights": [GemInsight, ...]
        }
    """
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    insights = insight_service.get_all_insights(
        limit=limit,
        offset=offset,
        category=category,
    )

    # 태그 필터 추가 (InsightService에 없는 기능이므로 여기서 처리)
    if tag:
        insights = [i for i in insights if tag in i.tags]

    return {
        "total": len(insights),
        "insights": [
            {
                "file_path": i.file_path,
                "category": i.category,
                "summary": i.summary,
                "tags": i.tags,
                "risk_level": i.risk_level,
                "error": i.error,
            }
            for i in insights
        ],
    }


@app.get("/api/insight/{file_id:path}", deprecated=True)
def get_insight_detail(file_id: str):
    """단일 GemInsight 상세 조회.

    Args:
        file_id: 파일 경로 (절대 경로)

    Returns:
        GemInsight 전체 정보 (entities, relations 포함)
    """
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    insight = insight_service.get_insight(file_id)
    if not insight:
        raise HTTPException(status_code=404, detail="GemInsight not found")

    return {
        "file_path": insight.file_path,
        "category": insight.category,
        "summary": insight.summary,
        "tags": insight.tags,
        "entities": insight.entities,
        "relations": insight.relations,
        "risk_level": insight.risk_level,
        "error": insight.error,
    }


@app.post("/api/insight/{file_id:path}/regenerate", deprecated=True)
def regenerate_insight_endpoint(file_id: str):
    """GemInsight 재생성 (파일 재분석).

    기존 GemInsight를 삭제하고 파일을 다시 분석하여 새 GemInsight를 생성합니다.

    Args:
        file_id: 파일 경로 (절대 경로)

    Returns:
        {
            "status": "success" | "error",
            "insight": GemInsight (성공 시)
        }
    """
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    insight = insight_service.regenerate_insight(file_id)
    if not insight:
        raise HTTPException(
            status_code=500,
            detail="GemInsight 재생성에 실패했습니다. 파일이 존재하는지 확인해주세요.",
        )

    return {
        "status": "success",
        "insight": {
            "file_path": insight.file_path,
            "category": insight.category,
            "summary": insight.summary,
            "tags": insight.tags,
            "entities": insight.entities,
            "relations": insight.relations,
            "risk_level": insight.risk_level,
            "error": insight.error,
        },
    }


# ── v2: Unified /api/files (FileRecord master endpoints) ────────────

@app.get("/api/files", response_model=FileListResponse)
def list_files(
    page: int = 1,
    limit: int = 50,
    sort_by: str = "added_at",     # added_at | file_mtime | file_ctime
    order: str = "desc",            # desc | asc
    status: str | None = None,      # pending | processing | completed | failed
    category: str | None = None,
    include_stats: bool = False,
):
    """v2 unified file list — replaces /api/dashboard, /api/insights,
    /api/watcher/files. Returns FileRecord[] with pagination and optional stats.

    Performance: iterates graph.get_file_nodes() **once** and reconstructs
    both the GemInsight object and the physical attributes from the same
    node_dict, avoiding the prior 3× RDF scan (get_all_insights +
    has_node + _node_to_dict inside the loop).
    """
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    import json as _json
    file_nodes = graph.get_file_nodes()

    records: list[FileRecord] = []
    for nd in file_nodes:
        file_path = nd.get("name", "")
        if not file_path:
            continue

        # 1) Prefer the authoritative raw_insight JSON when available.
        insight: GemInsight | None = None
        raw = nd.get("raw_insight")
        if raw:
            try:
                insight = GemInsight.from_dict(_json.loads(raw))
            except (ValueError, TypeError):
                insight = None

        # 2) Build a record directly from node attributes. This handles
        #    legacy pre-v2 nodes AND v2 skeleton-only (pending) nodes that
        #    don't yet have raw_insight/entities. Never drop a file node.
        if insight is None:
            # 상태 결정 규칙:
            #   - analysis_status 속성이 있으면 그 값을 사용 (v2 이후 노드)
            #   - 없는데 category/summary가 있으면 'completed' (v2 이전 노드,
            #     이미 LLM 분석이 끝난 상태로 KG에 들어온 경우)
            #   - 둘 다 없으면 'pending' (막 생성된 skeleton)
            explicit_status = nd.get("analysis_status")
            if explicit_status:
                node_status = explicit_status
            elif nd.get("category") or nd.get("summary"):
                node_status = "completed"
            else:
                node_status = "pending"

            size_raw = nd.get("size_bytes", "")
            try:
                size_val: int | None = int(size_raw) if size_raw else None
            except (ValueError, TypeError):
                size_val = None
            insight = GemInsight(
                file_path=file_path,
                category=nd.get("category") or "other",
                summary=nd.get("summary") or "",
                risk_level=nd.get("risk_level") or "auto_safe",
                analysis_status=node_status,
                last_analyzed_at=nd.get("last_analyzed_at") or None,
                added_at=nd.get("added_at") or None,
                size_bytes=size_val,
                error=nd.get("error") or None,
            )

        # Filter on the in-memory object — no extra RDF round-trip.
        if status and (insight.analysis_status or "pending") != status:
            continue
        if category and insight.category != category:
            continue

        try:
            records.append(_insight_to_record(insight, node_dict=nd))
        except Exception as e:
            # One malformed insight must not poison the whole response. Skip
            # it and log so it can be investigated/regenerated later.
            logger.warning(
                "Skipping unrenderable file record %s: %s", file_path, e
            )

    # Sort
    reverse = order == "desc"
    records.sort(key=lambda r: getattr(r, sort_by, "") or "", reverse=reverse)

    total = len(records)
    start = (page - 1) * limit
    page_records = records[start : start + limit]

    stats_payload = graph.get_stats() if include_stats else None

    # Whole-dataset status distribution (computed AFTER filter, so it's
    # consistent with `total`). The UI uses this to show the same counts
    # on the filter buttons regardless of the current page.
    status_counts: dict[str, int] = {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
    for r in records:
        s = r.analysis_status or "pending"
        status_counts[s] = status_counts.get(s, 0) + 1

    return FileListResponse(
        files=page_records,
        pagination={
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit if limit else 1,
            "sort_by": sort_by,
            "order": order,
        },
        stats=stats_payload,
        status_counts=status_counts,
    )


@app.get("/api/file/{file_id:path}", response_model=FileRecord)
def get_file(file_id: str, lang: str = Depends(get_lang)):
    """v2 single file detail — replaces /api/insight/{file_id}."""
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    ins = insight_service.get_insight(file_id)
    if not ins:
        raise HTTPException(status_code=404, detail=t("api.errors.fileNotFound", lang=lang))

    node_id = f"file:{file_id}"
    nd = graph._node_to_dict(graph._node_uri("file", file_id)) if graph.has_node(node_id) else None
    return _insight_to_record(ins, node_dict=nd)


@app.post("/api/file/{file_id:path}/regenerate", response_model=FileRecord)
def regenerate_file(file_id: str, lang: str = Depends(get_lang)):
    """v2 re-analysis — replaces /api/insight/{file_id}/regenerate."""
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    ins = insight_service.regenerate_insight(file_id)
    if not ins:
        raise HTTPException(status_code=500, detail=t("api.errors.reanalysisFailed", lang=lang))

    node_id = f"file:{file_id}"
    nd = graph._node_to_dict(graph._node_uri("file", file_id)) if graph.has_node(node_id) else None
    return _insight_to_record(ins, node_dict=nd)


@app.post("/api/files/retry-failed")
def retry_failed_files():
    """Re-enqueue every failed file for analysis. Returns count of triggered retries."""
    if not insight_service:
        raise HTTPException(status_code=503, detail="InsightService not initialized")

    failed = [
        i for i in insight_service.get_all_insights(limit=10000)
        if i.analysis_status == "failed"
    ]
    count = 0
    for ins in failed:
        # Flip back to pending — the watcher's next scan (or manual) will retry.
        if graph.update_status(ins.file_path, "pending"):
            count += 1
    return {"status": "requeued", "count": count}


@app.post("/api/file/open-folder")
def open_folder(req: OpenRequest, lang: str = Depends(get_lang)):
    """Open the folder containing the given file in the OS file explorer."""
    target = Path(req.path).expanduser()
    if not target.exists():
        raise HTTPException(status_code=404, detail=t("api.errors.pathNotFound", lang=lang, path=str(target)))

    folder = target if target.is_dir() else target.parent

    try:
        if sys.platform == "darwin":
            # macOS: reveal file in Finder
            subprocess.Popen(["open", "-R", str(target)] if target.is_file() else ["open", str(folder)])
        elif sys.platform == "win32":
            # Native Windows
            if target.is_file():
                subprocess.Popen(["explorer", f"/select,{target}"])
            else:
                subprocess.Popen(["explorer", str(folder)])
        elif _is_wsl():
            # WSL: prefer Windows Explorer via /mnt/c mount or \\wsl.localhost UNC
            win_path = _to_windows_path(target if target.is_file() else folder)
            if win_path:
                if target.is_file():
                    subprocess.Popen(["explorer.exe", f"/select,{win_path}"])
                else:
                    subprocess.Popen(["explorer.exe", win_path])
            else:
                # WSL-local path — open via \\wsl.localhost UNC in Windows Explorer
                unc = _to_wsl_unc(target if target.is_file() else folder)
                if unc:
                    if target.is_file():
                        subprocess.Popen(["explorer.exe", f"/select,{unc}"])
                    else:
                        subprocess.Popen(["explorer.exe", unc])
                else:
                    # Last resort: wslview / xdg-open (need wslu / x11 installed)
                    opener = shutil.which("wslview") or shutil.which("xdg-open")
                    if not opener:
                        raise HTTPException(
                            status_code=500,
                            detail=t("api.errors.noFileManager", lang=lang),
                        )
                    subprocess.Popen([opener, str(folder)])
        else:
            # Other Linux
            opener = shutil.which("xdg-open")
            if not opener:
                raise HTTPException(status_code=500, detail=t("api.errors.noFileManager", lang=lang))
            subprocess.Popen([opener, str(folder)])
    except Exception as e:
        logger.error("Failed to open folder: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"status": "ok", "opened": str(folder)}


# ── Directory browser (folder picker) ───────────────────────────

_BROWSE_BLOCKED = ("/proc", "/sys", "/dev", "/run", "/boot", "/sbin", "/snap")


@app.get("/api/dirs/browse")
def browse_dirs(path: str | None = None):
    """List immediate subdirectories of a given path for the folder picker UI."""
    if path:
        resolved = config._resolve_dir(path)
    else:
        resolved = Path.home()

    if resolved is None or not resolved.exists() or not resolved.is_dir():
        return {"current": str(path or "~"), "parent": None, "dirs": [], "error": "not_found"}

    resolved_str = str(resolved)
    if any(resolved_str == b or resolved_str.startswith(b + "/") for b in _BROWSE_BLOCKED):
        return {"current": resolved_str, "parent": str(resolved.parent), "dirs": [], "error": None}

    subdirs: list[str] = []
    try:
        for entry in sorted(resolved.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir():
                    subdirs.append(str(entry))
            except PermissionError:
                continue
    except PermissionError:
        return {"current": resolved_str, "parent": str(resolved.parent), "dirs": [], "error": "permission"}

    parent = str(resolved.parent) if resolved.parent != resolved else None
    return {"current": resolved_str, "parent": parent, "dirs": subdirs, "error": None}


# ── Static file serving (React build) ───────────────────────────

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(
            FRONTEND_DIR / "index.html",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
