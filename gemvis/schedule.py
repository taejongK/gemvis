"""Weekly work schedule — per-weekday start/end times.

Days without configured hours are treated as fully "personal" time.
Persisted to ~/.gemvis/schedule.json.
"""

import json
import logging
from datetime import datetime, time as dtime
from pathlib import Path

from gemvis.config import PROJECT_ROOT  # noqa: F401  (keeps import order consistent)

logger = logging.getLogger(__name__)

SCHEDULE_PATH = Path.home() / ".gemvis" / "schedule.json"

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

# Default: Mon-Fri 08:00-17:00, weekends off
DEFAULT_SCHEDULE: dict = {
    "monday":    {"start": "08:00", "end": "17:00"},
    "tuesday":   {"start": "08:00", "end": "17:00"},
    "wednesday": {"start": "08:00", "end": "17:00"},
    "thursday":  {"start": "08:00", "end": "17:00"},
    "friday":    {"start": "08:00", "end": "17:00"},
    "saturday":  None,
    "sunday":    None,
}


def _weekday_key(dt: datetime) -> str:
    """Map datetime to the schedule key (monday..sunday)."""
    return WEEKDAYS[dt.weekday()]


def _parse_hhmm(s: str) -> dtime:
    h, m = s.split(":")
    return dtime(int(h), int(m))


class WorkSchedule:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else SCHEDULE_PATH
        self.schedule: dict = {}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Merge with defaults so new keys are present
                merged = dict(DEFAULT_SCHEDULE)
                for day, val in data.items():
                    if day in merged:
                        merged[day] = val
                self.schedule = merged
                return
            except Exception as e:
                logger.error("Failed to load schedule: %s", e)
        self.schedule = dict(DEFAULT_SCHEDULE)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.schedule, f, ensure_ascii=False, indent=2)

    def update(self, schedule: dict):
        """Replace the full schedule with the given mapping (validated)."""
        normalized: dict = {}
        for day in WEEKDAYS:
            val = schedule.get(day)
            if val and isinstance(val, dict) and val.get("start") and val.get("end"):
                # Validate format
                _parse_hhmm(val["start"])
                _parse_hhmm(val["end"])
                normalized[day] = {"start": val["start"], "end": val["end"]}
            else:
                normalized[day] = None
        self.schedule = normalized
        self.save()

    # ── queries ────────────────────────────────────────────────────

    def period_for(self, dt: datetime) -> str:
        """Return 'work' if dt falls inside this weekday's work hours else 'personal'."""
        cfg = self.schedule.get(_weekday_key(dt))
        if not cfg:
            return "personal"
        start = _parse_hhmm(cfg["start"])
        end = _parse_hhmm(cfg["end"])
        current = dt.time()
        return "work" if start <= current < end else "personal"

    def work_window(self, date: datetime) -> tuple[datetime, datetime] | None:
        """Return (start_dt, end_dt) for the work window on the given date, or None if off."""
        cfg = self.schedule.get(_weekday_key(date))
        if not cfg:
            return None
        start_t = _parse_hhmm(cfg["start"])
        end_t = _parse_hhmm(cfg["end"])
        start_dt = datetime.combine(date.date(), start_t)
        end_dt = datetime.combine(date.date(), end_t)
        return start_dt, end_dt

    def as_dict(self) -> dict:
        return dict(self.schedule)
