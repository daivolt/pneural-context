"""PoC Telemetry — metrics collection, JSON export, and cross-run comparison."""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPORTS_DIR = Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


class Telemetry:
    """Collects metrics from all PoC tests and exports a JSON report."""

    def __init__(self) -> None:
        self.run_id = f"poc_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
        self.start_time = time.monotonic()
        self.environment: dict[str, Any] = {
            "pneural_url": os.environ.get("PNEURAL_POC_URL", "http://localhost:8779"),
            "opencode_url": os.environ.get("OPENCODE_URL", "http://localhost:4096"),
            "llm_model": "qwen2.5-coder-7b-instruct-q4_k_m.gguf",
            "embed_model": "nomic-embed-text",
            "opencode_version": "1.14.24",
            "project": os.environ.get("PNEURAL_POC_PROJECT", "poc-test"),
        }
        self.tests: dict[str, dict[str, Any]] = {}

    def record(self, test_name: str, key: str, value: Any) -> None:
        if test_name not in self.tests:
            self.tests[test_name] = {"start_time": time.monotonic()}
        self.tests[test_name][key] = value

    def finish_test(self, test_name: str, passed: bool) -> None:
        if test_name not in self.tests:
            self.tests[test_name] = {}
        self.tests[test_name]["pass"] = passed
        self.tests[test_name]["duration_seconds"] = round(
            time.monotonic() - self.tests[test_name].get("start_time", time.monotonic()), 2
        )

    def export(self) -> dict[str, Any]:
        total_duration = round(time.monotonic() - self.start_time, 2)
        passed = sum(1 for t in self.tests.values() if t.get("pass"))
        failed = sum(1 for t in self.tests.values() if not t.get("pass"))
        total_tokens_injected = sum(t.get("tokens_injected", 0) for t in self.tests.values())
        total_tokens_saved = sum(t.get("tokens_saved", 0) for t in self.tests.values())

        report = {
            "run_id": self.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "environment": self.environment,
            "tests": self.tests,
            "summary": {
                "total_tests": len(self.tests),
                "passed": passed,
                "failed": failed,
                "total_duration_seconds": total_duration,
                "total_tokens_injected": total_tokens_injected,
                "total_tokens_saved": total_tokens_saved,
            },
        }

        report_path = REPORTS_DIR / f"{self.run_id}.json"
        report_path.write_text(json.dumps(report, indent=2, default=str))
        return report


def compare_runs(report_a: str | Path, report_b: str | Path) -> dict[str, Any]:
    """Compare two telemetry reports and return a diff of metrics."""
    a = json.loads(Path(report_a).read_text())
    b = json.loads(Path(report_b).read_text())

    diff: dict[str, Any] = {
        "run_a": a["run_id"],
        "run_b": b["run_id"],
        "tests": {},
    }

    all_test_names = set(a.get("tests", {})) | set(b.get("tests", {}))
    for name in sorted(all_test_names):
        ta = a.get("tests", {}).get(name, {})
        tb = b.get("tests", {}).get(name, {})
        test_diff: dict[str, Any] = {}
        all_keys = set(ta.keys()) | set(tb.keys())
        for key in sorted(all_keys):
            if key == "start_time":
                continue
            va = ta.get(key)
            vb = tb.get(key)
            if va != vb:
                test_diff[key] = {"a": va, "b": vb}
                if isinstance(va, int | float) and isinstance(vb, int | float):
                    test_diff[key]["delta"] = round(vb - va, 4)
                    test_diff[key]["pct_change"] = (
                        round(((vb - va) / va) * 100, 2) if va != 0 else "inf"
                    )
        if test_diff:
            diff["tests"][name] = test_diff

    for key in (
        "total_tests",
        "passed",
        "failed",
        "total_duration_seconds",
        "total_tokens_injected",
        "total_tokens_saved",
    ):
        va = a.get("summary", {}).get(key)
        vb = b.get("summary", {}).get(key)
        if va != vb and isinstance(va, int | float) and isinstance(vb, int | float):
            diff.setdefault("summary", {})[key] = {
                "a": va,
                "b": vb,
                "delta": round(vb - va, 4),
            }

    return diff
