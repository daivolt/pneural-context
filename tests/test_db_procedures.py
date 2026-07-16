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


@pytest.mark.asyncio
async def test_add_procedure(mock_pool):
    mock_pool.fetchrow = AsyncMock(return_value={"id": 10})
    result = await pb_db.add_procedure(
        "p", "git commit workflow", "git", ["git add", "git commit"], pool=mock_pool
    )
    assert result == 10


@pytest.mark.asyncio
async def test_list_procedures(mock_pool):
    record = {
        "id": 1,
        "project": "p",
        "task_pattern": "deploy",
        "task_type": "ops",
        "steps": ["build", "test", "deploy"],
        "success_count": 5,
        "fail_count": 1,
        "reinforcement_score": 0.8,
        "last_success_at": 1700000000.0,
        "proven_by": [],
        "created_at": 1700000000.0,
        "retired": False,
    }
    mock_pool.fetch = AsyncMock(return_value=[record])
    result = await pb_db.list_procedures("p", pool=mock_pool)
    assert len(result) == 1
    assert result[0]["task_pattern"] == "deploy"


@pytest.mark.asyncio
async def test_search_procedures(mock_pool):
    record = {
        "id": 1,
        "project": "p",
        "task_pattern": "deploy",
        "task_type": "ops",
        "steps": [],
        "success_count": 5,
        "fail_count": 1,
        "reinforcement_score": 0.8,
        "proven_by": [],
        "created_at": 1700000000.0,
        "retired": False,
        "sim": 0.85,
    }
    mock_pool.acquire = MagicMock()
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="SET")
    conn.fetch = AsyncMock(return_value=[record])
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    result = await pb_db.search_procedures("p", "deploy", pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_retire_procedure(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 1")
    result = await pb_db.retire_procedure(1, pool=mock_pool)
    assert result is True


@pytest.mark.asyncio
async def test_retire_procedure_not_found(mock_pool):
    mock_pool.execute = AsyncMock(return_value="UPDATE 0")
    result = await pb_db.retire_procedure(999, pool=mock_pool)
    assert result is False
