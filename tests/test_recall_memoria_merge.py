from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pneural_context.pb_memoria import MemoriaBridge
from pneural_context.routers import recall as recall_router


@pytest.fixture
def mock_request(mock_config):
    request = MagicMock()
    request.app.state.config = mock_config
    request.app.state.embedding_client = None
    return request


@pytest.mark.asyncio
async def test_recall_merges_memoria_results(mock_request, mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    memoria = MagicMock(spec=MemoriaBridge)
    memoria.recall = AsyncMock(
        return_value=[
            {"source": "memoria", "text": "past session note", "project": "p", "timestamp": 1}
        ]
    )
    mock_request.app.state.memoria = memoria

    result = await recall_router.recall(
        mock_request, "deploy", project="p", limit=5, pool=mock_pool
    )

    assert result["count"] == 1
    assert result["results"][0]["text"] == "past session note"


@pytest.mark.asyncio
async def test_recall_graceful_when_memoria_down(mock_request, mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    memoria = MagicMock(spec=MemoriaBridge)
    memoria.recall = AsyncMock(side_effect=RuntimeError("timeout"))
    mock_request.app.state.memoria = memoria

    result = await recall_router.recall(
        mock_request, "deploy", project="p", limit=5, pool=mock_pool
    )

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_recall_skip_memoria_when_source_filtered(mock_request, mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    memoria = MagicMock(spec=MemoriaBridge)
    memoria.recall = AsyncMock(return_value=[])
    mock_request.app.state.memoria = memoria

    result = await recall_router.recall(
        mock_request, "deploy", project="p", limit=5, source="memory", pool=mock_pool
    )

    memoria.recall.assert_not_awaited()
    assert result["count"] == 0
