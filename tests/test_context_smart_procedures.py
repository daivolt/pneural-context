from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pneural_context.db import procedures as procedures_db
from pneural_context.models.context import SmartContextRequest
from pneural_context.routers import context as context_router


def _proc(pattern: str, steps: list[str] | None = None) -> dict:
    return {
        "id": 1,
        "project": "p",
        "task_pattern": pattern,
        "task_type": "ops",
        "steps": steps or ["s1", "s2"],
        "success_count": 5,
        "fail_count": 1,
        "reinforcement_score": 0.8,
        "last_success_at": 1700000000.0,
        "proven_by": [],
        "created_at": 1700000000.0,
        "retired": False,
    }


@pytest.fixture
def mock_request(mock_config):
    request = MagicMock()
    request.app.state.config = mock_config
    request.app.state.embedding_client = MagicMock()
    request.app.state.embedding_client.embed = AsyncMock(return_value=[0.1] * 768)
    return request


@pytest.mark.asyncio
async def test_match_procedures_token_overlap(mock_pool):
    procs = [
        _proc("read or write Google Sheets, SharePoint Excel, spreadsheet"),
        _proc("ssh into server, run sudo command, copy file via scp"),
    ]
    mock_pool.fetch = AsyncMock(return_value=procs)

    sheets = await procedures_db.match_procedures(
        "p", "can you read the APPT sheet and add a row", pool=mock_pool
    )
    assert len(sheets) == 1
    assert "Sheets" in sheets[0]["task_pattern"]
    assert sheets[0]["match_score"] >= 0.2

    ssh = await procedures_db.match_procedures(
        "p", "ssh into the dev server and restart with sudo", pool=mock_pool
    )
    assert len(ssh) == 1
    assert "ssh" in ssh[0]["task_pattern"]

    none = await procedures_db.match_procedures(
        "p", "what is the time complexity of quicksort", pool=mock_pool
    )
    assert none == []


@pytest.mark.asyncio
async def test_smart_context_includes_matched_procedures(mock_request, mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[_proc("read or write Google Sheets")])

    with patch.object(
        context_router.pb_db, "dedup_context_entries", new=AsyncMock(return_value=[])
    ):
        body = SmartContextRequest(project="p", conversation="please read my google sheet")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert len(result["procedures"]) == 1
    assert "Sheets" in result["procedures"][0]["task_pattern"]


@pytest.mark.asyncio
async def test_smart_context_falls_back_to_trigram(mock_request, mock_pool):
    # match_procedures finds nothing (list empty), trigram finds one
    proc = {**_proc("deploy app"), "sim": 0.85}
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="SET")
    conn.fetch = AsyncMock(return_value=[proc])
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.fetch = AsyncMock(return_value=[])

    with patch.object(
        context_router.pb_db, "dedup_context_entries", new=AsyncMock(return_value=[])
    ):
        body = SmartContextRequest(project="p", conversation="deploy app")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert len(result["procedures"]) == 1
    assert result["procedures"][0]["task_pattern"] == "deploy app"


@pytest.mark.asyncio
async def test_smart_context_no_procedures_for_unrelated_conversation(mock_request, mock_pool):
    mock_pool.fetch = AsyncMock(return_value=[_proc("read or write Google Sheets")])
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="SET")
    conn.fetch = AsyncMock(return_value=[])
    conn.transaction = MagicMock()
    conn.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
    conn.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=None)

    with patch.object(
        context_router.pb_db, "dedup_context_entries", new=AsyncMock(return_value=[])
    ):
        body = SmartContextRequest(project="p", conversation="unrelated topic xyz")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert result["procedures"] == []


@pytest.mark.asyncio
async def test_smart_context_no_procedures_on_search_failure(mock_request, mock_pool):
    mock_pool.fetch = AsyncMock(side_effect=RuntimeError("DB down"))

    with patch.object(
        context_router.pb_db, "dedup_context_entries", new=AsyncMock(return_value=[])
    ):
        body = SmartContextRequest(project="p", conversation="read google sheets")
        result = await context_router.get_smart_context(body, mock_request, mock_pool)

    assert result["procedures"] == []
    assert result["source"] == "smart_dedup"


@pytest.mark.asyncio
async def test_vector_layer_respects_floor(mock_pool):
    proc = _proc("use browser automation, CDP, session manager, xvfb")
    # Vector hit above floor -> included
    mock_pool.fetch = AsyncMock(return_value=[{**proc, "similarity": 0.62}])
    hits = await context_router._match_procedures(
        "p", "unrelated phrasing with no token overlap zzz", [0.1] * 768, pool=mock_pool
    )
    assert len(hits) == 1
    assert hits[0]["match_source"] == "vector"

    # Vector hit below floor -> excluded
    mock_pool.fetch = AsyncMock(return_value=[{**proc, "similarity": 0.40}])
    hits = await context_router._match_procedures(
        "p", "unrelated phrasing with no token overlap zzz", [0.1] * 768, pool=mock_pool
    )
    assert hits == []


@pytest.mark.asyncio
async def test_token_beats_vector_order(mock_pool):
    sheets = _proc("read or write Google Sheets, SharePoint Excel")
    browser = _proc("use browser automation, CDP, session manager, xvfb")
    browser["id"] = 2
    mock_pool.fetch = AsyncMock(
        side_effect=[
            [sheets, browser],  # list_procedures (token layer)
            [{**browser, "similarity": 0.62}],  # vector_search_procedures
        ]
    )
    hits = await context_router._match_procedures(
        "p", "read my google sheets please", [0.1] * 768, pool=mock_pool
    )
    assert hits[0]["match_source"] == "token"
    assert hits[1]["match_source"] == "vector"
