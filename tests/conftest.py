from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from pneural_context.pb_config import PBConfig


@pytest.fixture
def mock_pool():
    pool = AsyncMock(spec=asyncpg.Pool)
    pool.acquire = MagicMock()
    pool.close = AsyncMock()
    return pool


@pytest.fixture
def mock_conn():
    conn = AsyncMock(spec=asyncpg.Connection)
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.fetchval = AsyncMock(return_value=1)
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.fetch = AsyncMock(return_value=[])
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def mock_config():
    return PBConfig(
        database_url="postgresql://test:test@localhost/test",
        llm_url="http://localhost:12345/v1",
        llm_model="test-model",
        host="0.0.0.0",
        port=8777,
        embed_backend="ollama",
        embed_url="http://localhost:11434",
        embed_model="nomic-embed-text",
        embed_dimensions=768,
    )


@pytest.fixture
def mock_record():
    return {
        "id": 1,
        "project": "test-project",
        "entry": "test entry text",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 1.0,
        "last_accessed": 1700000000.0,
        "created_at": "2024-01-01T00:00:00+00:00",
        "search_enrichments": [],
    }
