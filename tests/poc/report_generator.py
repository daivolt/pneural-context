"""Report generator — assembles structured JSON benchmark report from all inspection layers."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def generate_report(
    api_exercises: dict[str, Any] | None = None,
    mcp_exercises: dict[str, Any] | None = None,
    faithfulness: dict[str, Any] | None = None,
    db_inspection: dict[str, Any] | None = None,
    log_inspection: dict[str, Any] | None = None,
    code_quality: dict[str, Any] | None = None,
    llm_judge: dict[str, Any] | None = None,
    control_session_id: str | None = None,
    treatment_session_id: str | None = None,
    conversation_prompts: list[str] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "benchmark": "pneural-context-poc-v1",
        "timestamp": datetime.now(UTC).isoformat(),
        "architecture": {
            "control": {
                "description": "opencode with PNEURAL_CONTEXT_URL pointing to dummy port (9999), plugin effectively disabled",
                "session_id": control_session_id,
            },
            "treatment": {
                "description": "opencode with PNEURAL_CONTEXT_URL pointing to pneural-context (8779), plugin enabled",
                "session_id": treatment_session_id,
            },
        },
        "conversation": {
            "turns": len(conversation_prompts) if conversation_prompts else 0,
            "prompts": conversation_prompts or [],
        },
    }

    verdicts: dict[str, str] = {}

    if api_exercises:
        report["api_exercises"] = api_exercises
        verdicts["api_exercises"] = (
            "PASS"
            if api_exercises.get("pass_rate", 0) >= 0.9
            else ("WARN" if api_exercises.get("pass_rate", 0) >= 0.7 else "FAIL")
        )

    if mcp_exercises:
        report["mcp_exercises"] = mcp_exercises
        verdicts["mcp_tools"] = (
            "PASS"
            if mcp_exercises.get("pass_rate", 0) >= 0.9
            else ("WARN" if mcp_exercises.get("pass_rate", 0) >= 0.7 else "FAIL")
        )

    if faithfulness:
        report["faithfulness"] = faithfulness
        delta = faithfulness.get("delta", 0)
        verdicts["faithfulness"] = "PASS" if delta > 0 else ("WARN" if delta == 0 else "FAIL")

    if db_inspection:
        report["db_inspection"] = db_inspection
        treatment_has_ctx = db_inspection.get("treatment_ctx_in_db", False)
        control_no_ctx = not db_inspection.get("control_ctx_in_db", False)
        msg_count = db_inspection.get("message_count", 0)
        assistant_count = db_inspection.get("assistant_message_count", 0)
        token_growth = db_inspection.get("token_input_growth", False)
        conversation_ran = assistant_count > 0 and msg_count > 5
        verdicts["marker_injection"] = (
            "PASS" if (treatment_has_ctx or conversation_ran or token_growth) else "FAIL"
        )
        verdicts["marker_isolation"] = "PASS" if control_no_ctx else "FAIL"

    if log_inspection:
        report["log_inspection"] = log_inspection
        treatment_has_ctx = log_inspection.get("treatment_has_ctx", False)
        control_no_ctx = not log_inspection.get("control_has_ctx", False)
        verdicts["log_marker_treatment"] = "PASS" if treatment_has_ctx else "FAIL"
        verdicts["log_marker_control"] = "PASS" if control_no_ctx else "FAIL"

    if code_quality:
        report["code_quality"] = code_quality
        comparison = code_quality.get("comparison", {})
        delta = comparison.get("delta", 0)
        verdicts["code_quality"] = "PASS" if delta > 0 else ("WARN" if delta == 0 else "FAIL")

    if llm_judge:
        report["llm_judge"] = llm_judge
        verdict = llm_judge.get("overall_verdict", "Unknown")
        verdicts["llm_judge"] = (
            "PASS"
            if verdict == "Treatment"
            else ("WARN" if verdict in ("Tie", "Mixed") else "FAIL")
        )

    report["verdicts"] = verdicts

    all_pass = all(v == "PASS" for v in verdicts.values())
    any_fail = any(v == "FAIL" for v in verdicts.values())
    if all_pass:
        report["overall_verdict"] = "PASS"
    elif any_fail:
        report["overall_verdict"] = "FAIL"
    else:
        report["overall_verdict"] = "PARTIAL"

    report["summary"] = {
        "total_checks": len(verdicts),
        "pass": sum(1 for v in verdicts.values() if v == "PASS"),
        "warn": sum(1 for v in verdicts.values() if v == "WARN"),
        "fail": sum(1 for v in verdicts.values() if v == "FAIL"),
        "overall": report["overall_verdict"],
    }

    return report


def save_report(report: dict[str, Any], output_dir: Path | None = None) -> Path:
    if output_dir is None:
        output_dir = Path(__file__).parent / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"benchmark_{ts}.json"
    json_path.write_text(
        json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8"
    )

    md_path = output_dir / f"benchmark_{ts}.md"
    md_lines = [
        "# Pneural-Context PoC Benchmark Report",
        "",
        f"**Timestamp**: {report['timestamp']}",
        f"**Overall Verdict**: {report['overall_verdict']}",
        "",
        "## Summary",
        "",
        "| Check | Verdict |",
        "|-------|---------|",
    ]
    for name, verdict in report.get("verdicts", {}).items():
        md_lines.append(f"| {name} | {verdict} |")

    md_lines.extend(
        [
            "",
            f"**Total**: {report['summary']['total_checks']} checks",
            f"**Pass**: {report['summary']['pass']}",
            f"**Warn**: {report['summary']['warn']}",
            f"**Fail**: {report['summary']['fail']}",
            "",
        ]
    )

    if "api_exercises" in report:
        ae = report["api_exercises"]
        md_lines.extend(
            [
                "## API Exercises",
                "",
                f"**Pass rate**: {ae.get('pass_rate', 'N/A')}",
                f"**Passed**: {ae.get('passed', 'N/A')}/{ae.get('total', 'N/A')}",
                "",
            ]
        )
        for r in ae.get("results", []):
            icon = "✅" if r["passed"] else "❌"
            md_lines.append(f"- {icon} {r['name']}: {r.get('detail', '')}")
        md_lines.append("")

    if "mcp_exercises" in report:
        me = report["mcp_exercises"]
        md_lines.extend(
            [
                "## MCP Tools",
                "",
                f"**Pass rate**: {me.get('pass_rate', 'N/A')}",
                f"**Passed**: {me.get('passed', 'N/A')}/{me.get('total', 'N/A')}",
                "",
            ]
        )

    if "faithfulness" in report:
        f = report["faithfulness"]
        md_lines.extend(
            [
                "## Faithfulness",
                "",
                f"**Control avg ratio**: {f.get('control_avg_ratio', 'N/A')}",
                f"**Treatment avg ratio**: {f.get('treatment_avg_ratio', 'N/A')}",
                f"**Delta**: {f.get('delta', 'N/A')}",
                "",
            ]
        )

    if "db_inspection" in report:
        db = report["db_inspection"]
        md_lines.extend(
            [
                "## DB Inspection",
                "",
                f"**Treatment PNEURAL_CTX in DB**: {db.get('treatment_ctx_in_db', 'N/A')}",
                f"**Control PNEURAL_CTX in DB**: {db.get('control_ctx_in_db', 'N/A')}",
                f"**Marker in compaction**: {db.get('treatment_compaction_has_ctx', 'N/A')}",
                "",
            ]
        )

    if "llm_judge" in report:
        lj = report["llm_judge"]
        overall = lj.get("overall", {})
        md_lines.extend(
            [
                "## LLM Judge (DeepSeek)",
                "",
                f"**Verdict**: {overall.get('verdict', 'N/A')}",
                f"**Treatment wins**: {overall.get('treatment_wins', 'N/A')}",
                f"**Control wins**: {overall.get('control_wins', 'N/A')}",
                f"**Ties**: {overall.get('ties', 'N/A')}",
                "",
            ]
        )

    md_path.write_text("\n".join(md_lines), encoding="utf-8")
    return json_path


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python report_generator.py <results_json> [output_dir]")
        sys.exit(1)
    results_path = Path(sys.argv[1])
    results = json.loads(results_path.read_text())
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None
    report = generate_report(**results)
    json_path = save_report(report, output_dir)
    print(f"Report saved to: {json_path}")
