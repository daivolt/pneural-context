from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pneural_context.db import search as search_mod


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    from pneural_context import pb_db

    pb_db.init_pool(mock_pool)
    pb_db.init_embedding_client(None)
    yield
    pb_db.init_pool(None)
    pb_db.init_embedding_client(None)


@pytest.mark.asyncio
async def test_vector_search_memory(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "entry": "test",
        "priority": "normal",
        "memory_type": "concept",
        "strength": 0.9,
        "similarity": 0.95,
    }
    mock_pool.fetch = AsyncMock(return_value=[row])
    result = await search_mod.vector_search_memory("p", [0.1, 0.2], limit=5, pool=mock_pool)
    assert len(result) == 1
    assert result[0]["_table"] == "pb_memory"
    assert result[0]["similarity"] == 0.95


@pytest.mark.asyncio
async def test_vector_search_consolidated(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "tier": "immediate",
        "content": "insight",
        "memory_type": "concept",
        "priority": "important",
        "strength": 0.8,
        "similarity": 0.88,
    }
    mock_pool.fetch = AsyncMock(return_value=[row])
    result = await search_mod.vector_search_consolidated("p", [0.1], pool=mock_pool)
    assert len(result) == 1
    assert result[0]["_table"] == "pb_consolidated_memory"


@pytest.mark.asyncio
async def test_vector_search_procedures(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "task_pattern": "deploy app",
        "task_type": "devops",
        "steps": ["step1", "step2"],
        "reinforcement_score": 3.0,
        "similarity": 0.91,
    }
    mock_pool.fetch = AsyncMock(return_value=[row])
    result = await search_mod.vector_search_procedures("p", [0.1], pool=mock_pool)
    assert len(result) == 1
    assert result[0]["_table"] == "pb_procedural_memory"


@pytest.mark.asyncio
async def test_vector_search_papers(mock_pool):
    row = {
        "id": 1,
        "filename": "paper.pdf",
        "folder": "docs",
        "title": "Test Paper",
        "snippet": "abc",
        "similarity": 0.87,
    }
    mock_pool.fetch = AsyncMock(return_value=[row])
    result = await search_mod.vector_search_papers([0.1], pool=mock_pool)
    assert len(result) == 1
    assert result[0]["_table"] == "pb_papers"


def test_rrf_merge_basic():
    set1 = [{"id": 1, "_table": "t1", "similarity": 0.9}]
    set2 = [{"id": 2, "_table": "t1", "similarity": 0.8}]
    result = search_mod._rrf_merge(set1, set2)
    assert len(result) == 2
    assert result[0]["rrf_score"] > 0


def test_rrf_merge_overlap():
    set1 = [{"id": 1, "_table": "t1", "similarity": 0.9}]
    set2 = [{"id": 1, "_table": "t1", "similarity": 0.8}]
    result = search_mod._rrf_merge(set1, set2)
    assert len(result) == 1
    assert result[0]["rrf_score"] > 0


def test_rrf_merge_empty():
    result = search_mod._rrf_merge([], [])
    assert result == []


@pytest.mark.asyncio
async def test_hybrid_search_memory_no_vec(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "entry": "test",
        "priority": "normal",
        "memory_type": "concept",
        "strength": 0.9,
        "rank": 0.8,
    }
    mock_pool.fetch = AsyncMock(return_value=[row])
    result = await search_mod.hybrid_search_memory("p", "test", query_vec=None, pool=mock_pool)
    assert len(result) == 1
    assert result[0]["_table"] == "pb_memory"


@pytest.mark.asyncio
async def test_hybrid_search_consolidated_no_vec(mock_pool):
    row = {
        "id": 1,
        "project": "p",
        "tier": "immediate",
        "content": "insight",
        "memory_type": "concept",
        "priority": "important",
        "strength": 0.8,
        "rank": 0.7,
    }
    mock_pool.fetch = AsyncMock(return_value=[row])
    result = await search_mod.hybrid_search_consolidated(
        "p", "insight", query_vec=None, pool=mock_pool
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_reindex_table_no_embedding_client():
    with pytest.raises(RuntimeError, match="Embedding client not initialized"):
        await search_mod.reindex_table("pb_memory", "entry")


@pytest.mark.asyncio
async def test_reindex_table_invalid_table():
    mock_ec = MagicMock()
    with patch.object(search_mod, "_embedding_client", mock_ec):
        with pytest.raises(ValueError, match="Invalid table"):
            await search_mod.reindex_table("bad_table", "entry")


@pytest.mark.asyncio
async def test_reindex_table_invalid_column():
    mock_ec = MagicMock()
    with patch.object(search_mod, "_embedding_client", mock_ec):
        with pytest.raises(ValueError, match="Invalid column"):
            await search_mod.reindex_table("pb_memory", "bad_col")
