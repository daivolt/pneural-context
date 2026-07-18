from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from pneural_context.pb_config import PBConfig
from pneural_context.server import create_app


def _make_config(**kwargs):
    defaults = {
        "database_url": "postgresql://test:test@localhost/test",
        "llm_url": "http://localhost:12345/v1",
        "llm_model": "test-model",
        "host": "0.0.0.0",
        "port": 8777,
        "embed_backend": "",
        "embed_url": "",
        "embed_model": "",
        "embed_dimensions": 768,
    }
    defaults.update(kwargs)
    return PBConfig(**defaults)


def _make_client(config):
    app = create_app(config_override=config)
    mock_pool = AsyncMock()
    mock_pool.fetch = AsyncMock(return_value=[])
    mock_pool.fetchrow = AsyncMock(return_value={"id": 1})
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    mock_pool.acquire = AsyncMock()
    mock_pool.close = AsyncMock()
    app.state.pool = mock_pool
    app.state.llm_client = None
    app.state.embedding_client = None
    app.state.memoria = None
    return TestClient(app, raise_server_exceptions=False)


class TestApiKeyAuth:
    def test_no_key_required_when_not_configured(self):
        config = _make_config(api_key="")
        client = _make_client(config)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_endpoint_not_protected(self):
        config = _make_config(api_key="secret123")
        client = _make_client(config)
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_api_endpoint_rejects_missing_key(self):
        config = _make_config(api_key="secret123")
        client = _make_client(config)
        resp = client.get("/api/memory?project=test")
        assert resp.status_code == 401
        assert "Missing API key" in resp.json()["detail"]

    def test_api_endpoint_rejects_wrong_key(self):
        config = _make_config(api_key="secret123")
        client = _make_client(config)
        resp = client.get("/api/memory?project=test", headers={"X-API-Key": "wrong"})
        assert resp.status_code == 401
        assert "Invalid API key" in resp.json()["detail"]

    def test_api_endpoint_accepts_header_key(self):
        config = _make_config(api_key="secret123")
        client = _make_client(config)
        resp = client.get("/api/status?project=test", headers={"X-API-Key": "secret123"})
        assert resp.status_code == 200

    def test_api_endpoint_accepts_query_key(self):
        config = _make_config(api_key="secret123")
        client = _make_client(config)
        resp = client.get("/api/status?project=test&api_key=secret123")
        assert resp.status_code == 200

    def test_api_endpoint_no_auth_when_key_empty(self):
        config = _make_config(api_key="")
        client = _make_client(config)
        resp = client.get("/api/status?project=test")
        assert resp.status_code == 200
