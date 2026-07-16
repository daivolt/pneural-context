"""Benchmark orchestrator — single-arm PoC benchmark for pneural-context.

This runs the TREATMENT arm only (plugin enabled with seeded benchmark data).
The control comparison is done by comparing against existing sessions in the DB
that were run without the benchmark memory data.

Architecture:
  Phase 1: Check services, clean/seed memory
  Phase 2: Run treatment arm (10-turn conversation)
  Phase 3: Copy opencode DB for inspection
  Phase 4: API exercises (all pneural-context endpoints)
  Phase 5: MCP exercises (all MCP tools)
  Phase 6: Evaluation (DB inspection, faithfulness, code quality, LLM judge)
  Phase 7: Report generation
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PNEURAL_URL = "http://localhost:8779"
OPENCODE_URL = "http://localhost:4096"
PROJECT = "poc-benchmark"

BASE_DIR = Path(__file__).parent
CONVERSATION_FILE = BASE_DIR / "conversation.json"
SEED_FILE = BASE_DIR / "seed_data.json"
CONVERSATION_DIR = BASE_DIR / "conversation"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"

OPENCODE_DB_PATH = Path(r"C:\Users\daivolt\.local\share\opencode\opencode.db")


def check_services() -> dict[str, bool]:
    results = {}
    for name, url, path in [
        ("pneural-context", PNEURAL_URL, "/docs"),
        ("opencode", OPENCODE_URL, "/session"),
    ]:
        try:
            r = httpx.get(f"{url}{path}", timeout=5, follow_redirects=True)
            results[name] = r.status_code < 500
        except Exception:
            results[name] = False
    return results


def seed_memory(entries: list[dict] | None = None) -> list[str]:
    if entries is None:
        entries = json.loads(SEED_FILE.read_text())
    ids = []
    with httpx.Client(base_url=PNEURAL_URL, timeout=30) as client:
        for entry in entries:
            r = client.post("/api/memory", json={"project": PROJECT, **entry})
            if r.status_code == 200:
                ids.append(r.json().get("id", ""))
            else:
                print(f"  [WARN] Failed to seed: {r.status_code} {r.text[:200]}")
    print(f"  Seeded {len(ids)} memory entries")
    return ids


def clean_project() -> None:
    with httpx.Client(base_url=PNEURAL_URL, timeout=30) as client:
        r = client.get("/api/memory", params={"project": PROJECT})
        if r.status_code != 200:
            return
        entries = r.json()
        if isinstance(entries, list):
            for e in entries:
                eid = e.get("id") or e.get("entry_id")
                if eid:
                    client.delete(f"/api/memory/{eid}", params={"project": PROJECT})
    print("  Cleaned project data")


def copy_opencode_db(suffix: str = "treatment") -> Path:
    dest = LOGS_DIR / f"{suffix}_opencode.db"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    src = OPENCODE_DB_PATH
    if not src.exists():
        print(f"  [WARN] opencode DB not found at {src}")
        return dest
    shutil.copy2(str(src), str(dest))
    print(f"  Copied opencode DB ({dest.stat().st_size} bytes)")
    return dest


def run_conversation(project: str = PROJECT) -> dict[str, Any]:
    from conversation_runner import ConversationRunner

    print(f"\n{'='*60}")
    print("  Running treatment arm conversation")
    print(f"{'='*60}")

    prompts = json.loads(CONVERSATION_FILE.read_text())
    runner = ConversationRunner(arm="treatment", project=project)

    session_id = None
    results = []
    try:
        session_id = runner.create_session()
        results = runner.run_conversation(prompts)
    finally:
        runner.close()

    print(f"  Treatment arm completed: {len(results)} turns")

    db_path = copy_opencode_db("treatment")

    return {
        "arm": "treatment",
        "session_id": session_id,
        "results": results,
        "db_path": str(db_path),
    }


def run_api_exercises() -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running API exercises (36 endpoints)")
    print(f"{'='*60}")

    from api_exercises import APIExercises

    exercises = APIExercises(base_url=PNEURAL_URL, project=PROJECT)
    try:
        exercises.run_all()
    finally:
        exercises.cleanup()
        exercises.close()
    return exercises.summary()


def run_mcp_exercises() -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running MCP tool exercises (29 tools)")
    print(f"{'='*60}")

    from mcp_exercise import MCPExercise

    exercise = MCPExercise(base_url=PNEURAL_URL, project=PROJECT)
    try:
        exercise.run_all()
    finally:
        exercise.close()
    return exercise.summary()


def run_faithfulness(treatment_dir: Path) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running faithfulness analysis")
    print(f"{'='*60}")

    treat_responses = []
    for i in range(1, 11):
        treat_file = treatment_dir / f"turn_{i:02d}_response.txt"
        treat_responses.append(treat_file.read_text() if treat_file.exists() else "")

    from faithfulness import check_faithfulness_per_turn

    per_turn = check_faithfulness_per_turn(treat_responses)
    avg_ratio = sum(r["match_ratio"] for r in per_turn) / len(per_turn) if per_turn else 0
    return {
        "per_turn": per_turn,
        "avg_match_ratio": round(avg_ratio, 3),
        "total_seeds_matched": sum(r["matched_seeds"] for r in per_turn),
    }


def run_db_inspection(db_path: Path, session_id: str | None) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running DB inspection")
    print(f"{'='*60}")

    from db_inspector import inspect_opencode_db

    return inspect_opencode_db(db_path, session_id)


def run_code_quality(treatment_dir: Path) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running code quality analysis")
    print(f"{'='*60}")

    from code_quality import analyze_response

    quality_scores = []
    for i in range(1, 11):
        resp_file = treatment_dir / f"turn_{i:02d}_response.txt"
        if resp_file.exists():
            text = resp_file.read_text()
            if text.strip():
                quality_scores.append(analyze_response(text))

    if not quality_scores:
        return {"error": "No responses to analyze"}

    avg_scores = {}
    for key in quality_scores[0]:
        if isinstance(quality_scores[0][key], int | float):
            avg_scores[key] = round(sum(s[key] for s in quality_scores) / len(quality_scores), 2)

    return {
        "per_turn_count": len(quality_scores),
        "averages": avg_scores,
    }


def run_llm_judge(treatment_dir: Path) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("  [SKIP] DEEPSEEK_API_KEY not set, skipping LLM judge")
        return {"error": "DEEPSEEK_API_KEY not set", "per_turn": [], "overall_verdict": "Skipped"}

    print(f"\n{'='*60}")
    print("  Running LLM judge (DeepSeek)")
    print(f"{'='*60}")

    treat_responses = []
    for i in range(1, 11):
        treat_file = treatment_dir / f"turn_{i:02d}_response.txt"
        treat_responses.append(treat_file.read_text() if treat_file.exists() else "")

    from faithfulness import FAITHFULNESS_TERMS

    prompts = json.loads(CONVERSATION_FILE.read_text())

    from llm_judge import judge_pair

    per_turn = []
    for i, (resp, _prompt) in enumerate(zip(treat_responses, prompts, strict=False)):
        if not resp.strip():
            per_turn.append({"turn": i + 1, "error": "empty response", "final_verdict": "Skipped"})
            continue

        seed_terms = " ".join(f"- {info['description']}" for info in FAITHFULNESS_TERMS.values())
        task = f"Build a FastAPI task management API. Relevant project knowledge: {seed_terms}"

        result = judge_pair(
            task,
            "[no context baseline - this response was generated without project-specific memory]",
            resp,
            api_key,
        )
        result["turn"] = i + 1
        per_turn.append(result)
        time.sleep(2)

    return {
        "per_turn": per_turn,
        "overall_verdict": "Treatment preferred"
        if sum(1 for r in per_turn if r.get("final_verdict") in ("Treatment", "B"))
        > len(per_turn) / 2
        else "Mixed",
    }


def main() -> None:
    phase = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    print("=" * 60)
    print("  PNEURAL-CONTEXT PoC BENCHMARK")
    print("=" * 60)

    for d in [CONVERSATION_DIR / "treatment", LOGS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    if phase == 0 or phase == 1:
        print("\n[1/7] Checking services...")
        services = check_services()
        for name, ok in services.items():
            print(f"  {name}: {'OK' if ok else 'DOWN'}")
        if not services.get("pneural-context"):
            print("  [ERROR] pneural-context is not running. Exiting.")
            sys.exit(1)
        if not services.get("opencode"):
            print("  [ERROR] opencode serve is not running. Exiting.")
            sys.exit(1)

    if phase == 0 or phase == 2:
        print("\n[2/7] Cleaning and seeding memory...")
        clean_project()
        seed_memory()

    if phase == 0 or phase == 3:
        print("\n[3/7] Running treatment arm conversation...")
        treatment = run_conversation()
        with open(LOGS_DIR / "treatment_results.json", "w") as f:
            json.dump(treatment, f, indent=2, default=str)
        print(f"  Treatment results saved to {LOGS_DIR / 'treatment_results.json'}")

    if phase == 0 or phase == 4:
        print("\n[4/7] Running API exercises...")
        api_results = run_api_exercises()
        with open(LOGS_DIR / "api_results.json", "w") as f:
            json.dump(api_results, f, indent=2, default=str)

    if phase == 0 or phase == 5:
        print("\n[5/7] Running MCP exercises...")
        mcp_results = run_mcp_exercises()
        with open(LOGS_DIR / "mcp_results.json", "w") as f:
            json.dump(mcp_results, f, indent=2, default=str)

    if phase == 0 or phase == 6:
        print("\n[6/7] Running evaluation...")
        treatment_dir = CONVERSATION_DIR / "treatment"
        treatment_results_file = LOGS_DIR / "treatment_results.json"

        treatment_sid = None
        if treatment_results_file.exists():
            treatment_sid = json.loads(treatment_results_file.read_text()).get("session_id")

        treatment_db = LOGS_DIR / "treatment_opencode.db"

        db_inspection = run_db_inspection(treatment_db, treatment_sid)
        faithfulness = run_faithfulness(treatment_dir)
        code_quality = run_code_quality(treatment_dir)
        llm_judge = run_llm_judge(treatment_dir)

        with open(LOGS_DIR / "db_inspection.json", "w") as f:
            json.dump(db_inspection, f, indent=2, default=str)
        with open(LOGS_DIR / "faithfulness.json", "w") as f:
            json.dump(faithfulness, f, indent=2, default=str)
        with open(LOGS_DIR / "code_quality.json", "w") as f:
            json.dump(code_quality, f, indent=2, default=str)
        with open(LOGS_DIR / "llm_judge.json", "w") as f:
            json.dump(llm_judge, f, indent=2, default=str)

    if phase == 0 or phase == 7:
        print("\n[7/7] Generating report...")
        treatment_results_file = LOGS_DIR / "treatment_results.json"
        api_results_file = LOGS_DIR / "api_results.json"
        mcp_results_file = LOGS_DIR / "mcp_results.json"
        db_inspection_file = LOGS_DIR / "db_inspection.json"
        faithfulness_file = LOGS_DIR / "faithfulness.json"
        code_quality_file = LOGS_DIR / "code_quality.json"
        llm_judge_file = LOGS_DIR / "llm_judge.json"

        def load_result(path: Path) -> dict:
            if path.exists():
                return json.loads(path.read_text())
            return {}

        from report_generator import generate_report, save_report

        report = generate_report(
            api_exercises=api_results if phase in (0, 4) else load_result(api_results_file),
            mcp_exercises=mcp_results if phase in (0, 5) else load_result(mcp_results_file),
            faithfulness=faithfulness if phase in (0, 6) else load_result(faithfulness_file),
            db_inspection=db_inspection if phase in (0, 6) else load_result(db_inspection_file),
            code_quality=code_quality if phase in (0, 6) else load_result(code_quality_file),
            llm_judge=llm_judge if phase in (0, 6) else load_result(llm_judge_file),
            control_session_id=None,
            treatment_session_id=treatment_sid
            if phase in (0, 3, 6)
            else load_result(treatment_results_file).get("session_id"),
            conversation_prompts=json.loads(CONVERSATION_FILE.read_text()),
        )

        json_path = save_report(report, REPORTS_DIR)
        print(f"\n{'='*60}")
        print("  BENCHMARK COMPLETE")
        print(f"  Report: {json_path}")
        print(f"  Overall: {report.get('overall_verdict', 'unknown')}")
        print(f"  Summary: {report.get('summary', 'no summary')}")
        print(f"{'='*60}")

        clean_project()


if __name__ == "__main__":
    main()
