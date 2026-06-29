"""QA suite for the geminsight-develop v2 refactor.

Covers:
- GemInsight dataclass round-trip (A)
- KG state machine + raw_insight persistence (B)
- Backward compat: pre-v2 nodes without raw_insight (C)
- Watcher 2-stage hydration with monkeypatched LLM (D, E)
- FastAPI /api/files unified endpoints (F)
- v1 deprecated endpoints still respond (G)

No live llama-server required — generate_insight is monkeypatched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from gemvis.embeddings import EmbeddingStore
from gemvis.insight import GemInsight
from gemvis.insight_service import InsightService
from gemvis.knowledge_graph import KnowledgeGraph
from gemvis.watcher import GemvisHandler


# ── Shared fixtures ─────────────────────────────────────────────────


@pytest.fixture
def kg(tmp_path: Path) -> KnowledgeGraph:
    """Isolated KnowledgeGraph using a temporary TTL + embeddings file."""
    emb = EmbeddingStore(path=tmp_path / "emb.npz")
    return KnowledgeGraph(graph_path=tmp_path / "graph.ttl", embeddings=emb)


@pytest.fixture
def sample_completed_insight(tmp_path: Path) -> GemInsight:
    """A fully-populated GemInsight that passed LLM analysis."""
    return GemInsight(
        file_path=str(tmp_path / "meeting.md"),
        category="document",
        summary="Gemvis 회의록",
        tags=["회의", "해커톤"],
        entities={
            "people": ["인규", "준혁"],
            "places": ["강남"],
            "projects": ["Gemvis"],
            "dates": ["2026-05-11"],
            "events": ["회의"],
        },
        relations=[
            {
                "source": "인규",
                "source_type": "person",
                "target": "Gemvis",
                "target_type": "project",
                "relation": "works_on",
            }
        ],
        risk_level="auto_safe",
        file_mtime=1715435400.0,
        file_ctime=1715400000.0,
        size_bytes=2847,
        analysis_status="completed",
        last_analyzed_at="2026-05-12T10:30:00",
    )


# ── A. GemInsight data model ───────────────────────────────────────


class TestGemInsightDataModel:
    def test_defaults_pending(self):
        g = GemInsight(file_path="/a")
        assert g.analysis_status == "pending"
        assert g.error is None
        assert g.last_analyzed_at is None

    def test_to_dict_from_dict_round_trip(self, sample_completed_insight):
        g = sample_completed_insight
        g2 = GemInsight.from_dict(g.to_dict())
        assert g2.file_path == g.file_path
        assert g2.analysis_status == g.analysis_status
        assert g2.last_analyzed_at == g.last_analyzed_at
        assert g2.size_bytes == g.size_bytes
        assert g2.relations == g.relations
        assert g2.entities == g.entities

    def test_from_dict_ignores_unknown_keys(self):
        g = GemInsight.from_dict(
            {"file_path": "/x", "unknown_future_field": "foo", "legacy_junk": 123}
        )
        assert g.file_path == "/x"

    def test_from_dict_missing_keys_use_defaults(self):
        g = GemInsight.from_dict({"file_path": "/x"})
        assert g.category == "other"
        assert g.analysis_status == "pending"
        assert g.tags == []

    def test_json_string_round_trip(self, sample_completed_insight):
        s = json.dumps(sample_completed_insight.to_dict(), ensure_ascii=False)
        g = GemInsight.from_dict(json.loads(s))
        assert g.summary == "Gemvis 회의록"
        assert g.relations[0]["relation"] == "works_on"


# ── B. KG state machine ────────────────────────────────────────────


class TestStateMachine:
    def test_upsert_skeleton_sets_pending(self, kg):
        node_id = kg.upsert_skeleton(
            "/tmp/foo.md", size_bytes=100, file_mtime=1715000000.0, file_ctime=1715000000.0
        )
        assert node_id == "file:/tmp/foo.md"
        nd = kg._node_to_dict(kg._node_uri("file", "/tmp/foo.md"))
        assert nd["analysis_status"] == "pending"
        assert nd["size_bytes"] == "100"

    def test_upsert_skeleton_preserves_added_at(self, kg):
        kg.upsert_skeleton("/tmp/foo.md", 1, 1715000000.0, 1715000000.0)
        first = kg._node_to_dict(kg._node_uri("file", "/tmp/foo.md"))["added_at"]
        kg.upsert_skeleton("/tmp/foo.md", 2, 1715000500.0, 1715000000.0)
        second = kg._node_to_dict(kg._node_uri("file", "/tmp/foo.md"))["added_at"]
        assert first == second

    def test_update_status_transitions(self, kg):
        kg.upsert_skeleton("/tmp/foo.md", 100, 1715000000.0, 1715000000.0)
        assert kg.update_status("/tmp/foo.md", "processing")
        assert (
            kg._node_to_dict(kg._node_uri("file", "/tmp/foo.md"))["analysis_status"]
            == "processing"
        )
        kg.update_status("/tmp/foo.md", "failed", error="LLM timeout")
        nd = kg._node_to_dict(kg._node_uri("file", "/tmp/foo.md"))
        assert nd["analysis_status"] == "failed"
        assert nd["error"] == "LLM timeout"

    def test_update_status_returns_false_for_missing_node(self, kg):
        assert kg.update_status("/nonexistent.md", "processing") is False

    def test_rollback_processing_to_pending(self, kg):
        kg.upsert_skeleton("/tmp/a.md", 1, 1715000000.0, 1715000000.0)
        kg.upsert_skeleton("/tmp/b.md", 2, 1715000000.0, 1715000000.0)
        kg.update_status("/tmp/a.md", "processing")
        kg.update_status("/tmp/b.md", "completed")

        rolled = kg.rollback_processing_to_pending()
        assert rolled == 1
        assert (
            kg._node_to_dict(kg._node_uri("file", "/tmp/a.md"))["analysis_status"]
            == "pending"
        )
        assert (
            kg._node_to_dict(kg._node_uri("file", "/tmp/b.md"))["analysis_status"]
            == "completed"
        )


# ── B2. KG raw_insight persistence ─────────────────────────────────


class TestRawInsightPersistence:
    def test_add_insight_writes_raw_insight_attribute(self, kg, sample_completed_insight):
        kg.add_insight(sample_completed_insight)
        nd = kg._node_to_dict(
            kg._node_uri("file", sample_completed_insight.file_path)
        )
        assert "raw_insight" in nd
        parsed = json.loads(nd["raw_insight"])
        assert parsed["summary"] == "Gemvis 회의록"
        assert parsed["relations"][0]["relation"] == "works_on"

    def test_add_insight_skips_errored_insights(self, kg):
        bad = GemInsight(file_path="/tmp/err.md", error="boom", analysis_status="failed")
        kg.add_insight(bad)
        assert not kg.has_node("file:/tmp/err.md")

    def test_get_file_nodes_contains_raw_insight(self, kg, sample_completed_insight):
        kg.add_insight(sample_completed_insight)
        files = kg.get_file_nodes()
        assert len(files) == 1
        assert "raw_insight" in files[0]


# ── C. Backward compat ─────────────────────────────────────────────


class TestBackwardCompat:
    def test_service_get_insight_uses_raw_path_when_available(
        self, kg, sample_completed_insight
    ):
        kg.add_insight(sample_completed_insight)
        svc = InsightService(kg)
        loaded = svc.get_insight(sample_completed_insight.file_path)
        assert loaded is not None
        assert loaded.relations == sample_completed_insight.relations
        assert loaded.analysis_status == "completed"

    def test_service_falls_back_on_legacy_node(self, kg):
        """Pre-v2 nodes (no raw_insight attribute) must still load via
        neighbor-assembly fallback."""
        kg.add_node(
            "file",
            "/legacy.md",
            category="memo",
            summary="legacy summary",
            risk_level="auto_safe",
            file_mtime="2026-04-01T10:00:00",
            file_ctime="2026-04-01T10:00:00",
            added_at="2026-04-01T10:00:00",
        )
        tag_id = kg.add_node("tag", "legacy-tag")
        kg.add_edge("file:/legacy.md", tag_id, "tagged_with")
        kg.save()

        svc = InsightService(kg)
        loaded = svc.get_insight("/legacy.md")
        assert loaded is not None
        assert loaded.summary == "legacy summary"
        assert "legacy-tag" in loaded.tags
        # Fallback cannot restore relations — documented limitation
        assert loaded.relations == []

    def test_service_falls_back_on_corrupt_raw_insight(self, kg):
        kg.add_node(
            "file",
            "/broken.md",
            category="memo",
            summary="corrupt test",
            raw_insight="{not valid json",
        )
        kg.save()
        svc = InsightService(kg)
        loaded = svc.get_insight("/broken.md")
        assert loaded is not None
        assert loaded.summary == "corrupt test"


# ── D/E. Watcher hydration pipeline ────────────────────────────────


def _make_text_file(tmp_path: Path, name: str, body: str = "hello") -> Path:
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


class TestWatcherHydration:
    def test_stage_transitions_on_success(self, kg, tmp_path, monkeypatch):
        """A brand-new file goes through pending → processing → completed."""
        target = _make_text_file(tmp_path, "note.md", "Gemvis rocks")

        captured_statuses: list[str] = []

        def fake_generate(path):
            nd = kg._node_to_dict(kg._node_uri("file", str(path.resolve())))
            captured_statuses.append(nd["analysis_status"])
            return GemInsight(
                file_path=str(path.resolve()),
                category="memo",
                summary="mock summary",
                tags=["t"],
                analysis_status="completed",
                last_analyzed_at="2026-05-12T10:00:00",
                size_bytes=path.stat().st_size,
            )

        monkeypatch.setattr("gemvis.watcher.generate_insight", fake_generate)

        handler = GemvisHandler(kg)
        handler._process_file(target)

        assert captured_statuses == ["processing"], (
            "Stage 2 must see status=processing, meaning Stage 1 ran first"
        )
        nd = kg._node_to_dict(kg._node_uri("file", str(target.resolve())))
        assert nd["analysis_status"] == "completed"
        assert nd["category"] == "memo"
        assert "raw_insight" in nd

    def test_stage_transition_on_failure(self, kg, tmp_path, monkeypatch):
        target = _make_text_file(tmp_path, "bad.md")

        def fake_generate(path):
            return GemInsight(
                file_path=str(path.resolve()),
                error="LLM exploded",
                analysis_status="failed",
            )

        monkeypatch.setattr("gemvis.watcher.generate_insight", fake_generate)

        handler = GemvisHandler(kg)
        handler._process_file(target)

        nd = kg._node_to_dict(kg._node_uri("file", str(target.resolve())))
        assert nd["analysis_status"] == "failed"
        assert nd["error"] == "LLM exploded"

    def test_stage_transition_on_exception(self, kg, tmp_path, monkeypatch):
        """Even when generate_insight raises, skeleton stays and status=failed."""
        target = _make_text_file(tmp_path, "boom.md")

        def fake_generate(path):
            raise RuntimeError("boom")

        monkeypatch.setattr("gemvis.watcher.generate_insight", fake_generate)

        handler = GemvisHandler(kg)
        handler._process_file(target)

        nd = kg._node_to_dict(kg._node_uri("file", str(target.resolve())))
        assert nd["analysis_status"] == "failed"
        assert "boom" in (nd.get("error") or "")

    def test_duplicate_process_is_idempotent(self, kg, tmp_path, monkeypatch):
        target = _make_text_file(tmp_path, "once.md")
        calls = {"n": 0}

        def fake_generate(path):
            calls["n"] += 1
            return GemInsight(
                file_path=str(path.resolve()),
                category="memo",
                summary="s",
                analysis_status="completed",
            )

        monkeypatch.setattr("gemvis.watcher.generate_insight", fake_generate)

        handler = GemvisHandler(kg)
        handler._process_file(target)
        handler._process_file(target)  # second call: _processed cache hits

        assert calls["n"] == 1


# ── F/G. FastAPI unified endpoints ─────────────────────────────────


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """Fresh FastAPI TestClient with isolated state dirs."""
    monkeypatch.setenv("GEMVIS_GRAPH_PATH", str(tmp_path / "graph.ttl"))
    monkeypatch.setenv("GEMVIS_EMBEDDINGS_PATH", str(tmp_path / "emb.npz"))
    monkeypatch.setenv("GEMVIS_EVENTS_PATH", str(tmp_path / "events.ttl"))
    monkeypatch.setenv("GEMVIS_WATCH_DIRS", str(tmp_path / "watched"))
    (tmp_path / "watched").mkdir()

    import importlib
    import gemvis.config as cfg
    importlib.reload(cfg)
    import gemvis.knowledge_graph as kg_mod
    importlib.reload(kg_mod)
    import gemvis.embeddings as emb_mod
    importlib.reload(emb_mod)
    import gemvis.event_log as evt_mod
    importlib.reload(evt_mod)
    import gemvis.insight_service as is_mod
    importlib.reload(is_mod)
    import gemvis.watcher as w_mod
    importlib.reload(w_mod)
    import gemvis.api as api_mod
    importlib.reload(api_mod)

    client = TestClient(api_mod.app)
    with client:
        yield client, api_mod


class TestUnifiedFileAPI:
    def test_empty_list(self, api_client):
        client, _ = api_client
        r = client.get("/api/files")
        assert r.status_code == 200
        body = r.json()
        assert body["files"] == []
        assert body["pagination"]["total"] == 0

    def test_list_with_stats_include(self, api_client):
        client, _ = api_client
        r = client.get("/api/files?include_stats=true")
        assert r.status_code == 200
        assert r.json()["stats"] is not None

    def test_list_with_stats_excluded(self, api_client):
        client, _ = api_client
        r = client.get("/api/files")
        assert r.json()["stats"] is None

    def test_inserted_insight_appears_as_filerecord(self, api_client):
        client, api_mod = api_client
        ins = GemInsight(
            file_path="/tmp/fixture.md",
            category="memo",
            summary="hello",
            tags=["t"],
            analysis_status="completed",
            last_analyzed_at="2026-05-12T10:00:00",
            size_bytes=42,
            file_mtime=1715000000.0,
            file_ctime=1715000000.0,
        )
        api_mod.graph.add_insight(ins)

        r = client.get("/api/files")
        assert r.status_code == 200
        files = r.json()["files"]
        assert len(files) == 1
        rec = files[0]
        assert rec["file_id"] == "/tmp/fixture.md"
        assert rec["file_name"] == "fixture.md"
        assert rec["analysis_status"] == "completed"
        assert rec["category"] == "memo"
        assert rec["summary"] == "hello"

    def test_status_filter(self, api_client):
        client, api_mod = api_client
        api_mod.graph.upsert_skeleton("/tmp/pend.md", 10, 1715000000.0, 1715000000.0)
        api_mod.graph.add_insight(
            GemInsight(
                file_path="/tmp/done.md",
                category="memo",
                summary="ok",
                analysis_status="completed",
                file_mtime=1715000000.0,
                file_ctime=1715000000.0,
            )
        )

        pending = client.get("/api/files?status=pending").json()["files"]
        completed = client.get("/api/files?status=completed").json()["files"]

        assert [f["file_id"] for f in pending] == ["/tmp/pend.md"]
        assert [f["file_id"] for f in completed] == ["/tmp/done.md"]

    def test_pending_record_has_null_analytical_fields(self, api_client):
        client, api_mod = api_client
        api_mod.graph.upsert_skeleton(
            "/tmp/wait.md", 10, 1715000000.0, 1715000000.0
        )
        body = client.get("/api/files").json()
        rec = body["files"][0]
        assert rec["analysis_status"] == "pending"
        assert rec["category"] is None
        assert rec["summary"] is None
        assert rec["risk_level"] is None

    def test_get_single_file(self, api_client):
        client, api_mod = api_client
        api_mod.graph.add_insight(
            GemInsight(
                file_path="/tmp/x.md",
                category="memo",
                summary="one",
                analysis_status="completed",
                file_mtime=1715000000.0,
                file_ctime=1715000000.0,
            )
        )
        r = client.get("/api/file//tmp/x.md")
        assert r.status_code == 200
        assert r.json()["file_id"] == "/tmp/x.md"

    def test_get_missing_file_returns_404(self, api_client):
        client, _ = api_client
        r = client.get("/api/file//tmp/missing.md")
        assert r.status_code == 404

    def test_retry_failed_requeues(self, api_client):
        client, api_mod = api_client
        api_mod.graph.upsert_skeleton("/tmp/f.md", 1, 1715000000.0, 1715000000.0)
        api_mod.graph.update_status("/tmp/f.md", "failed", error="nope")

        r = client.post("/api/files/retry-failed")
        assert r.status_code == 200
        assert r.json()["count"] == 1
        nd = api_mod.graph._node_to_dict(
            api_mod.graph._node_uri("file", "/tmp/f.md")
        )
        assert nd["analysis_status"] == "pending"


class TestV1Deprecated:
    """v1 endpoints must still respond (backward compat during migration)."""

    def test_dashboard_still_works(self, api_client):
        client, _ = api_client
        r = client.get("/api/dashboard")
        assert r.status_code == 200
        assert "stats" in r.json()

    def test_insights_list_still_works(self, api_client):
        client, _ = api_client
        r = client.get("/api/insights")
        assert r.status_code == 200
        assert "insights" in r.json()

    def test_watcher_files_still_works(self, api_client):
        client, _ = api_client
        r = client.get("/api/watcher/files")
        assert r.status_code == 200
        assert "files" in r.json()


class TestStartupRollback:
    """Lifespan hook rolls orphaned 'processing' nodes back on startup."""

    def test_processing_node_rolled_back_on_startup(self, tmp_path, monkeypatch):
        graph_path = tmp_path / "graph.ttl"
        emb_path = tmp_path / "emb.npz"
        evt_path = tmp_path / "events.ttl"

        from gemvis.embeddings import EmbeddingStore as _ES
        from gemvis.knowledge_graph import KnowledgeGraph as _KG

        emb = _ES(path=emb_path)
        kg = _KG(graph_path=graph_path, embeddings=emb)
        kg.upsert_skeleton("/tmp/stuck.md", 1, 1715000000.0, 1715000000.0)
        kg.update_status("/tmp/stuck.md", "processing")
        del kg

        monkeypatch.setenv("GEMVIS_GRAPH_PATH", str(graph_path))
        monkeypatch.setenv("GEMVIS_EMBEDDINGS_PATH", str(emb_path))
        monkeypatch.setenv("GEMVIS_EVENTS_PATH", str(evt_path))
        monkeypatch.setenv("GEMVIS_WATCH_DIRS", str(tmp_path / "watched"))
        (tmp_path / "watched").mkdir(exist_ok=True)

        import importlib
        import gemvis.config as cfg
        importlib.reload(cfg)
        import gemvis.knowledge_graph as kg_mod
        importlib.reload(kg_mod)
        import gemvis.api as api_mod
        importlib.reload(api_mod)

        client = TestClient(api_mod.app)
        with client:
            r = client.get("/api/file//tmp/stuck.md")
            assert r.status_code == 200
            body = r.json()
            assert body["analysis_status"] == "pending", (
                "Startup hook should have rolled 'processing' → 'pending'"
            )
