"""User-defined to-do tasks pinned to calendar dates.

Stored as a single JSON file at ``~/.gemvis/tasks.json``. The Gemvis daily
summary pipeline calls :func:`evaluate_tasks_for_date` so that tasks whose
text matches the day's file activity get auto-checked (with evidence).

Rules:

- Manual user toggle (check/uncheck) locks the task — LLM evaluation
  no longer touches it.
- LLM evaluation only promotes ``completed: False → True``. It never
  flips a previously-completed task back to incomplete.
- Incomplete tasks from past dates roll forward to today the first time
  the user opens today's date (lazy migration, no background cron).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

TASKS_PATH = Path.home() / ".gemvis" / "tasks.json"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(s: str) -> None:
    if not _DATE_RE.match(s or ""):
        raise ValueError(f"Invalid date format: {s!r}, expected YYYY-MM-DD")


@dataclass
class Task:
    id: str
    text: str
    date: str               # currently assigned date (changes via rollover)
    original_date: str      # when the task was first created
    created_at: str
    completed: bool = False
    completed_at: Optional[str] = None
    related_files: list[str] = field(default_factory=list)
    evidence: Optional[str] = None
    rollover_count: int = 0
    # Once the user manually toggles the checkbox, LLM evaluation skips it.
    locked_by_user: bool = False

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=str(d["id"]),
            text=str(d["text"]),
            date=str(d["date"]),
            original_date=str(d.get("original_date", d["date"])),
            created_at=str(d["created_at"]),
            completed=bool(d.get("completed", False)),
            completed_at=d.get("completed_at"),
            related_files=[str(p) for p in d.get("related_files", []) if isinstance(p, str)],
            evidence=d.get("evidence"),
            rollover_count=int(d.get("rollover_count", 0) or 0),
            locked_by_user=bool(d.get("locked_by_user", False)),
        )


# ── Storage ─────────────────────────────────────────────────────


def _load_all() -> list[Task]:
    if not TASKS_PATH.exists():
        return []
    try:
        with TASKS_PATH.open(encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("tasks.json load failed (%s); starting fresh", e)
        return []
    if not isinstance(raw, list):
        return []
    out: list[Task] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            out.append(Task.from_dict(item))
        except (KeyError, ValueError, TypeError) as e:
            logger.warning("Skipping malformed task entry: %s (%s)", item, e)
    return out


def _save_all(tasks: list[Task]) -> None:
    TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(t) for t in tasks]
    with TASKS_PATH.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def clear_all() -> None:
    """Drop every stored task. Called from the global "데이터 초기화" action."""
    _save_all([])


# ── CRUD ────────────────────────────────────────────────────────


def add_task(text: str, target_date: str) -> Task:
    _validate_date(target_date)
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("Task text must not be empty")
    today = datetime.now().date().isoformat()
    if target_date < today:
        raise ValueError("Cannot create tasks in the past")
    now_iso = datetime.now().isoformat(timespec="seconds")
    task = Task(
        id=uuid.uuid4().hex,
        text=cleaned,
        date=target_date,
        original_date=target_date,
        created_at=now_iso,
    )
    tasks = _load_all()
    tasks.append(task)
    _save_all(tasks)
    return task


def update_task(
    task_id: str,
    *,
    completed: Optional[bool] = None,
    text: Optional[str] = None,
) -> Optional[Task]:
    """Apply a manual edit. Any completion change locks the task from LLM eval."""
    tasks = _load_all()
    target: Optional[Task] = None
    for t in tasks:
        if t.id == task_id:
            target = t
            break
    if target is None:
        return None
    if completed is not None and completed != target.completed:
        target.completed = completed
        target.completed_at = (
            datetime.now().isoformat(timespec="seconds") if completed else None
        )
        target.locked_by_user = True
    if text is not None:
        new_text = text.strip()
        if not new_text:
            raise ValueError("Task text must not be empty")
        target.text = new_text
    _save_all(tasks)
    return target


def delete_task(task_id: str) -> bool:
    tasks = _load_all()
    before = len(tasks)
    tasks = [t for t in tasks if t.id != task_id]
    if len(tasks) == before:
        return False
    _save_all(tasks)
    return True


def list_for_date(target_date: str) -> list[Task]:
    _validate_date(target_date)
    return [t for t in _load_all() if t.date == target_date]


def progress_in_range(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list[dict]:
    """Return [{date, total, done}] for every date that has tasks in range.

    Used by the calendar to render per-day donut gauges. Dates with zero
    tasks are omitted so the UI doesn't have to filter again.
    """
    if date_from:
        _validate_date(date_from)
    if date_to:
        _validate_date(date_to)
    buckets: dict[str, dict[str, int]] = {}
    for t in _load_all():
        if date_from and t.date < date_from:
            continue
        if date_to and t.date > date_to:
            continue
        b = buckets.setdefault(t.date, {"total": 0, "done": 0})
        b["total"] += 1
        if t.completed:
            b["done"] += 1
    return [
        {"date": d, "total": v["total"], "done": v["done"]}
        for d, v in sorted(buckets.items())
    ]


def rollover_to_today() -> int:
    """Move every incomplete task whose date < today into today. Returns moved count."""
    today = datetime.now().date().isoformat()
    tasks = _load_all()
    moved = 0
    for t in tasks:
        if not t.completed and t.date < today:
            t.date = today
            t.rollover_count += 1
            moved += 1
    if moved:
        _save_all(tasks)
    return moved


# ── LLM evaluation ──────────────────────────────────────────────


EVAL_PROMPT = """\
You evaluate whether the user's to-do items for {date} were accomplished,
using ONLY the file activity on that day.

TO-DO ITEMS (id → text):
{tasks_block}

FILES ACTIVE ON {date} (path · category · summary · tags · entities):
{files_block}

For each to-do, decide:
- completed: true ONLY if the file activity provides clear evidence the item was done.
- related_files: list of file paths (from the FILES list above) that are evidence. Empty if none.
- evidence: ONE short sentence in Korean explaining your decision.

Return ONLY a JSON object of this exact shape, no prose, no markdown fences:
{{
  "<task_id>": {{"completed": true, "related_files": ["/abs/path"], "evidence": "..."}},
  ...
}}

Rules:
- Use EXACT task_id strings from above as JSON keys.
- A file counts as evidence only if its summary/tags/entities clearly match the to-do text.
- When unsure, set completed=false. Never guess.
- related_files must be paths from the FILES list — never invent paths.
"""


def _format_tasks_block(tasks: list[Task]) -> str:
    if not tasks:
        return "(none)"
    return "\n".join(f"- {t.id} → {t.text}" for t in tasks)


def _format_files_block(file_meta: list[dict]) -> str:
    if not file_meta:
        return "(none)"
    lines: list[str] = []
    for fm in file_meta:
        parts: list[str] = []
        path = fm.get("path", "")
        if path:
            parts.append(path)
        cat = fm.get("category")
        if cat:
            parts.append(f"[{cat}]")
        summary = fm.get("summary")
        if summary:
            parts.append(str(summary))
        tags = fm.get("tags") or []
        if tags:
            parts.append("tags=" + ",".join(str(x) for x in tags))
        ents = fm.get("entities") or {}
        ent_pieces: list[str] = []
        for k in ("people", "projects", "events", "dates", "places"):
            vals = ents.get(k) or []
            if vals:
                ent_pieces.append(f"{k}:{','.join(str(v) for v in vals)}")
        if ent_pieces:
            parts.append("ent=" + ";".join(ent_pieces))
        lines.append("- " + " · ".join(parts))
    return "\n".join(lines)


def _parse_eval_json(text: str) -> dict:
    """Tolerant parser: strips fences, falls back to the first balanced {...}."""
    s = (text or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```\s*$", "", s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    start = s.find("{")
    end = s.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {}


def evaluate_tasks_for_date(
    target_date: str,
    file_meta: list[dict],
    *,
    refresh_all: bool = False,
) -> int:
    """LLM-evaluate tasks for ``target_date``. Returns # updated.

    refresh_all=False (auto, from daily summary hook): only tasks that are
    still incomplete AND not user-locked are considered, so the LLM never
    overrides a user decision in the background.

    refresh_all=True (manual "재검사" button): every task for the date is
    sent to the LLM so evidence/related_files can be refreshed when new
    files arrive. Even in this mode the LLM can never downgrade a
    ``completed=True`` task back to ``False`` — completion is one-way.
    """
    from gemvis.llm_client import complete_text

    _validate_date(target_date)
    all_tasks = _load_all()
    if refresh_all:
        eligible = [t for t in all_tasks if t.date == target_date]
    else:
        eligible = [
            t for t in all_tasks
            if t.date == target_date and not t.completed and not t.locked_by_user
        ]
    if not eligible:
        return 0
    if not file_meta:
        return 0

    prompt = EVAL_PROMPT.format(
        date=target_date,
        tasks_block=_format_tasks_block(eligible),
        files_block=_format_files_block(file_meta),
    )
    try:
        raw = complete_text(prompt, temperature=0.0)
    except Exception as e:
        logger.error("Task evaluation LLM call failed: %s", e)
        return 0

    parsed = _parse_eval_json(raw)
    if not parsed:
        logger.warning("Task evaluation: unparseable LLM output: %r", (raw or "")[:200])
        return 0

    eligible_ids = {t.id for t in eligible}
    allowed_paths = {fm.get("path", "") for fm in file_meta if fm.get("path")}
    updated = 0
    for t in all_tasks:
        if t.id not in eligible_ids:
            continue
        result = parsed.get(t.id)
        if not isinstance(result, dict):
            continue
        completed = bool(result.get("completed", False))
        related = result.get("related_files", [])
        evidence = result.get("evidence", "")

        clean_related: list[str] = []
        if isinstance(related, list):
            for p in related:
                if isinstance(p, str) and p in allowed_paths:
                    clean_related.append(p)

        changed = False
        if completed and not t.completed:
            t.completed = True
            t.completed_at = datetime.now().isoformat(timespec="seconds")
            changed = True
        if clean_related != t.related_files:
            t.related_files = clean_related
            changed = True
        new_evidence = (str(evidence)[:280] if evidence else None) or None
        if new_evidence != t.evidence:
            t.evidence = new_evidence
            changed = True
        if changed:
            updated += 1

    if updated:
        _save_all(all_tasks)
    return updated
