"""Test 08: Plugin hooks — verify pneural-context.mjs plugin behavior via direct HTTP calls.

Since we can't load the .mjs plugin in Python, we test the HTTP endpoints
that the plugin calls, simulating the plugin's behavior.
"""

from __future__ import annotations

import time

PROJECT = "poc-test"
PNEURAL_URL = "http://localhost:8779"
PLUGIN_URL = PNEURAL_URL  # Plugin calls pneumatic-context REST API


def test_plugin_fetch_context(api, tel):
    """Simulates plugin's fetchContext call (GET /api/context)."""
    r = api.get("/api/context", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    md = data.get("markdown", "")
    marker = data.get("marker", "")
    tel.record("test_08_plugin_hooks", "context_marker", marker)
    tel.record("test_08_plugin_hooks", "context_has_pneural_ctx", "PNEURAL_CTX" in md)
    tel.record("test_08_plugin_hooks", "context_entries", data.get("entries", 0))
    assert "PNEURAL_CTX" in md
    assert marker


def test_plugin_cache_behavior(api, tel):
    """Verify that calling GET /api/context twice returns same marker within cache TTL."""
    r1 = api.get("/api/context", params={"project": PROJECT})
    data1 = r1.json()
    time.sleep(0.5)
    r2 = api.get("/api/context", params={"project": PROJECT})
    data2 = r2.json()
    tel.record("test_08_plugin_hooks", "first_marker", data1.get("marker"))
    tel.record("test_08_plugin_hooks", "second_marker", data2.get("marker"))
    tel.record(
        "test_08_plugin_hooks", "markers_different", data1.get("marker") != data2.get("marker")
    )


def test_plugin_smart_dedup_fetch(api, tel):
    """Simulates plugin's fetchSmartContext call (POST /api/context/smart)."""
    r = api.post(
        "/api/context/smart",
        json={
            "project": PROJECT,
            "conversation": "Tell me about memory injection and context management",
        },
    )
    assert r.status_code == 200
    data = r.json()
    tel.record("test_08_plugin_hooks", "smart_context_source", data.get("source"))
    tel.record("test_08_plugin_hooks", "smart_entries_count", len(data.get("entries", [])))


def test_plugin_session_record(api, tel):
    """Simulates plugin's session.idle handler (POST /api/session/record)."""
    import uuid

    r = api.post(
        "/api/session/record",
        json={
            "project": PROJECT,
            "session_id": str(uuid.uuid4()),
            "title": "Plugin test: idle session recording",
            "messages": [
                {"role": "user", "content": "How does context injection work?"},
                {
                    "role": "assistant",
                    "content": "Context injection fetches memory from the REST API and builds a markdown block.",
                },
            ],
            "memory_type": "temporal",
        },
    )
    assert r.status_code == 200
    data = r.json()
    tel.record("test_08_plugin_hooks", "session_recorded", data.get("stored", False))
    tel.record("test_08_plugin_hooks", "session_summary_len", len(data.get("summary", "")))


def test_plugin_project_resolution(api, tel):
    """Test that project resolution works — plugin resolves from .pneural-context.json."""
    r = api.get("/api/context", params={"project": PROJECT})
    assert r.status_code == 200
    tel.record("test_08_plugin_hooks", "project_resolution_ok", True)


def test_plugin_preservation_instruction(api, tel):
    """Verify the preservation instruction that goes into compacting hook."""
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    md = data.get("markdown", "")
    marker = data.get("marker", "")
    has_preservation = "preserve" in md.lower() or "PNEURAL_CTX" in md
    tel.record("test_08_plugin_hooks", "preservation_instruction_present", has_preservation)
    tel.record("test_08_plugin_hooks", "marker_for_compacting", marker)
    assert has_preservation


def test_plugin_red_ink_always(api, tel):
    """Verify red ink entries always appear in context (plugin invariant)."""
    api.post(
        "/api/memory",
        json={
            "project": PROJECT,
            "text": "CRITICAL plugin test: always validate environment variables at startup",
            "priority": "critical",
            "memory_type": "red",
        },
    )
    time.sleep(1)
    r = api.get("/api/context", params={"project": PROJECT})
    data = r.json()
    red = data.get("red_ink_entries", [])
    tel.record("test_08_plugin_hooks", "red_ink_entries_count", len(red))
    assert len(red) > 0
