from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from pneural_context.pb_config import PBConfig
from pneural_context.server import create_app


@pytest.fixture
def app():
    config = PBConfig(
        database_url="postgresql://test:test@localhost/test",
        llm_url="http://localhost:12345/v1",
        llm_model="test-model",
        host="0.0.0.0",
        port=8777,
        embed_backend="",
        embed_url="",
        embed_model="",
        embed_dimensions=768,
    )
    app = create_app(config_override=config)
    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(return_value=[])
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "id": 1,
            "entry": "test",
            "project": "test-project",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
            "updated": True,
        }
    )
    mock_pool.fetchval = AsyncMock(return_value=1)
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    mock_pool.acquire = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchrow = AsyncMock(return_value={"id": 1, "entry": "test"})
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchval = AsyncMock(return_value=1)
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.close = AsyncMock()
    app.state.pool = mock_pool
    app.state.llm_client = AsyncMock()
    app.state.embedding_client = None
    app.state.memoria = None
    return app


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=True)


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestMemoryRoutes:
    def test_get_memory_empty(self, client):
        resp = client.get("/api/memory?project=test-project")
        assert resp.status_code == 200

    def test_get_memory_full_empty(self, client):
        resp = client.get("/api/memory/full?project=test-project")
        assert resp.status_code == 200

    def test_get_red_ink_empty(self, client):
        resp = client.get("/api/memory/red-ink?project=test-project")
        assert resp.status_code == 200

    def test_add_memory(self, client):
        resp = client.post(
            "/api/memory",
            json={
                "project": "test-project",
                "text": "test entry",
                "priority": "normal",
            },
        )
        assert resp.status_code == 200
        assert "id" in resp.json()

    def test_touch_memory_by_ids(self, client):
        resp = client.post(
            "/api/memory/touch",
            json={
                "project": "test-project",
                "ids": [1, 2, 3],
            },
        )
        assert resp.status_code == 200

    def test_touch_memory_by_index(self, client):
        resp = client.post(
            "/api/memory/touch",
            json={
                "project": "test-project",
                "index": 1,
            },
        )
        assert resp.status_code == 200

    def test_boost_memory(self, client):
        resp = client.post(
            "/api/memory/boost",
            json={
                "project": "test-project",
                "index": 1,
            },
        )
        assert resp.status_code == 200

    def test_replace_memory(self, client):
        resp = client.post(
            "/api/memory/replace",
            json={
                "project": "test-project",
                "old": "old text",
                "new": "new text",
            },
        )
        assert resp.status_code == 200

    def test_classify_memory(self, client):
        resp = client.post(
            "/api/memory/classify",
            json={
                "project": "test-project",
            },
        )
        assert resp.status_code == 200

    def test_update_priority(self, client):
        resp = client.patch(
            "/api/memory/1/priority",
            json={
                "project": "test-project",
                "priority": "critical",
            },
        )
        assert resp.status_code == 200

    def test_update_type(self, client):
        resp = client.patch(
            "/api/memory/1/type",
            json={
                "project": "test-project",
                "memory_type": "concept",
            },
        )
        assert resp.status_code == 200

    def test_delete_memory(self, client):
        resp = client.delete("/api/memory/1?project=test-project")
        assert resp.status_code == 200

    def test_get_memory_by_type(self, client):
        resp = client.get("/api/memory/type/concept?project=test-project")
        assert resp.status_code == 200


class TestContextRoutes:
    def test_get_context(self, client):
        resp = client.get("/api/context?project=test-project")
        assert resp.status_code == 200

    def test_get_smart_context_no_conversation(self, client):
        resp = client.post(
            "/api/context/smart",
            json={
                "project": "test-project",
            },
        )
        assert resp.status_code == 200


class TestRecallRoutes:
    def test_recall(self, client):
        resp = client.get("/api/recall?q=test&project=test-project")
        assert resp.status_code == 200


class TestProcedureRoutes:
    def test_list_procedures(self, client):
        resp = client.get("/api/procedures?project=test-project")
        assert resp.status_code == 200

    def test_add_procedure(self, client):
        resp = client.post(
            "/api/procedures",
            json={
                "project": "test-project",
                "task_pattern": "deploy app",
                "steps": ["step1", "step2"],
            },
        )
        assert resp.status_code == 200


class TestDecayRoutes:
    def test_get_decay_status(self, client):
        resp = client.get("/api/decay/status?project=test-project")
        assert resp.status_code == 200

    def test_apply_decay(self, client):
        resp = client.post("/api/decay")
        assert resp.status_code == 200

    def test_archive_decay(self, client):
        resp = client.post("/api/decay/archive?threshold=0.1")
        assert resp.status_code == 200


class TestArchiveRoutes:
    def test_search_archived(self, client):
        resp = client.get("/api/archive/search?project=test-project&q=test")
        assert resp.status_code == 200


class TestConsolidationRoutes:
    def test_get_consolidation_status(self, client):
        resp = client.get("/api/consolidation/status?project=test-project")
        assert resp.status_code == 200

    def test_add_consolidated(self, client):
        resp = client.post(
            "/api/consolidation",
            json={
                "project": "test-project",
                "tier": "immediate",
                "content": "test insight",
            },
        )
        assert resp.status_code == 200

    def test_get_consolidated(self, client):
        resp = client.get("/api/consolidation?project=test-project&tier=immediate")
        assert resp.status_code == 200


class TestCostsRoutes:
    def test_get_costs(self, client):
        resp = client.get("/api/costs?project=test-project")
        assert resp.status_code == 200

    def test_get_cost_summary(self, client):
        resp = client.get("/api/costs/summary?project=test-project")
        assert resp.status_code == 200

    def test_get_cost_trends(self, client):
        resp = client.get("/api/costs/trends?project=test-project")
        assert resp.status_code == 200

    def test_record_cost(self, client):
        resp = client.post(
            "/api/costs",
            json={
                "project": "test-project",
                "session_id": "s1",
                "tokens_injected": 100,
                "tokens_saved_injection": 50,
                "tokens_saved_forgetting": 20,
                "context_type": "full",
                "task_outcome": "success",
            },
        )
        assert resp.status_code == 200


class TestAnchorRoutes:
    def test_get_anchors(self, client):
        resp = client.get("/api/anchors?project=test-project")
        assert resp.status_code == 200


class TestBriefingRoutes:
    def test_get_briefing(self, client):
        resp = client.get("/api/briefing?project=test-project&task=test+task")
        assert resp.status_code == 200


class TestProjectsRoutes:
    def test_list_projects(self, client):
        resp = client.get("/api/projects")
        assert resp.status_code == 200


class TestSessionRoutes:
    def test_add_session(self, client):
        resp = client.post(
            "/api/session/record",
            json={
                "project": "test-project",
                "title": "test session",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert resp.status_code == 200


class TestConfigRoutes:
    def test_get_config(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "stored_config" in data
