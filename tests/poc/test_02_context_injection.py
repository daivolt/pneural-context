"""Test 02: Context injection via real opencode session."""

from __future__ import annotations

import time

import pytest
from helpers import oc_create_session, oc_send_message

PROJECT = "poc-test"

SEED_ENTRIES = [
    {
        "text": "The deployment server is at 10.42.0.89 running pneural-context on port 8779",
        "priority": "important",
        "memory_type": "concept",
    },
    {
        "text": "Always use environment variables for secrets, never hardcode credentials",
        "priority": "critical",
        "memory_type": "red",
    },
    {
        "text": "The project uses FastAPI with asyncpg for PostgreSQL access",
        "priority": "normal",
        "memory_type": "concept",
    },
    {
        "text": "Smart dedup uses cosine similarity with high/low thresholds",
        "priority": "normal",
        "memory_type": "procedural",
    },
    {
        "text": "Test entry for context injection verification",
        "priority": "normal",
        "memory_type": "temporal",
    },
]


@pytest.fixture(scope="module")
def seeded_ids(api):
    ids = []
    for entry in SEED_ENTRIES:
        r = api.post("/api/memory", json={"project": PROJECT, **entry})
        assert r.status_code == 200
        data = r.json()
        ids.append(data["id"])
    time.sleep(1)
    yield ids


def test_seed_entries(seeded_ids, tel):
    tel.record("test_02_context_injection", "memory_entries_seeded", len(seeded_ids))
    assert len(seeded_ids) == 5


def test_get_context(api, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    tel.record("test_02_context_injection", "context_entries_returned", data.get("entries", 0))
    tel.record(
        "test_02_context_injection", "marker_in_response", "PNEURAL_CTX" in data.get("markdown", "")
    )
    assert "PNEURAL_CTX" in data["markdown"]
    assert "deployment server" in data["markdown"].lower()


def test_last_accessed_updated(api, seeded_ids, tel):
    full = api.get("/api/memory/full", params={"project": PROJECT}).json()
    now = time.time()
    accessed_count = 0
    for e in full:
        if e.get("id") in seeded_ids:
            la = e.get("last_accessed")
            if la:
                ts = la if isinstance(la, int | float) else None
                if ts and (now - ts) < 60:
                    accessed_count += 1
    tel.record("test_02_context_injection", "last_accessed_updated", accessed_count > 0)


def test_red_ink_in_context(api, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    red = data.get("red_ink_entries", [])
    tel.record("test_02_context_injection", "red_ink_entries", len(red))
    assert any("secrets" in e.lower() or "credentials" in e.lower() for e in red)


def test_opencode_session_injects_context(oc, api, tel):
    sid = oc_create_session(oc, title="poc-context-injection")
    if not sid:
        tel.record("test_02_context_injection", "opencode_session_created", False)
        pytest.skip("opencode serve did not return session id")
    tel.record("test_02_context_injection", "opencode_session_created", True)
    tel.record("test_02_context_injection", "session_id", sid)

    result = oc_send_message(oc, sid, "What context do you have about this project?")
    tel.record("test_02_context_injection", "message_sent", True)
    if result and result.get("text"):
        assistant_text = result["text"].lower()
        tel.record(
            "test_02_context_injection",
            "assistant_referenced_memory",
            any(
                kw in assistant_text
                for kw in ["deployment", "server", "8779", "fastapi", "context", "dedup"]
            ),
        )
        tel.record("test_02_context_injection", "assistant_response_length", len(result["text"]))
    else:
        tel.record("test_02_context_injection", "assistant_referenced_memory", False)
        tel.record("test_02_context_injection", "assistant_response_length", 0)
