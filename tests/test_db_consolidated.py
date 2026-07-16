from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pneural_context import pb_db


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    pb_db.init_pool(mock_pool)
    pb_db.init_embedding_client(None)
    yield
    pb_db.init_pool(None)
    pb_db.init_embedding_client(None)


@pytest.mark.asyncio
async def test_add_consolidated(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 5})
    result = await pb_db.add_consolidated("p", "immediate", "test content", pool=mock_pool)
    assert result == 5


@pytest.mark.asyncio
async def test_add_consolidated_invalid_tier():
    with pytest.raises(ValueError, match="tier must be one of"):
        await pb_db.add_consolidated("p", "invalid_tier", "content", pool=AsyncMock())


@pytest.mark.asyncio
async def test_add_consolidated_invalid_type():
    with pytest.raises(ValueError, match="memory_type must be one of"):
        await pb_db.add_consolidated(
            "p", "immediate", "content", memory_type="invalid", pool=AsyncMock()
        )


@pytest.mark.asyncio
async def test_add_consolidated_invalid_priority():
    with pytest.raises(ValueError, match="priority must be one of"):
        await pb_db.add_consolidated(
            "p", "immediate", "content", priority="invalid", pool=AsyncMock()
        )


@pytest.mark.asyncio
async def test_get_consolidated(mock_pool):
    record = {
        "id": 1,
        "project": "p",
        "tier": "consolidated",
        "content": "test",
        "source_sessions": [],
        "source_episode_ids": [],
        "memory_type": "concept",
        "priority": "normal",
        "strength": 0.8,
        "created_at": 1700000000.0,
        "last_accessed": 1700000000.0,
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.get_consolidated("p", pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_promote_consolidated(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    result = await pb_db.promote_consolidated(1, "timeless", pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_touch_consolidated_by_ids(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 2")
    result = await pb_db.touch_consolidated_by_ids([1, 2], pool=mock_pool)
    assert result == 2


@pytest.mark.asyncio
async def test_touch_consolidated_by_ids_empty():
    result = await pb_db.touch_consolidated_by_ids([], pool=AsyncMock())
    assert result == 0
