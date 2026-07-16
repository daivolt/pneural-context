from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pneural_context import pb_db


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    pb_db.init_pool(mock_pool)
    yield
    pb_db.init_pool(None)


@pytest.mark.asyncio
async def test_record_memory_cost(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 1})
    result = await pb_db.record_memory_cost(
        "p", "sess-1", 100, 50, 25, "full", "success", pool=mock_pool
    )
    assert result == 1


@pytest.mark.asyncio
async def test_record_memory_cost_with_breakdown(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 2})
    breakdown = {"embedding_tokens": 30, "search_tokens": 20}
    result = await pb_db.record_memory_cost(
        "p", "sess-2", 200, 100, 50, "briefing", "partial", breakdown=breakdown, pool=mock_pool
    )
    assert result == 2


@pytest.mark.asyncio
async def test_get_memory_costs(mock_pool):
    record = {
        "id": 1,
        "session_id": "s1",
        "project": "p",
        "tokens_injected": 100,
        "tokens_saved_injection": 50,
        "tokens_saved_forgetting": 25,
        "context_type": "full",
        "task_outcome": "success",
        "created_at": 1700000000.0,
        "breakdown": None,
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.get_memory_costs("p", days=30, pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_get_memory_cost_summary(mock_pool):
    mock_pool.fetchrow = AsyncMock(
        return_value={
            "total_records": 10,
            "total_injected": 1000,
            "total_saved_injection": 500,
            "total_saved_forgetting": 200,
            "avg_injected": 100,
        }
    )
    result = await pb_db.get_memory_cost_summary("p", days=30, pool=mock_pool)
    assert result["total_records"] == 10
