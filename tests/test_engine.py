from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from pneural_context import pb_engine


def test_to_epoch():
    from pneural_context.pb_engine import _to_epoch

    assert _to_epoch(1700000000.0) == 1700000000.0
    assert _to_epoch(0) == 0.0
    assert _to_epoch("not a number") == 0.0


@pytest.mark.asyncio
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
@patch("pneural_context.pb_db.list_procedures", new_callable=AsyncMock)
@patch("pneural_context.pb_db.get_consolidated_for_injection", new_callable=AsyncMock)
async def test_auto_classify_no_llm(mock_consolidated, mock_procedures, mock_entries):
    mock_entries.return_value = [
        {
            "id": 1,
            "project": "p",
            "entry": "temporal note",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
        },
    ]
    result = await pb_engine.auto_classify("p", llm=None)
    assert result["project"] == "p"
    assert result["classified"] == 0
    assert result["error"] == "no LLM client"


@pytest.mark.asyncio
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
async def test_auto_classify_no_unclassified(mock_entries):
    mock_entries.return_value = [
        {
            "id": 1,
            "project": "p",
            "entry": "classified",
            "priority": "normal",
            "memory_type": "concept",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
        },
    ]
    llm = AsyncMock()
    result = await pb_engine.auto_classify("p", llm=llm)
    assert result["classified"] == 0


@pytest.mark.asyncio
@patch("pneural_context.pb_db.update_memory_type", new_callable=AsyncMock)
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
async def test_auto_classify_with_llm(mock_entries, mock_update):
    mock_entries.return_value = [
        {
            "id": 1,
            "project": "p",
            "entry": "temporal note",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
        },
    ]
    mock_update.return_value = True
    llm = AsyncMock()
    llm.classify = AsyncMock(return_value="concept")
    result = await pb_engine.auto_classify("p", llm=llm)
    assert result["classified"] == 1


@pytest.mark.asyncio
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
async def test_auto_classify_llm_failure(mock_entries):
    mock_entries.return_value = [
        {
            "id": 1,
            "project": "p",
            "entry": "temporal note",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
        },
    ]
    llm = AsyncMock()
    llm.classify = AsyncMock(side_effect=Exception("LLM error"))
    result = await pb_engine.auto_classify("p", llm=llm)
    assert result["classified"] == 0


@pytest.mark.asyncio
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
async def test_run_consolidation_no_entries(mock_entries):
    mock_entries.return_value = []
    result = await pb_engine.run_consolidation("p", llm=None)
    assert result["project"] == "p"
    assert result.get("reason") == "no entries"


@pytest.mark.asyncio
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
@patch("pneural_context.pb_db.list_procedures", new_callable=AsyncMock)
@patch("pneural_context.pb_db.get_consolidated_for_injection", new_callable=AsyncMock)
async def test_generate_anchors(mock_consolidated, mock_procedures, mock_entries):
    mock_entries.return_value = [
        {
            "id": 1,
            "project": "p",
            "entry": "critical note",
            "priority": "critical",
            "memory_type": "red",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
        },
    ]
    mock_procedures.return_value = [
        {"id": 1, "task_pattern": "deploy app", "reinforcement_score": 3.0, "steps": ["step1"]},
    ]
    mock_consolidated.return_value = [
        {"id": 1, "tier": "immediate", "content": "insight", "priority": "normal", "strength": 0.5},
    ]
    result = await pb_engine.generate_anchors("p")
    assert result["project"] == "p"
    assert result["active_memory_count"] == 1
    assert result["red_ink_count"] == 1


@pytest.mark.asyncio
@patch("pneural_context.pb_db.get_memory_entries_full", new_callable=AsyncMock)
@patch("pneural_context.pb_db.list_procedures", new_callable=AsyncMock)
@patch("pneural_context.pb_db.get_consolidated_for_injection", new_callable=AsyncMock)
async def test_generate_briefing_no_llm(mock_consolidated, mock_procedures, mock_entries):
    mock_entries.return_value = [
        {
            "id": 1,
            "project": "p",
            "entry": "test entry",
            "priority": "normal",
            "memory_type": "temporal",
            "strength": 1.0,
            "last_accessed": 1700000000.0,
            "created_at": "2024-01-01T00:00:00+00:00",
            "search_enrichments": [],
        },
    ]
    mock_procedures.return_value = [
        {"id": 1, "task_pattern": "deploy app", "reinforcement_score": 3.0, "steps": ["step1"]},
    ]
    mock_consolidated.return_value = []
    result = await pb_engine.generate_briefing("p", task_description="test task", llm=None)
    assert result["project"] == "p"
    assert "briefing" in result
