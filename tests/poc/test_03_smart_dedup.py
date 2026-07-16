"""Test 03: Smart dedup — verify dedup zones with real embeddings."""

from __future__ import annotations

import time

import pytest

PROJECT = "poc-test"

DEDUP_ENTRIES = [
    {
        "text": "API testing uses pytest with httpx for async HTTP clients",
        "priority": "normal",
        "memory_type": "concept",
    },
    {
        "text": "API testing requires proper fixture setup and teardown",
        "priority": "normal",
        "memory_type": "procedural",
    },
    {
        "text": "API testing should cover both happy and error paths",
        "priority": "normal",
        "memory_type": "concept",
    },
    {
        "text": "PostgreSQL database runs on port 5432 with asyncpg driver",
        "priority": "normal",
        "memory_type": "concept",
    },
    {
        "text": "Firewall rules allow traffic on port 8779 from Tailscale range",
        "priority": "normal",
        "memory_type": "concept",
    },
    {
        "text": "Deployment to production uses systemd service unit",
        "priority": "normal",
        "memory_type": "procedural",
    },
    {
        "text": "CRITICAL: never drop production database tables without backup",
        "priority": "critical",
        "memory_type": "red",
    },
]


@pytest.fixture(scope="module")
def dedup_ids(api):
    ids = []
    for entry in DEDUP_ENTRIES:
        r = api.post("/api/memory", json={"project": PROJECT, **entry})
        assert r.status_code == 200
        ids.append(r.json()["id"])
    time.sleep(2)
    yield ids


def test_smart_dedup_matching_conversation(api, dedup_ids, tel):
    r = api.post(
        "/api/context/smart",
        json={
            "project": PROJECT,
            "conversation": "We need to set up API testing for the new endpoints",
        },
    )
    assert r.status_code == 200
    data = r.json()
    tel.record("test_03_smart_dedup", "dedup_source", data.get("source"))
    entries = data.get("entries", [])
    tel.record("test_03_smart_dedup", "smart_entries_count", len(entries))
    tel.record("test_03_smart_dedup", "dedup_threshold_high", data.get("dedup_threshold_high"))
    tel.record("test_03_smart_dedup", "dedup_threshold_low", data.get("dedup_threshold_low"))
    if data.get("source") == "smart_dedup":
        api_testing_count = sum(
            1
            for e in entries
            if "api" in e.get("entry", "").lower() or "testing" in e.get("entry", "").lower()
        )
        tel.record("test_03_smart_dedup", "api_testing_entries_in_smart", api_testing_count)
        assert len(entries) > 0, "Smart dedup returned empty entries"


def test_smart_dedup_unrelated_conversation(api, dedup_ids, tel):
    r = api.post(
        "/api/context/smart",
        json={
            "project": PROJECT,
            "conversation": "Tell me about quantum computing and entanglement",
        },
    )
    assert r.status_code == 200
    data = r.json()
    entries = data.get("entries", [])
    tel.record("test_03_smart_dedup", "unrelated_entries_count", len(entries))
    tel.record("test_03_smart_dedup", "unrelated_source", data.get("source"))


def test_red_ink_always_injected(api, dedup_ids, tel):
    r = api.post(
        "/api/context/smart",
        json={
            "project": PROJECT,
            "conversation": "Quantum physics lecture notes",
        },
    )
    assert r.status_code == 200
    data = r.json()
    entries = data.get("entries", [])
    red_in_entries = any(e.get("priority") == "critical" for e in entries)
    tel.record("test_03_smart_dedup", "red_ink_always_injected", red_in_entries)
    assert red_in_entries, "Red ink (critical) entries must always be injected"


def test_full_context_includes_all(api, dedup_ids, tel):
    r = api.get("/api/context", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    tel.record("test_03_smart_dedup", "full_context_entries", data.get("entries", 0))
    assert data.get("entries", 0) >= len(DEDUP_ENTRIES)
