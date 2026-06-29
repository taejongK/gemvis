"""File event log — persistent record of create/modify/delete actions.

Events are stored separately from the main knowledge graph so that
summaries can be regenerated over historical activity even after files
are deleted. Retention is unlimited; users can delete summaries but
the underlying events remain.
"""

import logging
import uuid
from datetime import datetime, time as dtime
from pathlib import Path

from rdflib import Graph as RDFGraph, Namespace, URIRef, Literal, RDF

from gemvis.config import EVENTS_PATH

logger = logging.getLogger(__name__)

EV_NS = Namespace("http://gemvis.local/event/")
EV_TYPE = Namespace("http://gemvis.local/type/")
EV_ATTR = Namespace("http://gemvis.local/attr/")

ACTIONS = {"created", "modified", "deleted", "original_created"}


class EventLog:
    """Append-only log of file events persisted to TTL."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else EVENTS_PATH
        self.rdf = RDFGraph()
        self.rdf.bind("evn", EV_NS)
        self.rdf.bind("evt", EV_TYPE)
        self.rdf.bind("eva", EV_ATTR)
        self.load()

    # ── persistence ────────────────────────────────────────────────

    def load(self):
        if not self.path.exists():
            logger.info("No existing event log at %s", self.path)
            return
        try:
            self.rdf.parse(self.path, format="turtle")
            logger.info("Loaded event log with %d triples", len(self.rdf))
        except Exception as e:
            logger.error("Failed to load event log: %s", e)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.rdf.serialize(destination=str(self.path), format="turtle")

    # ── writing ────────────────────────────────────────────────────

    def record(
        self,
        action: str,
        file_path: str,
        timestamp: datetime | None = None,
        period: str | None = None,
    ) -> str:
        """Append a new event. Returns the event URI string."""
        if action not in ACTIONS:
            raise ValueError(f"Unknown action: {action}")

        ts = timestamp or datetime.now()
        event_id = uuid.uuid4().hex
        subj = URIRef(str(EV_NS) + event_id)

        self.rdf.add((subj, RDF.type, URIRef(str(EV_TYPE) + "file_event")))
        self.rdf.add((subj, URIRef(str(EV_ATTR) + "action"), Literal(action)))
        self.rdf.add((subj, URIRef(str(EV_ATTR) + "file_path"), Literal(file_path)))
        self.rdf.add((subj, URIRef(str(EV_ATTR) + "timestamp"), Literal(ts.isoformat())))
        if period:
            self.rdf.add((subj, URIRef(str(EV_ATTR) + "period"), Literal(period)))

        self.save()
        return str(subj)

    # ── querying ───────────────────────────────────────────────────

    def events_in_range(
        self,
        start: datetime,
        end: datetime,
        period: str | None = None,
    ) -> list[dict]:
        """Return events whose timestamp falls within [start, end)."""
        results = []
        ts_pred = URIRef(str(EV_ATTR) + "timestamp")
        action_pred = URIRef(str(EV_ATTR) + "action")
        path_pred = URIRef(str(EV_ATTR) + "file_path")
        period_pred = URIRef(str(EV_ATTR) + "period")

        start_iso = start.isoformat()
        end_iso = end.isoformat()

        for subj, _, ts_lit in self.rdf.triples((None, ts_pred, None)):
            ts_str = str(ts_lit)
            if not (start_iso <= ts_str < end_iso):
                continue
            evt = {
                "event_id": str(subj),
                "timestamp": ts_str,
            }
            for _, _, a in self.rdf.triples((subj, action_pred, None)):
                evt["action"] = str(a)
            for _, _, p in self.rdf.triples((subj, path_pred, None)):
                evt["file_path"] = str(p)
            for _, _, pr in self.rdf.triples((subj, period_pred, None)):
                evt["period"] = str(pr)

            if period and evt.get("period") != period:
                continue
            results.append(evt)

        results.sort(key=lambda e: e.get("timestamp", ""))
        return results

    def events_on_date(self, date_str: str, period: str | None = None) -> list[dict]:
        """Convenience: events on YYYY-MM-DD (local time)."""
        date = datetime.fromisoformat(date_str).date()
        start = datetime.combine(date, dtime.min)
        end = datetime.combine(date, dtime.max)
        return self.events_in_range(start, end, period=period)

    def count(self) -> int:
        """Total number of events logged."""
        ts_pred = URIRef(str(EV_ATTR) + "timestamp")
        return sum(1 for _ in self.rdf.triples((None, ts_pred, None)))

    def clear(self):
        """Drop all events and persist an empty log."""
        self.rdf = RDFGraph()
        self.rdf.bind("evn", EV_NS)
        self.rdf.bind("evt", EV_TYPE)
        self.rdf.bind("eva", EV_ATTR)
        self.save()
