from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pneural_context import pb_db


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    pb_db.init_pool(mock_pool)
    pb_db.init_embedding_client(None)
    yield
    pb_db.init_pool(None)
    pb_db.init_embedding_client(None)


@pytest.fixture
def memory_record():
    return {
        "id": 1,
        "project": "test-project",
        "entry": "test entry",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 1.0,
        "last_accessed": 1700000000.0,
        "created_at": "2024-01-01T00:00:00+00:00",
    }


@pytest.mark.asyncio
async def test_add_memory_entry(mock_pool, memory_record):
    mock_pool.fetch = AsyncMock(return_value=[])
    mock_pool.fetchrow = AsyncMock(return_value={"id": 42})
    result = await pb_db.add_memory_entry("test-project", "hello world", pool=mock_pool)
    assert result == 42
    mock_pool.fetchrow.assert_called_once()


@pytest.mark.asyncio
async def test_add_memory_entry_critical(memory_record):
    pool = AsyncMock()
    pool.fetch = AsyncMock(return_value=[])
    pool.fetchrow = AsyncMock(return_value={"id": 99})
    result = await pb_db.add_memory_entry("proj", "critical note", "critical", pool=pool)
    assert result == 99


@pytest.mark.asyncio
async def test_get_memory_entries(mock_pool, memory_record):
    mock_pool.fetch = AsyncMock(return_value=[memory_record])
    result = await pb_db.get_memory_entries("test-project", pool=mock_pool)
    assert len(result) == 1
    assert result[0]["project"] == "test-project"


@pytest.mark.asyncio
async def test_get_memory_entries_full(mock_pool, memory_record):
    record = {**memory_record, "search_enrichments": []}
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.get_memory_entries_full("test-project", pool=mock_pool)
    assert len(result) == 1
    assert "search_enrichments" in result[0]


@pytest.mark.asyncio
async def test_get_red_ink(mock_pool):
    record = {
        "id": 1,
        "project": "p",
        "entry": "critical note",
        "priority": "critical",
        "memory_type": "red",
        "strength": 0.9,
        "last_accessed": 1700000000.0,
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.get_red_ink("p", min_strength=0.5, pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_update_memory_priority(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    result = await pb_db.update_memory_priority("p", 1, "critical", pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_update_memory_priority_not_found(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 0")
    result = await pb_db.update_memory_priority("p", 999, "critical", pool=mock_pool)
    assert result is False


@pytest.mark.asyncio
async def test_update_memory_type(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    result = await pb_db.update_memory_type("p", 1, "concept", pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_update_memory_type_invalid():
    with pytest.raises(ValueError, match="memory_type must be one of"):
        await pb_db.update_memory_type("p", 1, "invalid_type", pool=AsyncMock())


@pytest.mark.asyncio
async def test_touch_memory_access(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    result = await pb_db.touch_memory_access("p", 1, pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_touch_memory_by_ids(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 3")
    result = await pb_db.touch_memory_by_ids([1, 2, 3], pool=mock_pool)
    assert result == 3


@pytest.mark.asyncio
async def test_touch_memory_by_ids_empty():
    result = await pb_db.touch_memory_by_ids([], pool=AsyncMock())
    assert result == 0


@pytest.mark.asyncio
async def test_boost_memory_entry(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 1, "strength": 1.0})
    result = await pb_db.boost_memory_entry("p", 1, pool=mock_pool)
    assert result["updated"] is True
    assert result["id"] == 1


@pytest.mark.asyncio
async def test_boost_memory_entry_not_found(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    result = await pb_db.boost_memory_entry("p", 999, pool=mock_pool)
    assert result["updated"] is False


@pytest.mark.asyncio
async def test_replace_memory_entry(mock_pool):
    mock_pool.acquire = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value={"id": 1, "entry": "old text"})
    conn.execute = AsyncMock(return_value="UPDATE 1")
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    result = await pb_db.replace_memory_entry("p", "old", "new", pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_delete_memory_entry(mock_pool):
    mock_pool.execute = AsyncMock(return_value="DELETE 1")
    result = await pb_db.delete_memory_entry("p", 1, pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_get_memory_char_count(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"total": 150})
    result = await pb_db.get_memory_char_count("p", pool=mock_pool)
    assert result == 150


@pytest.mark.asyncio
async def test_get_memory_char_count_empty(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    result = await pb_db.get_memory_char_count("p", pool=mock_pool)
    assert result == 0
