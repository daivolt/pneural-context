"""Benchmark orchestrator — runs control arm, treatment arm, API exercises, and evaluation.

IMPORTANT: This script runs ON the Windows machine (desktop-ryzen) because it connects
to opencode serve on localhost:4096. The control arm requires opencode serve to be
restarted with PNEURAL_CONTEXT_URL=http://localhost:9999 (a dummy URL that refuses connections).

Architecture:
  Phase 1: Seed memory into pneural-context
  Phase 2: Run control arm (plugin effectively disabled via dummy URL)
  Phase 3: Run treatment arm (plugin enabled, PNEURAL_CONTEXT_URL=http://localhost:8779)
  Phase 4: API exercises (all pneural-context endpoints)
  Phase 5: MCP exercises (all MCP tools)
  Phase 6: Evaluation (faithfulness, DB inspection, code quality, LLM judge)
  Phase 7: Report generation

NOTE: The control arm requires restarting opencode serve with a different env var.
This benchmark script CANNOT restart opencode serve automatically — you must do it
manually between phases 2 and 3.
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
        for e in r.json():
            eid = e.get("id") or e.get("entry_id")
            if eid:
                client.delete(f"/api/memory/{eid}", params={"project": PROJECT})
    print("  Cleaned project data")


def copy_opencode_db(arm: str) -> Path:
    """Copy the opencode DB locally (benchmark runs on the same machine as opencode)."""
    dest = LOGS_DIR / f"{arm}_opencode.db"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    src = OPENCODE_DB_PATH
    if not src.exists():
        print(f"  [WARN] opencode DB not found at {src}")
        return dest
    shutil.copy2(str(src), str(dest))
    print(f"  Copied opencode DB for {arm} ({dest.stat().st_size} bytes)")
    return dest


def run_conversation_arm(arm: str, project: str) -> dict[str, Any]:
    from conversation_runner import ConversationRunner

    print(f"\n{'='*60}")
    print(f"  Running {arm} arm conversation")
    print(f"{'='*60}")

    prompts = json.loads(CONVERSATION_FILE.read_text())
    runner = ConversationRunner(arm=arm, project=project)

    session_id = None
    results = []
    try:
        session_id = runner.create_session()
        results = runner.run_conversation(prompts)
    finally:
        runner.close()

    print(f"  {arm} arm completed: {len(results)} turns")

    db_path = copy_opencode_db(arm)

    return {
        "arm": arm,
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


def run_faithfulness(control_dir: Path, treatment_dir: Path) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running faithfulness analysis")
    print(f"{'='*60}")

    ctrl_responses = []
    treat_responses = []
    for i in range(1, 11):
        ctrl_file = control_dir / f"turn_{i:02d}_response.txt"
        treat_file = treatment_dir / f"turn_{i:02d}_response.txt"
        ctrl_responses.append(ctrl_file.read_text() if ctrl_file.exists() else "")
        treat_responses.append(treat_file.read_text() if treat_file.exists() else "")

    from faithfulness import compare_faithfulness

    return compare_faithfulness(ctrl_responses, treat_responses)


def run_db_inspection(
    control_db: Path, treatment_db: Path, control_sid: str | None, treatment_sid: str | None
) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running DB inspection")
    print(f"{'='*60}")

    from db_inspector import compare_dbs

    return compare_dbs(control_db, treatment_db, control_sid, treatment_sid)


def run_code_quality(control_dir: Path, treatment_dir: Path) -> dict[str, Any]:
    print(f"\n{'='*60}")
    print("  Running code quality analysis")
    print(f"{'='*60}")

    from code_quality import compare_quality

    return compare_quality(control_dir, treatment_dir)


def run_llm_judge(control_dir: Path, treatment_dir: Path) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY", "")
    if not api_key:
        print("  [SKIP] DEEPSEEK_API_KEY not set, skipping LLM judge")
        return {
            "error": "DEEPSEEK_API_KEY not set",
            "per_turn": [],
            "overall": {"verdict": "Skipped"},
        }

    print(f"\n{'='*60}")
    print("  Running LLM judge (DeepSeek)")
    print(f"{'='*60}")

    from llm_judge import judge_all_turns

    ctrl_responses = []
    treat_responses = []
    for i in range(1, 11):
        ctrl_file = control_dir / f"turn_{i:02d}_response.txt"
        treat_file = treatment_dir / f"turn_{i:02d}_response.txt"
        ctrl_responses.append(ctrl_file.read_text() if ctrl_file.exists() else "")
        treat_responses.append(treat_file.read_text() if treat_file.exists() else "")

    prompts = json.loads(CONVERSATION_FILE.read_text())
    return judge_all_turns(ctrl_responses, treat_responses, prompts, api_key)


def main() -> None:
    phase = int(sys.argv[1]) if len(sys.argv) > 1 else 0

    print("=" * 60)
    print("  PNEURAL-CONTEXT PoC BENCHMARK")
    print("=" * 60)

    for d in [CONVERSATION_DIR / "control", CONVERSATION_DIR / "treatment", LOGS_DIR, REPORTS_DIR]:
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
        print("\n[3/7] Running control arm...")
        print("  NOTE: For control arm, opencode serve should be running with")
        print("  PNEURAL_CONTEXT_URL=http://localhost:9999 (dummy URL).")
        print("  If it's currently running with the treatment URL, you need to")
        print("  restart opencode serve with the control env var first.")
        print("  Press Ctrl+C to abort, or wait 10s to continue...")
        time.sleep(10)
        control = run_conversation_arm("control", PROJECT)

        with open(LOGS_DIR / "control_results.json", "w") as f:
            json.dump(control, f, indent=2, default=str)
        print(f"  Control results saved to {LOGS_DIR / 'control_results.json'}")

        if phase == 3:
            print("\n  [IMPORTANT] Control arm complete. Now restart opencode serve")
            print("  with PNEURAL_CONTEXT_URL=http://localhost:8779 (treatment URL)")
            print("  then run: python benchmark.py 4")
            return

    if phase == 0 or phase == 4:
        print("\n[4/7] Running treatment arm...")
        treatment = run_conversation_arm("treatment", PROJECT)

        with open(LOGS_DIR / "treatment_results.json", "w") as f:
            json.dump(treatment, f, indent=2, default=str)
        print(f"  Treatment results saved to {LOGS_DIR / 'treatment_results.json'}")

    if phase == 0 or phase == 5:
        print("\n[5/7] Running API exercises...")
        api_results = run_api_exercises()

    if phase == 0 or phase == 6:
        print("\n[6/7] Running MCP exercises...")
        mcp_results = run_mcp_exercises()

    if phase == 0 or phase == 7:
        print("\n[7/7] Running evaluation...")

        control_dir = CONVERSATION_DIR / "control"
        treatment_dir = CONVERSATION_DIR / "treatment"

        control_db = LOGS_DIR / "control_opencode.db"
        treatment_db = LOGS_DIR / "treatment_opencode.db"

        control_results_file = LOGS_DIR / "control_results.json"
        treatment_results_file = LOGS_DIR / "treatment_results.json"

        control_sid = None
        treatment_sid = None
        if control_results_file.exists():
            control_sid = json.loads(control_results_file.read_text()).get("session_id")
        if treatment_results_file.exists():
            treatment_sid = json.loads(treatment_results_file.read_text()).get("session_id")

        faithfulness = run_faithfulness(control_dir, treatment_dir)
        db_inspection = run_db_inspection(control_db, treatment_db, control_sid, treatment_sid)
        code_quality = run_code_quality(control_dir, treatment_dir)
        llm_judge = run_llm_judge(control_dir, treatment_dir)

        from report_generator import generate_report, save_report

        report = generate_report(
            api_exercises=api_results if phase in (0, 5) else {},
            mcp_exercises=mcp_results if phase in (0, 6) else {},
            faithfulness=faithfulness,
            db_inspection=db_inspection,
            code_quality=code_quality,
            llm_judge=llm_judge,
            control_session_id=control_sid,
            treatment_session_id=treatment_sid,
            conversation_prompts=json.loads(CONVERSATION_FILE.read_text()),
        )

        json_path = save_report(report, REPORTS_DIR)
        print(f"\n{'='*60}")
        print("  BENCHMARK COMPLETE")
        print(f"  Report: {json_path}")
        print(f"  Overall: {report['overall_verdict']}")
        print(f"  Summary: {report['summary']}")
        print(f"{'='*60}")

        clean_project()


if __name__ == "__main__":
    main()
