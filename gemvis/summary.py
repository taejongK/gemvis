"""Daily summary generator.

Builds a work or personal summary for a given date by combining:
- File events (events.ttl) within the target time window
- Current file metadata (summary/category/tags from the main graph)

Persists each summary as a `gvt:daily_summary` node in the main TTL graph,
identified by `daily_summary:YYYY-MM-DD_<period>`.
"""

import logging
from collections import defaultdict
from datetime import datetime, time as dtime, timedelta
from pathlib import Path
from typing import Literal

from gemvis.event_log import EventLog
from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.schedule import WorkSchedule
from gemvis.llm_client import complete_text
from gemvis.i18n import t

logger = logging.getLogger(__name__)

Period = Literal["work", "personal", "daily"]


LANG_NAMES = {"ko": "Korean", "en": "English", "ja": "Japanese", "zh": "Chinese"}


SUMMARY_PROMPT = """\
You are summarizing one day of a user's file activity for Gemvis, a local file assistant.

DATE: {date}
PERIOD: {period}   # work = work hours, personal = personal hours
WINDOW: {window}

FILE ACTIVITY (grouped by file, most recent action):
{activity}

For each file still analyzed, a short summary is included in the list above.

Your task:
1. Write a concise summary of what the user did during this period in {language}.
2. 2-4 short paragraphs or a bullet list (whichever is clearer).
3. Group by topic/project when possible.
4. Mention total counts (created/modified/deleted) briefly.
5. If the activity list is empty, simply say there was no significant activity.

Return ONLY the summary text in {language}. No JSON, no markdown fences, no preamble.
"""


DAILY_SUMMARY_PROMPT = """\
You are summarizing one full day (00:00–23:59) of a user's file activity for Gemvis in ONE short sentence.

DATE: {date}
FILE ACTIVITY (grouped by file, most recent action):
{activity}

For each file still analyzed, a short summary is included in the list above.

Your task:
1. Write exactly ONE short sentence (under 30 words) in {language} capturing the day's core theme.
2. Be concrete: mention the main topic, project, or theme — not "the user worked on files".
3. If the activity is empty, say briefly that there was no significant activity that day.

Return ONLY the single sentence in {language}. No JSON, no markdown, no preamble, no list bullets.
"""


def _period_window(date: datetime, period: Period, schedule: WorkSchedule, lang: str = "ko") -> tuple[datetime, datetime, str] | None:
    """Return (start, end, label) for the requested period on `date`.

    Returns None if the period is not applicable
    (e.g. work period on a day with no schedule).
    """
    day = date.date()
    window = schedule.work_window(date)

    if period == "daily":
        # Full day, 00:00 → next 00:00. Schedule is irrelevant.
        start = datetime.combine(day, dtime.min)
        end = datetime.combine(day + timedelta(days=1), dtime.min)
        return start, end, "00:00-23:59"

    if period == "work":
        if window is None:
            return None
        start, end = window
        return start, end, f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"

    # personal: complement of work window within the day
    if window is None:
        # Entire day is personal
        start = datetime.combine(day, dtime.min)
        end = datetime.combine(day + timedelta(days=1), dtime.min)
        return start, end, t("summary.personalNight", lang=lang)
    else:
        # Personal covers before start + after end. We merge both halves
        # into a list of events below, so here we just return the full day.
        start = datetime.combine(day, dtime.min)
        end = datetime.combine(day + timedelta(days=1), dtime.min)
        return start, end, f"{window[0].strftime('%H:%M')} 전 / {window[1].strftime('%H:%M')} 이후"


def _collect_events(
    events: list[dict],
    period: Period,
    work_window: tuple[datetime, datetime] | None,
) -> list[dict]:
    """Filter events to the requested period."""
    if period == "daily":
        # All events that day, regardless of schedule.
        return list(events)

    if period == "work":
        if work_window is None:
            return []
        start, end = work_window
        start_iso, end_iso = start.isoformat(), end.isoformat()
        return [e for e in events if start_iso <= e.get("timestamp", "") < end_iso]

    # personal
    if work_window is None:
        return events  # whole day
    start, end = work_window
    start_iso, end_iso = start.isoformat(), end.isoformat()
    return [e for e in events if not (start_iso <= e.get("timestamp", "") < end_iso)]


def _group_by_file(events: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for e in events:
        path = e.get("file_path", "?")
        grouped[path].append(e)
    return grouped


def _format_activity(
    grouped: dict[str, list[dict]],
    graph: KnowledgeGraph,
) -> str:
    """Build a text block describing each file's activity for the LLM prompt."""
    if not grouped:
        return "(활동 없음)"

    lines: list[str] = []
    for path, evts in grouped.items():
        # Sort by time
        evts = sorted(evts, key=lambda x: x.get("timestamp", ""))
        actions = [e.get("action", "?") for e in evts]
        action_counts: dict[str, int] = defaultdict(int)
        for a in actions:
            action_counts[a] += 1
        # Compact action summary
        action_str = ", ".join(f"{k}×{v}" if v > 1 else k for k, v in action_counts.items())

        times = [e.get("timestamp", "")[:16].replace("T", " ") for e in evts]
        first_t, last_t = times[0] if times else "", times[-1] if times else ""

        # Current graph metadata (if file still exists)
        node_id = f"file:{path}"
        info_parts: list[str] = []
        if graph.has_node(node_id):
            node_type, name = node_id.split(":", 1)
            nd = graph._node_to_dict(graph._node_uri(node_type, name))
            if nd:
                if nd.get("category"):
                    info_parts.append(f"분류:{nd['category']}")
                if nd.get("summary"):
                    info_parts.append(f"요약:{nd['summary']}")
        else:
            info_parts.append("(현재 삭제됨)")

        file_name = Path(path).name
        time_range = first_t if first_t == last_t else f"{first_t}~{last_t}"
        info_str = " · ".join(info_parts) if info_parts else "(메타 없음)"
        lines.append(f"- {file_name} [{action_str}] {time_range}\n    {info_str}")

    return "\n".join(lines)


def _count_actions(events: list[dict]) -> dict[str, int]:
    """Count distinct files per action type."""
    by_action_files: dict[str, set[str]] = defaultdict(set)
    for e in events:
        by_action_files[e.get("action", "?")].add(e.get("file_path", "?"))
    return {k: len(v) for k, v in by_action_files.items()}


def generate_summary(
    date: datetime,
    period: Period,
    graph: KnowledgeGraph,
    event_log: EventLog,
    schedule: WorkSchedule,
    *,
    skip_if_empty: bool = False,
    lang: str = "ko",
) -> dict | None:
    """Generate and persist a daily summary for the given date+period.

    If ``skip_if_empty`` is True and there were no file events in the period,
    no node is created and ``None`` is returned. Manual generations from the
    UI keep the default (False) so the user always gets a result.
    """
    # 1. Determine the time window
    windowed = _period_window(date, period, schedule, lang)
    if windowed is None:
        return {
            "id": None,
            "date": date.date().isoformat(),
            "period": period,
            "summary": t("summary.noWorkHours", lang=lang),
            "file_count": 0,
            "generated_at": datetime.now().isoformat(),
            "work_hours": "",
            "files": [],
        }

    start, end, window_label = windowed

    # 2. Gather events on that date, then filter by period
    day_events = event_log.events_in_range(
        datetime.combine(date.date(), dtime.min),
        datetime.combine(date.date() + timedelta(days=1), dtime.min),
    )
    if period == "work":
        work_window = (start, end)
        events = _collect_events(day_events, "work", work_window)
    elif period == "daily":
        events = _collect_events(day_events, "daily", None)
    else:
        work_window = schedule.work_window(date)
        events = _collect_events(day_events, "personal", work_window)

    grouped = _group_by_file(events)
    action_counts = _count_actions(events)
    file_paths = list(grouped.keys())

    if skip_if_empty and not events:
        logger.info("No %s activity for %s — skipping auto summary", period, date.date())
        return None

    # 3. Call the LLM for natural-language summary
    activity_text = _format_activity(grouped, graph)
    if period == "daily":
        prompt = DAILY_SUMMARY_PROMPT.format(
            date=date.date().isoformat(),
            activity=activity_text,
            language=LANG_NAMES.get(lang, "Korean"),
        )
    else:
        prompt = SUMMARY_PROMPT.format(
            date=date.date().isoformat(),
            period=period,
            window=window_label,
            activity=activity_text,
            language=LANG_NAMES.get(lang, "Korean"),
        )

    try:
        summary_text = complete_text(prompt)
    except Exception as e:
        logger.error("Summary LLM failed: %s", e)
        summary_text = "(요약 생성 실패) 원본 이벤트로만 기록됩니다."

    # 4. Persist to graph as a daily_summary node
    saved_window_label = window_label if period in ("work", "daily") else ""
    summary_id = _save_summary_node(
        graph=graph,
        date=date.date().isoformat(),
        period=period,
        summary_text=summary_text,
        window_label=saved_window_label,
        action_counts=action_counts,
        file_paths=file_paths,
    )

    return {
        "id": summary_id,
        "date": date.date().isoformat(),
        "period": period,
        "summary": summary_text,
        "file_count": len(file_paths),
        "action_counts": action_counts,
        "work_hours": saved_window_label,
        "generated_at": datetime.now().isoformat(),
        "files": [
            {"path": p, "actions": [e["action"] for e in evts]}
            for p, evts in grouped.items()
        ],
    }


def _save_summary_node(
    graph: KnowledgeGraph,
    date: str,
    period: Period,
    summary_text: str,
    window_label: str,
    action_counts: dict[str, int],
    file_paths: list[str],
) -> str:
    """Write the summary as a `gvt:daily_summary` node."""
    name = f"{date}_{period}"
    # Remove any pre-existing summary for the same slot
    existing_id = f"daily_summary:{name}"
    if graph.has_node(existing_id):
        graph.remove_node(existing_id, cascade_orphans=False)

    node_id = graph.add_node(
        "daily_summary",
        name,
        date=date,
        period=period,
        summary=summary_text,
        work_hours=window_label,
        file_count=len(file_paths),
        created_count=action_counts.get("created", 0),
        modified_count=action_counts.get("modified", 0),
        deleted_count=action_counts.get("deleted", 0),
        generated_at=datetime.now().isoformat(),
    )

    for path in file_paths:
        target = f"file:{path}"
        if graph.has_node(target):
            graph.add_edge(node_id, target, "covers_file")

    graph.save()
    return node_id


def get_summary(
    date: str,
    period: Period,
    graph: KnowledgeGraph,
) -> dict | None:
    """Load a persisted summary from the graph. Returns None if not present."""
    name = f"{date}_{period}"
    node_id = f"daily_summary:{name}"
    if not graph.has_node(node_id):
        return None
    node_type, nname = node_id.split(":", 1)
    nd = graph._node_to_dict(graph._node_uri(node_type, nname))
    if nd is None:
        return None

    # Collect covered files
    files = []
    for n in graph.get_neighbors(node_id):
        if n.get("type") == "file":
            files.append({"id": n["id"], "name": n.get("name", "")})

    return {
        "id": node_id,
        "date": nd.get("date"),
        "period": nd.get("period"),
        "summary": nd.get("summary", ""),
        "work_hours": nd.get("work_hours", ""),
        "file_count": int(nd.get("file_count", 0) or 0),
        "created_count": int(nd.get("created_count", 0) or 0),
        "modified_count": int(nd.get("modified_count", 0) or 0),
        "deleted_count": int(nd.get("deleted_count", 0) or 0),
        "generated_at": nd.get("generated_at"),
        "files": files,
    }


def delete_summary(date: str, period: Period, graph: KnowledgeGraph) -> bool:
    """Remove a persisted summary. Returns True if it existed."""
    node_id = f"daily_summary:{date}_{period}"
    return graph.remove_node(node_id, cascade_orphans=False)


def list_summaries(
    graph: KnowledgeGraph,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict]:
    """List all daily_summary nodes, optionally filtered by inclusive date range.

    Uses direct RDF iteration (workaround for pyparsing race condition in multithreaded env).
    """
    from rdflib import RDF, Literal, URIRef
    from gemvis.knowledge_graph import GV_TYPE, GV_ATTR

    type_uri = URIRef(str(GV_TYPE) + "daily_summary")
    attr_prefix = str(GV_ATTR)

    results = []
    for subj in graph.rdf.subjects(RDF.type, type_uri):
        # Extract all attributes for this summary node
        attrs = {}
        for pred, obj in graph.rdf.predicate_objects(subj):
            pred_str = str(pred)
            if pred_str.startswith(attr_prefix) and isinstance(obj, Literal):
                key = pred_str[len(attr_prefix):]
                attrs[key] = str(obj)

        date_str = attrs.get("date", "")
        if date_from and date_str < date_from:
            continue
        if date_to and date_str > date_to:
            continue

        results.append({
            "date": date_str,
            "period": attrs.get("period", ""),
            "summary": attrs.get("summary", ""),
            "work_hours": attrs.get("work_hours", ""),
            "file_count": int(attrs.get("file_count") or 0),
            "created_count": int(attrs.get("created_count") or 0),
            "modified_count": int(attrs.get("modified_count") or 0),
            "deleted_count": int(attrs.get("deleted_count") or 0),
            "generated_at": attrs.get("generated_at", ""),
        })

    # Sort by date descending (Python sort instead of SPARQL ORDER BY)
    results.sort(key=lambda x: x["date"], reverse=True)
    return results
