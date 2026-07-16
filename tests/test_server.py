from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from pneural_context.pb_config import PBConfig
from pneural_context.server import create_app


class TestCreateApp:
    def test_create_app_with_config(self):
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
        assert app is not None
        assert app.state.config.database_url == "postgresql://test:test@localhost/test"

    def test_create_app_has_routes(self):
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
        routes = [r.path for r in app.routes]
        assert "/health" in routes


class TestHealthEndpoint:
    def test_health_endpoint(self):
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
        mock_pool.fetchrow = AsyncMock(return_value={"id": 1})
        mock_pool.execute = AsyncMock(return_value="UPDATE 1")
        mock_pool.close = AsyncMock()
        app.state.pool = mock_pool
        app.state.llm_client = None
        app.state.embedding_client = None
        app.state.memoria = None
        client = TestClient(app, raise_server_exceptions=True)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
