"""Test 04: Session recording — real session triggers idle recording."""

from __future__ import annotations

import time
import uuid

import pytest
from helpers import oc_create_session, oc_send_message

PROJECT = "poc-test"


def test_record_session_via_api(api, tel):
    session_id = str(uuid.uuid4())
    messages = [
        {"role": "user", "content": "How does pneural-context handle memory injection?"},
        {
            "role": "assistant",
            "content": "Pneural-context injects context via the system transform hook, fetching entries from the REST API and building a markdown block with a PNEURAL_CTX marker.",
        },
        {"role": "user", "content": "What about deduplication?"},
        {
            "role": "assistant",
            "content": "Smart dedup uses cosine similarity between conversation embeddings and memory embeddings, with high/low threshold zones to decide which entries to inject.",
        },
    ]
    r = api.post(
        "/api/session/record",
        json={
            "project": PROJECT,
            "session_id": session_id,
            "title": "PoC session recording test",
            "messages": messages,
            "memory_type": "temporal",
        },
    )
    assert r.status_code == 200
    data = r.json()
    tel.record("test_04_session_recording", "session_recorded", data.get("stored", False))
    tel.record("test_04_session_recording", "entry_id", data.get("id"))
    tel.record("test_04_session_recording", "summary_length", len(data.get("summary", "")))
    assert data.get("stored") is True
    return data


def test_summary_is_llm_generated(api, tel):
    record_r = test_record_session_via_api(api, tel)
    summary = record_r.get("summary", "")
    title_fallback = "PoC session recording test"
    is_llm = len(summary) > len(title_fallback) + 20
    tel.record("test_04_session_recording", "summary_is_llm_generated", is_llm)
    tel.record("test_04_session_recording", "summary_text", summary[:200])


def test_session_entry_in_memory(api, tel):
    full = api.get("/api/memory/full", params={"project": PROJECT}).json()
    session_entries = [e for e in full if e.get("memory_type") == "temporal"]
    tel.record("test_04_session_recording", "temporal_entries_count", len(session_entries))
    assert len(session_entries) > 0, "Expected at least one temporal (session) entry"


def test_opencode_session_recording(oc, api, tel):
    sid = oc_create_session(oc, title="poc-session-recording")
    if not sid:
        tel.record("test_04_session_recording", "opencode_session_created", False)
        pytest.skip("opencode serve not available")

    tel.record("test_04_session_recording", "opencode_session_created", True)

    for msg in ["Hello, I am testing session recording", "Can you tell me about memory injection?"]:
        result = oc_send_message(oc, sid, msg, poll_timeout=30, poll_interval=1.5)
        status = result.get("status_code", 0) if result else 0
        tel.record("test_04_session_recording", f"message_status_{msg[:20]}", status)

    time.sleep(3)
    full = api.get("/api/memory/full", params={"project": PROJECT}).json()
    tel.record("test_04_session_recording", "memory_count_after_session", len(full))
