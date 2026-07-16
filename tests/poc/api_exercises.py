"""API exercises — 36 exercises covering all pneural-context API endpoints and features."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

PNEURAL_URL = "http://localhost:8779"
PROJECT = "poc-benchmark"


class APIExercises:
    def __init__(self, base_url: str = PNEURAL_URL, project: str = PROJECT):
        self.base_url = base_url
        self.project = project
        self.client = httpx.Client(base_url=base_url, timeout=120)
        self.results: list[dict[str, Any]] = []
        self.created_ids: list[str] = []
        self._proc_id: str | None = None

    def record(self, name: str, passed: bool, detail: str = "", **extra: Any) -> None:
        entry = {"name": name, "passed": passed, "detail": detail, **extra}
        self.results.append(entry)
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}: {detail[:80]}" if detail else f"  [{status}] {name}")

    def run_all(self) -> list[dict[str, Any]]:
        exercises = [
            self.ex_01_health,
            self.ex_02_add_memory,
            self.ex_03_add_memory_all_priorities,
            self.ex_04_add_memory_all_types,
            self.ex_05_get_memory,
            self.ex_06_get_full_memory,
            self.ex_07_get_red_ink,
            self.ex_08_get_memory_by_type,
            self.ex_09_set_priority,
            self.ex_10_set_type,
            self.ex_11_touch_entry,
            self.ex_12_boost_entry,
            self.ex_13_replace_memory,
            self.ex_14_classify_memory,
            self.ex_15_delete_memory,
            self.ex_16_get_context,
            self.ex_17_smart_context,
            self.ex_18_context_has_marker,
            self.ex_19_recall,
            self.ex_20_add_procedure,
            self.ex_21_list_procedures,
            self.ex_22_search_procedures,
            self.ex_23_procedure_outcome,
            self.ex_24_retire_procedure,
            self.ex_25_briefing,
            self.ex_26_get_anchors,
            self.ex_27_consolidation_trigger,
            self.ex_28_consolidation_status,
            self.ex_29_consolidation_get,
            self.ex_30_decay_status,
            self.ex_31_decay_cycle,
            self.ex_32_archive_search,
            self.ex_33_cost_record,
            self.ex_34_cost_analysis,
            self.ex_35_cost_trends,
            self.ex_36_session_record,
        ]
        for ex in exercises:
            try:
                ex()
            except Exception as e:
                self.record(ex.__name__, False, f"Exception: {e}")
            time.sleep(0.1)
        return self.results

    def ex_01_health(self) -> None:
        r = self.client.get("/health")
        self.record("01_health", r.status_code == 200, f"status={r.status_code}")

    def ex_02_add_memory(self) -> None:
        r = self.client.post(
            "/api/memory",
            json={"project": self.project, "text": "API exercise test entry", "priority": "normal"},
        )
        ok = r.status_code == 200 and "id" in r.json()
        self.record("02_add_memory", ok, f"status={r.status_code}")
        if ok:
            self.created_ids.append(r.json()["id"])

    def ex_03_add_memory_all_priorities(self) -> None:
        all_ok = True
        for prio in ["critical", "important", "normal"]:
            r = self.client.post(
                "/api/memory",
                json={"project": self.project, "text": f"Priority test: {prio}", "priority": prio},
            )
            if r.status_code == 200 and "id" in r.json():
                self.created_ids.append(r.json()["id"])
            else:
                all_ok = False
        self.record("03_add_all_priorities", all_ok, "added critical, important, normal")

    def ex_04_add_memory_all_types(self) -> None:
        all_ok = True
        for mtype in ["red", "concept", "procedural", "temporal", "relation"]:
            r = self.client.post(
                "/api/memory",
                json={
                    "project": self.project,
                    "text": f"Type test: {mtype}",
                    "priority": "normal",
                    "memory_type": mtype,
                },
            )
            if r.status_code == 200 and "id" in r.json():
                self.created_ids.append(r.json()["id"])
            else:
                all_ok = False
        self.record(
            "04_add_all_types", all_ok, "added red, concept, procedural, temporal, relation"
        )

    def ex_05_get_memory(self) -> None:
        r = self.client.get("/api/memory", params={"project": self.project})
        ok = r.status_code == 200 and isinstance(r.json(), list) and len(r.json()) > 0
        self.record(
            "05_get_memory",
            ok,
            f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}",
        )

    def ex_06_get_full_memory(self) -> None:
        r = self.client.get("/api/memory/full", params={"project": self.project})
        ok = r.status_code == 200 and isinstance(r.json(), list)
        self.record("06_get_full_memory", ok, f"status={r.status_code}")

    def ex_07_get_red_ink(self) -> None:
        r = self.client.get("/api/memory/red-ink", params={"project": self.project})
        ok = r.status_code == 200 and isinstance(r.json(), list)
        self.record(
            "07_get_red_ink",
            ok,
            f"status={r.status_code}, count={len(r.json()) if r.status_code == 200 else 0}",
        )

    def ex_08_get_memory_by_type(self) -> None:
        for mtype in ["concept", "procedural", "temporal", "relation"]:
            r = self.client.get(f"/api/memory/type/{mtype}", params={"project": self.project})
            if r.status_code != 200:
                self.record("08_get_by_type", False, f"type={mtype} status={r.status_code}")
                return
        self.record("08_get_by_type", True, "all 4 types returned 200")

    def ex_09_set_priority(self) -> None:
        r = self.client.post(
            "/api/memory",
            json={"project": self.project, "text": "Priority change test", "priority": "normal"},
        )
        if r.status_code != 200:
            self.record("09_set_priority", False, f"create failed: {r.status_code}")
            return
        entry_id = r.json().get("id")
        r2 = self.client.patch(
            f"/api/memory/{entry_id}/priority",
            json={"project": self.project, "priority": "critical"},
        )
        self.record("09_set_priority", r2.status_code == 200, f"status={r2.status_code}")

    def ex_10_set_type(self) -> None:
        r = self.client.post(
            "/api/memory",
            json={
                "project": self.project,
                "text": "Type change test",
                "priority": "normal",
                "memory_type": "temporal",
            },
        )
        if r.status_code != 200:
            self.record("10_set_type", False, f"create failed: {r.status_code}")
            return
        entry_id = r.json().get("id")
        r2 = self.client.patch(
            f"/api/memory/{entry_id}/type", json={"project": self.project, "memory_type": "concept"}
        )
        self.record("10_set_type", r2.status_code == 200, f"status={r2.status_code}")

    def ex_11_touch_entry(self) -> None:
        mem = self.client.get("/api/memory", params={"project": self.project})
        entries = mem.json() if mem.status_code == 200 else []
        idx = entries[0]["id"] if entries else 0
        r = self.client.post("/api/memory/touch", json={"project": self.project, "index": idx})
        self.record("11_touch_entry", r.status_code == 200, f"status={r.status_code}")

    def ex_12_boost_entry(self) -> None:
        mem = self.client.get("/api/memory", params={"project": self.project})
        entries = mem.json() if mem.status_code == 200 else []
        idx = entries[0]["id"] if entries else 0
        r = self.client.post("/api/memory/boost", json={"project": self.project, "index": idx})
        self.record("12_boost_entry", r.status_code == 200, f"status={r.status_code}")

    def ex_13_replace_memory(self) -> None:
        r = self.client.post(
            "/api/memory",
            json={
                "project": self.project,
                "text": "Original text for replace test",
                "priority": "normal",
            },
        )
        if r.status_code != 200:
            self.record("13_replace_memory", False, f"create failed: {r.status_code}")
            return
        r2 = self.client.post(
            "/api/memory/replace",
            json={
                "project": self.project,
                "old": "Original text for replace test",
                "new": "Replaced text for replace test",
            },
        )
        self.record("13_replace_memory", r2.status_code == 200, f"status={r2.status_code}")

    def ex_14_classify_memory(self) -> None:
        r = self.client.post("/api/memory/classify", json={"project": self.project})
        self.record("14_classify_memory", r.status_code == 200, f"status={r.status_code}")

    def ex_15_delete_memory(self) -> None:
        r = self.client.post(
            "/api/memory", json={"project": self.project, "text": "Delete me", "priority": "normal"}
        )
        if r.status_code != 200:
            self.record("15_delete_memory", False, f"create failed: {r.status_code}")
            return
        eid = r.json().get("id")
        if not eid:
            self.record("15_delete_memory", False, "no id in response")
            return
        r2 = self.client.delete(f"/api/memory/{eid}", params={"project": self.project})
        self.record("15_delete_memory", r2.status_code == 200, f"status={r2.status_code}")

    def ex_16_get_context(self) -> None:
        r = self.client.get("/api/context", params={"project": self.project})
        ok = r.status_code == 200 and "markdown" in r.json()
        self.record(
            "16_get_context",
            ok,
            f"status={r.status_code}, has_markdown={r.status_code == 200 and 'markdown' in r.json()}",
        )

    def ex_17_smart_context(self) -> None:
        r = self.client.post(
            "/api/context/smart",
            json={
                "project": self.project,
                "conversation": "I need to add authentication to my FastAPI app",
            },
        )
        ok = r.status_code == 200 and "entries" in r.json()
        self.record(
            "17_smart_context",
            ok,
            f"status={r.status_code}, entries={len(r.json().get('entries', [])) if r.status_code == 200 else 0}",
        )

    def ex_18_context_has_marker(self) -> None:
        r = self.client.get("/api/context", params={"project": self.project})
        data = r.json()
        has_marker = "marker" in data and data["marker"]
        self.record("18_context_marker", has_marker, f"marker={data.get('marker', 'NONE')}")

    def ex_19_recall(self) -> None:
        r = self.client.get(
            "/api/recall", params={"q": "FastAPI asyncpg connection pool", "project": self.project}
        )
        ok = r.status_code == 200
        self.record("19_recall", ok, f"status={r.status_code}")

    def ex_20_add_procedure(self) -> None:
        r = self.client.post(
            "/api/procedures",
            json={
                "project": self.project,
                "task_pattern": "Add CRUD endpoint",
                "steps": [
                    "Create Pydantic models",
                    "Write router",
                    "Register in server.py",
                    "Add tests",
                ],
                "task_type": "development",
            },
        )
        ok = r.status_code == 200 and "id" in r.json()
        self.record("20_add_procedure", ok, f"status={r.status_code}")
        if ok:
            self._proc_id = r.json()["id"]

    def ex_21_list_procedures(self) -> None:
        r = self.client.get("/api/procedures", params={"project": self.project})
        ok = r.status_code == 200 and isinstance(r.json(), list)
        self.record("21_list_procedures", ok, f"status={r.status_code}")

    def ex_22_search_procedures(self) -> None:
        r = self.client.get(
            "/api/procedures/search", params={"project": self.project, "query": "add endpoint"}
        )
        ok = r.status_code == 200 and isinstance(r.json(), list)
        self.record("22_search_procedures", ok, f"status={r.status_code}")

    def ex_23_procedure_outcome(self) -> None:
        if not self._proc_id:
            self.record("23_procedure_outcome", False, "no proc_id from ex_20")
            return
        r = self.client.post(
            f"/api/procedures/{self._proc_id}/outcome",
            json={"project": self.project, "outcome": "success"},
        )
        self.record("23_procedure_outcome", r.status_code == 200, f"status={r.status_code}")

    def ex_24_retire_procedure(self) -> None:
        if not self._proc_id:
            self.record("24_retire_procedure", False, "no proc_id from ex_20")
            return
        r = self.client.post(
            f"/api/procedures/{self._proc_id}/retire", json={"project": self.project}
        )
        self.record("24_retire_procedure", r.status_code == 200, f"status={r.status_code}")

    def ex_25_briefing(self) -> None:
        r = self.client.get(
            "/api/briefing",
            params={
                "project": self.project,
                "task_description": "Build a task management API with FastAPI",
            },
        )
        ok = r.status_code == 200
        self.record("25_briefing", ok, f"status={r.status_code}")

    def ex_26_get_anchors(self) -> None:
        r = self.client.get("/api/anchors", params={"project": self.project})
        ok = r.status_code == 200
        self.record("26_anchors", ok, f"status={r.status_code}")

    def ex_27_consolidation_trigger(self) -> None:
        r = self.client.post("/api/consolidation", json={"project": self.project})
        time.sleep(2)
        self.record("27_consolidation_trigger", r.status_code == 200, f"status={r.status_code}")

    def ex_28_consolidation_status(self) -> None:
        r = self.client.get("/api/consolidation/status", params={"project": self.project})
        ok = r.status_code == 200
        self.record("28_consolidation_status", ok, f"status={r.status_code}")

    def ex_29_consolidation_get(self) -> None:
        for tier in ["immediate", "consolidated", "timeless"]:
            r = self.client.get(
                "/api/consolidation", params={"project": self.project, "tier": tier}
            )
            if r.status_code != 200:
                self.record("29_consolidation_get", False, f"tier={tier} status={r.status_code}")
                return
        self.record("29_consolidation_get", True, "all 3 tiers returned 200")

    def ex_30_decay_status(self) -> None:
        r = self.client.get("/api/decay/status", params={"project": self.project})
        ok = r.status_code == 200
        self.record("30_decay_status", ok, f"status={r.status_code}")

    def ex_31_decay_cycle(self) -> None:
        r = self.client.post("/api/decay", json={"project": self.project})
        ok = r.status_code == 200
        self.record("31_decay_cycle", ok, f"status={r.status_code}")

    def ex_32_archive_search(self) -> None:
        r = self.client.get("/api/archive/search", params={"project": self.project, "q": "test"})
        ok = r.status_code == 200
        self.record("32_archive_search", ok, f"status={r.status_code}")

    def ex_33_cost_record(self) -> None:
        r = self.client.post(
            "/api/costs",
            json={
                "project": self.project,
                "session_id": "poc-benchmark-session",
                "tokens_injected": 500,
                "tokens_saved_injection": 200,
                "tokens_saved_forgetting": 100,
                "context_type": "full",
                "task_outcome": "success",
            },
        )
        self.record("33_cost_record", r.status_code == 200, f"status={r.status_code}")

    def ex_34_cost_analysis(self) -> None:
        r = self.client.get("/api/costs", params={"project": self.project})
        ok = r.status_code == 200
        self.record("34_cost_analysis", ok, f"status={r.status_code}")

    def ex_35_cost_trends(self) -> None:
        r = self.client.get("/api/costs/trends", params={"project": self.project, "days": 7})
        ok = r.status_code == 200
        self.record("35_cost_trends", ok, f"status={r.status_code}")

    def ex_36_session_record(self) -> None:
        r = self.client.post(
            "/api/session/record",
            json={
                "project": self.project,
                "session_id": "poc-test-session-001",
                "title": "PoC Benchmark Test Session",
                "messages": [
                    {"role": "user", "content": "Hello, I need help with FastAPI"},
                    {
                        "role": "assistant",
                        "content": "Sure! I can help you build a FastAPI application.",
                    },
                ],
                "memory_type": "temporal",
            },
        )
        self.record("36_session_record", r.status_code == 200, f"status={r.status_code}")

    def cleanup(self) -> None:
        for eid in self.created_ids:
            try:
                self.client.delete(f"/api/memory/{eid}", params={"project": self.project})
            except Exception:
                pass

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
    exercises = APIExercises()
    try:
        exercises.run_all()
    finally:
        exercises.cleanup()
        exercises.close()
    summary = exercises.summary()
    print(json.dumps(summary, indent=2))
