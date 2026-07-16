from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pneural_context.db import dedup as dedup_mod


@pytest.fixture(autouse=True)
def setup_pool(mock_pool):
    from pneural_context import pb_db

    pb_db.init_pool(mock_pool)
    yield
    pb_db.init_pool(None)


@pytest.mark.asyncio
async def test_dedup_keeps_critical_high_strength(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "critical",
            "priority": "critical",
            "memory_type": "red",
            "strength": 0.9,
            "similarity": 0.7,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_dedup_keeps_critical_low_strength(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "critical",
            "priority": "critical",
            "memory_type": "red",
            "strength": 0.3,
            "similarity": 0.6,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_dedup_excludes_critical_below_strength_threshold(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "weak critical",
            "priority": "critical",
            "memory_type": "red",
            "strength": 0.2,
            "similarity": 0.6,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_dedup_excludes_high_similarity(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "redundant",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 0.5,
            "similarity": 0.9,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_dedup_excludes_very_low_similarity(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "irrelevant",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 0.5,
            "similarity": 0.4,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_dedup_keeps_medium_similarity(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "relevant",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 0.5,
            "similarity": 0.65,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert len(result) == 1


@pytest.mark.asyncio
async def test_dedup_custom_thresholds(mock_pool):
    rows = [
        {
            "id": 1,
            "project": "p",
            "entry": "mid",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 0.5,
            "similarity": 0.6,
        },
    ]
    mock_pool.fetch = AsyncMock(return_value=rows)
    result = await dedup_mod.dedup_context_entries(
        "p", [0.1] * 10, threshold_high=0.7, threshold_low=0.5, pool=mock_pool
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_dedup_empty(mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[])
    result = await dedup_mod.dedup_context_entries("p", [0.1] * 10, pool=mock_pool)
    assert result == []
