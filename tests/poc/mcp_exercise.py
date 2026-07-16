"""MCP exercise — tests all 29 MCP tools via the HTTP API (simulating MCP calls)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

PNEURAL_URL = "http://localhost:8779"
PROJECT = "poc-benchmark"


class MCPExercise:
    def __init__(self, base_url: str = PNEURAL_URL, project: str = PROJECT):
        self.base_url = base_url
        self.project = project
        self.client = httpx.Client(base_url=base_url, timeout=60)
        self.results: list[dict[str, Any]] = []
        self._proc_id: str | None = None

    def record(self, name: str, passed: bool, detail: str = "") -> None:
        self.results.append({"name": name, "passed": passed, "detail": detail})
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {detail[:80]}" if detail else f"  [{status}] {name}")

    def run_all(self) -> list[dict[str, Any]]:
        tools = [
            ("pb_add_memory", self._add_memory),
            ("pb_get_memory", self._get_memory),
            ("pb_get_full_memory", self._get_full_memory),
            ("pb_replace_memory", self._replace_memory),
            ("pb_get_context", self._get_context),
            ("pb_recall", self._recall),
            ("pb_get_red_ink", self._get_red_ink),
            ("pb_set_priority", self._set_priority),
            ("pb_touch_entry", self._touch_entry),
            ("pb_boost_entry", self._boost_entry),
            ("pb_briefing", self._briefing),
            ("pb_get_briefing_anchors", self._get_briefing_anchors),
            ("pb_list_procedures", self._list_procedures),
            ("pb_add_procedure", self._add_procedure),
            ("pb_search_procedures", self._search_procedures),
            ("pb_procedure_outcome", self._procedure_outcome),
            ("pb_retire_procedure", self._retire_procedure),
            ("pb_classify_memory", self._classify_memory),
            ("pb_set_type", self._set_type),
            ("pb_trigger_consolidation", self._trigger_consolidation),
            ("pb_get_consolidation", self._get_consolidation),
            ("pb_consolidation_status", self._consolidation_status),
            ("pb_get_anchors", self._get_anchors),
            ("pb_decay_status", self._decay_status),
            ("pb_search_archive", self._search_archive),
            ("pb_cost_analysis", self._cost_analysis),
            ("pb_cost_trends", self._cost_trends),
            ("pb_record_cost", self._record_cost),
            ("pb_help", self._help),
        ]
        for name, func in tools:
            try:
                func(name)
            except Exception as e:
                self.record(name, False, f"Exception: {e}")
            time.sleep(0.1)
        return self.results

    def _add_memory(self, name: str) -> None:
        r = self.client.post(
            "/api/memory",
            json={"project": self.project, "text": f"MCP test {name}", "priority": "normal"},
        )
        self.record(name, r.status_code == 200 and "id" in r.json(), f"status={r.status_code}")

    def _get_memory(self, name: str) -> None:
        r = self.client.get("/api/memory", params={"project": self.project})
        self.record(
            name,
            r.status_code == 200 and isinstance(r.json(), list),
            f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}",
        )

    def _get_full_memory(self, name: str) -> None:
        r = self.client.get("/api/memory/full", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _replace_memory(self, name: str) -> None:
        self.client.post(
            "/api/memory",
            json={"project": self.project, "text": "MCP replace before", "priority": "normal"},
        )
        r = self.client.post(
            "/api/memory/replace",
            json={"project": self.project, "old": "MCP replace before", "new": "MCP replace after"},
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _get_context(self, name: str) -> None:
        r = self.client.get("/api/context", params={"project": self.project})
        ok = r.status_code == 200 and "markdown" in r.json() and "marker" in r.json()
        self.record(
            name,
            ok,
            f"has_markdown={r.status_code == 200 and 'markdown' in r.json()}, has_marker={r.status_code == 200 and 'marker' in r.json()}",
        )

    def _recall(self, name: str) -> None:
        r = self.client.get("/api/recall", params={"q": "FastAPI", "project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _get_red_ink(self, name: str) -> None:
        r = self.client.get("/api/memory/red-ink", params={"project": self.project})
        self.record(
            name,
            r.status_code == 200,
            f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}",
        )

    def _set_priority(self, name: str) -> None:
        mem = self.client.get("/api/memory", params={"project": self.project})
        entries = mem.json() if mem.status_code == 200 else []
        idx = entries[0]["id"] if entries else 0
        r = self.client.patch(
            f"/api/memory/{idx}/priority", json={"project": self.project, "priority": "important"}
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _touch_entry(self, name: str) -> None:
        mem = self.client.get("/api/memory", params={"project": self.project})
        entries = mem.json() if mem.status_code == 200 else []
        idx = entries[0]["id"] if entries else 0
        r = self.client.post("/api/memory/touch", json={"project": self.project, "index": idx})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _boost_entry(self, name: str) -> None:
        mem = self.client.get("/api/memory", params={"project": self.project})
        entries = mem.json() if mem.status_code == 200 else []
        idx = entries[0]["id"] if entries else 0
        r = self.client.post("/api/memory/boost", json={"project": self.project, "index": idx})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _briefing(self, name: str) -> None:
        r = self.client.get(
            "/api/briefing",
            params={"project": self.project, "task_description": "Build FastAPI app"},
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _get_briefing_anchors(self, name: str) -> None:
        r = self.client.get("/api/anchors", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _list_procedures(self, name: str) -> None:
        r = self.client.get("/api/procedures", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _add_procedure(self, name: str) -> None:
        r = self.client.post(
            "/api/procedures",
            json={
                "project": self.project,
                "task_pattern": "MCP test procedure",
                "steps": ["Step 1", "Step 2", "Step 3"],
                "task_type": "test",
            },
        )
        ok = r.status_code == 200
        if ok:
            self._proc_id = r.json().get("id")
        self.record(name, ok, f"status={r.status_code}")

    def _search_procedures(self, name: str) -> None:
        r = self.client.get(
            "/api/procedures/search", params={"project": self.project, "query": "test"}
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _procedure_outcome(self, name: str) -> None:
        if not self._proc_id:
            self.record(name, False, "no proc_id")
            return
        r = self.client.post(
            f"/api/procedures/{self._proc_id}/outcome",
            json={"project": self.project, "outcome": "success"},
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _retire_procedure(self, name: str) -> None:
        if not self._proc_id:
            self.record(name, False, "no proc_id")
            return
        r = self.client.post(
            f"/api/procedures/{self._proc_id}/retire", json={"project": self.project}
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _classify_memory(self, name: str) -> None:
        r = self.client.post("/api/memory/classify", json={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _set_type(self, name: str) -> None:
        mem = self.client.get("/api/memory", params={"project": self.project})
        entries = mem.json() if mem.status_code == 200 else []
        idx = entries[0]["id"] if entries else 0
        r = self.client.patch(
            f"/api/memory/{idx}/type", json={"project": self.project, "memory_type": "concept"}
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _trigger_consolidation(self, name: str) -> None:
        r = self.client.post("/api/consolidation", json={"project": self.project})
        time.sleep(2)
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _get_consolidation(self, name: str) -> None:
        r = self.client.get("/api/consolidation", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _consolidation_status(self, name: str) -> None:
        r = self.client.get("/api/consolidation/status", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _get_anchors(self, name: str) -> None:
        r = self.client.get("/api/anchors", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _decay_status(self, name: str) -> None:
        r = self.client.get("/api/decay/status", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _search_archive(self, name: str) -> None:
        r = self.client.get("/api/archive/search", params={"project": self.project, "q": "test"})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _cost_analysis(self, name: str) -> None:
        r = self.client.get("/api/costs", params={"project": self.project})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _cost_trends(self, name: str) -> None:
        r = self.client.get("/api/costs/trends", params={"project": self.project, "days": 7})
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _record_cost(self, name: str) -> None:
        r = self.client.post(
            "/api/costs",
            json={
                "project": self.project,
                "session_id": "mcp-test",
                "tokens_injected": 300,
                "tokens_saved_injection": 100,
                "tokens_saved_forgetting": 50,
                "context_type": "briefing",
                "task_outcome": "success",
            },
        )
        self.record(name, r.status_code == 200, f"status={r.status_code}")

    def _help(self, name: str) -> None:
        r = self.client.get("/health")
        self.record(
            name, r.status_code == 200, f"status={r.status_code} (health check as help proxy)"
        )

    def close(self) -> None:
        self.client.close()

    def summary(self) -> dict[str, Any]:
        passed = sum(1 for r in self.results if r["passed"])
        failed = sum(1 for r in self.results if not r["passed"])
        return {
            "total": len(self.results),
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / len(self.results), 3) if self.results else 0,
            "results": self.results,
        }


if __name__ == "__main__":
    exercise = MCPExercise()
    try:
        exercise.run_all()
    finally:
        exercise.close()
    summary = exercise.summary()
    print(json.dumps(summary, indent=2))
