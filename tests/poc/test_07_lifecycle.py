"""Test 07: Multi-session lifecycle — add → inject → consolidate → decay."""

from __future__ import annotations

import time

PNEURAL_URL = "http://localhost:8779"
PROJECT = "poc-test"


def test_lifecycle_session1_add_memory(api, tel):
    r = api.post(
        "/api/memory",
        json={
            "project": PROJECT,
            "text": "Lifecycle test: the deployment server runs at 10.42.0.89 port 8779",
            "priority": "important",
            "memory_type": "concept",
        },
    )
    assert r.status_code == 200
    entry_id = r.json()["id"]
    tel.record("test_07_lifecycle", "session1_memory_id", entry_id)
    tel.record("test_07_lifecycle", "session1_add_ok", True)


def test_lifecycle_session1_verify_injection(api, tel):
    time.sleep(1)
    r = api.get("/api/context", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    md = data.get("markdown", "")
    tel.record("test_07_lifecycle", "session1_context_entries", data.get("entries", 0))
    tel.record(
        "test_07_lifecycle", "session1_has_deployment", "deployment" in md.lower() or "8779" in md
    )


def test_lifecycle_session2_add_more(api, tel):
    r = api.post(
        "/api/memory",
        json={
            "project": PROJECT,
            "text": "Lifecycle test: PostgreSQL database runs on port 5432 with asyncpg driver",
            "priority": "normal",
            "memory_type": "concept",
        },
    )
    assert r.status_code == 200
    tel.record("test_07_lifecycle", "session2_add_ok", True)
    time.sleep(1)


def test_lifecycle_session2_verify_both(api, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    md = data.get("markdown", "").lower()
    has_deployment = "deployment" in md or "8779" in md
    has_postgres = "postgresql" in md or "5432" in md or "asyncpg" in md
    tel.record("test_07_lifecycle", "session2_both_visible", has_deployment and has_postgres)


def test_lifecycle_consolidate(api, tel):
    import httpx

    with httpx.Client(base_url=PNEURAL_URL, timeout=120.0) as long_client:
        r = long_client.post("/api/consolidation", json={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    tel.record(
        "test_07_lifecycle",
        "consolidation_result",
        data.get("ok") or data.get("immediate_created") is not None,
    )
    time.sleep(1)


def test_lifecycle_session3_verify_consolidated(api, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    tel.record("test_07_lifecycle", "session3_context_entries", data.get("entries", 0))
    tel.record(
        "test_07_lifecycle", "session3_consolidated_entries", data.get("consolidated_entries", 0)
    )


def test_lifecycle_decay(api, tel):
    r = api.post("/api/decay")
    assert r.status_code == 200
    data = r.json()
    tel.record("test_07_lifecycle", "decay_result", data)

    full = api.get("/api/memory/full", params={"project": PROJECT}).json()
    red_entries = [e for e in full if e.get("priority") == "critical"]
    tel.record("test_07_lifecycle", "red_ink_preserved_after_decay", len(red_entries))
    for e in red_entries:
        tel.record("test_07_lifecycle", f"red_entry_{e.get('id')}_strength", e.get("strength"))


def test_lifecycle_decay_status(api, tel):
    r = api.get("/api/decay/status", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    tel.record("test_07_lifecycle", "decay_status", data if isinstance(data, list) else "dict")


def test_lifecycle_cost_summary(api, tel):
    r = api.get("/api/costs/summary", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    tel.record("test_07_lifecycle", "cost_summary", data)
