from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pneural_context.models.context import SmartContextRequest
from pneural_context.routers import context as context_router


@pytest.fixture
def mock_request(mock_config):
    request = MagicMock()
    request.app.state.config = mock_config
    request.app.state.embedding_client = MagicMock()
    request.app.state.embedding_client.embed = AsyncMock(return_value=[0.1] * 768)
    return request


@pytest.fixture
def mock_pool_with_conn(mock_pool):
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="SET")
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value={"id": 1})
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    return mock_pool, conn


@pytest.mark.asyncio
async def test_smart_context_includes_matched_procedures(mock_request, mock_pool_with_conn):
    mock_pool, conn = mock_pool_with_conn
    proc = {
        "id": 1,
        "project": "p",
        "task_pattern": "deploy app",
        "task_type": "ops",
        "steps": ["build", "test", "deploy"],
        "success_count": 5,
        "fail_count": 1,
        "reinforcement_score": 0.8,
        "proven_by": [],
        "created_at": 1700000000.0,
        "retired": False,
        "sim": 0.85,
    }
    conn.fetch = AsyncMock(return_value=[proc])

    with patch.object(
        context_router.pb_db,
        "dedup_context_entries",
        new=AsyncMock(return_value=[]),
    ):
        body = SmartContextRequest(project="p", conversation="how do I deploy the app")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert result["procedures"]
    assert len(result["procedures"]) == 1
    assert result["procedures"][0]["task_pattern"] == "deploy app"


@pytest.mark.asyncio
async def test_smart_context_no_procedures_for_unrelated_conversation(
    mock_request,
    mock_pool_with_conn,
):
    mock_pool, conn = mock_pool_with_conn
    conn.fetch = AsyncMock(return_value=[])

    with patch.object(
        context_router.pb_db,
        "dedup_context_entries",
        new=AsyncMock(return_value=[]),
    ):
        body = SmartContextRequest(project="p", conversation="unrelated topic xyz")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert result["procedures"] == []


@pytest.mark.asyncio
async def test_smart_context_no_procedures_on_search_failure(mock_request, mock_pool_with_conn):
    mock_pool, conn = mock_pool_with_conn
    conn.fetch = AsyncMock(side_effect=RuntimeError("DB down"))

    with patch.object(
        context_router.pb_db,
        "dedup_context_entries",
        new=AsyncMock(return_value=[]),
    ):
        body = SmartContextRequest(project="p", conversation="deploy app")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert result["procedures"] == []
    assert result["source"] == "smart_dedup"
