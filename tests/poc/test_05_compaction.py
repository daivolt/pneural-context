"""Test 05: Compaction — verify PNEURAL_CTX marker survives session compaction."""

from __future__ import annotations

import time

import pytest
from helpers import oc_create_session, oc_send_message

PROJECT = "poc-test"


def test_context_has_marker(api, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    marker = data.get("marker", "")
    tel.record("test_05_compaction", "marker_in_context", bool(marker))
    assert marker, "PNEURAL_CTX marker must exist in context response"
    tel.record("test_05_compaction", "marker_value", marker)


def test_compaction_preservation_instruction(api, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    md = data.get("markdown", "")
    has_preservation = "PNEURAL_CTX" in md and "preserve" in md.lower()
    tel.record("test_05_compaction", "has_preservation_instruction", has_preservation)
    tel.record("test_05_compaction", "context_length", len(md))


def test_red_ink_survives_in_context(api, tel):
    full = api.get("/api/memory/full", params={"project": PROJECT}).json()
    red_entries = [e for e in full if e.get("priority") == "critical"]
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    md = data.get("markdown", "").lower()
    red_in_context = sum(
        1 for e in red_entries if e.get("entry", "").split(".")[0].lower()[:30] in md
    )
    tel.record("test_05_compaction", "red_ink_entries_total", len(red_entries))
    tel.record("test_05_compaction", "red_ink_in_context", red_in_context)
    assert red_in_context > 0, "At least one red ink entry must appear in context"


def test_long_session_compaction(oc, api, tel):
    sid = oc_create_session(oc, title="poc-compaction")
    if not sid:
        pytest.skip("opencode serve not available")
    tel.record("test_05_compaction", "session_id", sid)

    messages = [
        "Tell me about the pneural-context project architecture",
        "How does the consolidation system work?",
        "Explain the decay mechanism in memory management",
        "What are the different memory types supported?",
        "How does smart dedup work with cosine similarity?",
        "Describe the session recording and idle detection mechanism",
        "What is the purpose of red ink entries?",
        "How are procedures stored and searched?",
        "Explain the cost analysis and token tracking system",
        "What are the MCP server capabilities?",
    ]

    for i, msg in enumerate(messages):
        result = oc_send_message(oc, sid, msg, poll_timeout=30, poll_interval=1.5)
        status = result.get("status_code", 0) if result else 0
        tel.record("test_05_compaction", f"message_{i}_status", status)
        time.sleep(0.5)

    context_r = api.get("/api/context", params={"project": PROJECT})
    data = context_r.json()
    tel.record("test_05_compaction", "marker_after_long_session", bool(data.get("marker")))
    tel.record("test_05_compaction", "context_length_after", len(data.get("markdown", "")))
    tel.record("test_05_compaction", "messages_sent", len(messages))
