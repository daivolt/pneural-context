from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pneural_context import pb_db


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    pb_db.init_pool(mock_pool)
    yield
    pb_db.init_pool(None)


@pytest.mark.asyncio
async def test_apply_decay(mock_pool):
    mock_pool.fetchval = AsyncMock(side_effect=[10, 2, 5, 1])
    mock_pool.execute = AsyncMock(return_value="UPDATE 8")
    result = await pb_db.apply_decay(pool=mock_pool)
    assert result["total"] == 10
    assert result["red_ink_protected"] == 2
    assert result["consolidated_total"] == 5


@pytest.mark.asyncio
async def test_archive_decay(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "entry": "old entry",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 0.05,
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    mock_pool.acquire = MagicMock()
    conn = AsyncMock()
    conn.fetch = AsyncMock(side_effect=[[row], []])
    conn.execute = AsyncMock(return_value="DELETE 1")
    conn.fetchval = AsyncMock(side_effect=[9, 4])
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    result = await pb_db.archive_decay(threshold=0.1, pool=mock_pool)
    assert result["archived"] == 1


@pytest.mark.asyncio
async def test_get_decay_status(mock_pool):
    record = {
        "id": 1,
        "entry": "fading",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 0.2,
        "last_accessed": 1700000000.0,
        "age_seconds": 86400.0,
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.get_decay_status("p", pool=mock_pool)
    assert result["project"] == "p"
    assert result["total"] == 1
    assert result["fading_count"] == 1


@pytest.mark.asyncio
async def test_archive_memory_entry(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "entry": "old",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 0.05,
        "created_at": "2024-01-01T00:00:00+00:00",
    }
    mock_pool.fetchrow = AsyncMock(return_value=row)
    mock_pool.acquire = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    result = await pb_db.archive_memory_entry(1, pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_archive_memory_entry_not_found(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    result = await pb_db.archive_memory_entry(999, pool=mock_pool)
    assert result is False


@pytest.mark.asyncio
async def test_search_archived(mock_pool):
    record = {
        "id": 1,
        "original_id": 1,
        "project": "p",
        "entry": "old",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 0.05,
        "archived_at": 1700000000.0,
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.search_archived("p", query="old", pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_search_archived_no_query(mock_pool):
    record = {
        "id": 1,
        "original_id": 1,
        "project": "p",
        "entry": "old",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 0.05,
        "archived_at": 1700000000.0,
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.search_archived("p", query="", pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_restore_archived(mock_pool):
    row = {
        "id": 1,
        "original_id": 1,
        "project": "p",
        "entry": "restored",
        "priority": "normal",
        "memory_type": "temporal",
        "strength": 0.3,
    }
    new_row = {"id": 99}
    mock_pool.fetchrow = AsyncMock(side_effect=[row, new_row])
    mock_pool.acquire = MagicMock()
    conn = AsyncMock()
    conn.fetchrow = AsyncMock(return_value=new_row)
    conn.execute = AsyncMock(return_value="DELETE 1")
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    result = await pb_db.restore_archived(1, pool=mock_pool)
    assert result["restored"] is True


@pytest.mark.asyncio
async def test_restore_archived_not_found(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value=None)
    result = await pb_db.restore_archived(999, pool=mock_pool)
    assert result is None
