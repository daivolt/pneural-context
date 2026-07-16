"""Test 09: Cost analysis — record costs, verify summary/trends/effectiveness."""

from __future__ import annotations

import uuid

PROJECT = "poc-test"


def test_record_costs_full(api, tel):
    session_id = str(uuid.uuid4())
    r = api.post(
        "/api/costs",
        json={
            "project": PROJECT,
            "session_id": session_id,
            "tokens_injected": 1500,
            "tokens_saved_injection": 400,
            "tokens_saved_forgetting": 200,
            "context_type": "full",
            "task_outcome": "success",
        },
    )
    assert r.status_code == 200
    tel.record("test_09_cost_analysis", "full_cost_recorded", r.json().get("ok", False))


def test_record_costs_smart_dedup(api, tel):
    session_id = str(uuid.uuid4())
    r = api.post(
        "/api/costs",
        json={
            "project": PROJECT,
            "session_id": session_id,
            "tokens_injected": 800,
            "tokens_saved_injection": 600,
            "tokens_saved_forgetting": 150,
            "context_type": "smart_dedup",
            "task_outcome": "success",
        },
    )
    assert r.status_code == 200
    tel.record("test_09_cost_analysis", "smart_dedup_cost_recorded", r.json().get("ok", False))


def test_record_costs_briefing(api, tel):
    session_id = str(uuid.uuid4())
    r = api.post(
        "/api/costs",
        json={
            "project": PROJECT,
            "session_id": session_id,
            "tokens_injected": 300,
            "tokens_saved_injection": 900,
            "tokens_saved_forgetting": 100,
            "context_type": "briefing",
            "task_outcome": "partial",
        },
    )
    assert r.status_code == 200
    tel.record("test_09_cost_analysis", "briefing_cost_recorded", r.json().get("ok", False))


def test_cost_summary(api, tel):
    r = api.get("/api/costs/summary", params={"project": PROJECT})
    assert r.status_code == 200
    data = r.json()
    tel.record("test_09_cost_analysis", "summary_total_injected", data.get("total_injected"))
    tel.record(
        "test_09_cost_analysis", "summary_total_saved_injection", data.get("total_saved_injection")
    )
    tel.record(
        "test_09_cost_analysis",
        "summary_total_saved_forgetting",
        data.get("total_saved_forgetting"),
    )
    tel.record("test_09_cost_analysis", "summary_sessions", data.get("total_sessions"))
    tel.record(
        "test_09_cost_analysis", "summary_effectiveness_ratio", data.get("effectiveness_ratio")
    )


def test_cost_trends(api, tel):
    r = api.get("/api/costs/trends", params={"project": PROJECT, "days": 30})
    assert r.status_code == 200
    data = r.json()
    tel.record("test_09_cost_analysis", "trends_records", data.get("records"))
    tel.record("test_09_cost_analysis", "trends_days", data.get("days"))


def test_cost_list(api, tel):
    r = api.get("/api/costs", params={"project": PROJECT, "days": 30})
    assert r.status_code == 200
    costs = r.json()
    tel.record(
        "test_09_cost_analysis", "cost_records_count", len(costs) if isinstance(costs, list) else 0
    )
    if isinstance(costs, list) and len(costs) > 0:
        first = costs[0]
        tel.record("test_09_cost_analysis", "first_cost_context_type", first.get("context_type"))
        tel.record(
            "test_09_cost_analysis", "first_cost_tokens_injected", first.get("tokens_injected")
        )


def test_cost_with_breakdown(api, tel):
    session_id = str(uuid.uuid4())
    r = api.post(
        "/api/costs",
        json={
            "project": PROJECT,
            "session_id": session_id,
            "tokens_injected": 1200,
            "tokens_saved_injection": 500,
            "tokens_saved_forgetting": 300,
            "context_type": "full",
            "task_outcome": "success",
            "breakdown": {
                "red_ink_tokens": 200,
                "concept_tokens": 400,
                "procedural_tokens": 300,
                "temporal_tokens": 300,
            },
        },
    )
    assert r.status_code == 200
    tel.record("test_09_cost_analysis", "breakdown_cost_recorded", r.json().get("ok", False))

    r2 = api.get("/api/costs", params={"project": PROJECT, "days": 30})
    costs = r2.json()
    breakdown_entries = [c for c in costs if isinstance(c, dict) and c.get("breakdown")]
    tel.record("test_09_cost_analysis", "breakdown_entries_found", len(breakdown_entries))
