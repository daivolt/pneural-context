"""Benchmark orchestrator — runs control arm, treatment arm, API exercises, and evaluation."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx

PNEURAL_URL = "http://localhost:8779"
OPENCODE_URL = "http://localhost:4096"
DUMMY_URL = "http://localhost:9999"
PROJECT = "poc-benchmark"

BASE_DIR = Path(__file__).parent
CONVERSATION_FILE = BASE_DIR / "conversation.json"
SEED_FILE = BASE_DIR / "seed_data.json"
CONVERSATION_DIR = BASE_DIR / "conversation"
LOGS_DIR = BASE_DIR / "logs"
REPORTS_DIR = BASE_DIR / "reports"

OPENCODE_DB_WIN = r"C:\Users\daivolt\AppData\Local\opencode\opencode.db"
RYZEN_SSH = ["sshpass", "-p", "icaro9$d", "scp", "-o", "StrictHostKeyChecking=no"]
RYZEN_HOST = "daivolt@10.42.0.89"


def check_services() -> dict[str, bool]:
    results = {}
    for name, url in [("pneural-context", PNEURAL_URL), ("opencode", OPENCODE_URL)]:
        try:
            r = (
                httpx.get(f"{url}/health", timeout=5)
                if "pneural" in name
                else httpx.get(f"{url}/session", timeout=5)
            )
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
    dest = LOGS_DIR / f"{arm}_opencode.db"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        RYZEN_SSH + [f"{RYZEN_HOST}:{OPENCODE_DB_WIN.replace(chr(92), '/')}", str(dest)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        print(f"  [WARN] Failed to copy opencode DB for {arm}: {result.stderr[:200]}")
    else:
        print(f"  Copied opencode DB for {arm}")
    return dest


def run_conversation_arm(arm: str, pneural_url: str, project: str) -> dict[str, Any]:
    from conversation_runner import ConversationRunner

    print(f"\n{'='*60}")
    print(f"  Running {arm} arm conversation (pneural={pneural_url})")
    print(f"{'='*60}")

    prompts = json.loads(CONVERSATION_FILE.read_text())
    runner = ConversationRunner(arm=arm, project=project)

    original_env = None
    if arm == "control":
        import os

        original_env = os.environ.get("PNEURAL_CONTEXT_URL")
        os.environ["PNEURAL_CONTEXT_URL"] = "http://localhost:9999"

    session_id = None
    results = []
    try:
        session_id = runner.create_session()
        results = runner.run_conversation(prompts)
    finally:
        runner.close()
        if arm == "control" and original_env is not None:
            import os

            os.environ["PNEURAL_CONTEXT_URL"] = original_env

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
    import os

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
    print("=" * 60)
    print("  PNEURAL-CONTEXT PoC BENCHMARK")
    print("=" * 60)

    for d in [CONVERSATION_DIR / "control", CONVERSATION_DIR / "treatment", LOGS_DIR, REPORTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)

    print("\n[1/7] Checking services...")
    services = check_services()
    for name, ok in services.items():
        print(f"  {name}: {'OK' if ok else 'DOWN'}")
    if not all(services.values()):
        print("  [ERROR] Not all services are up. Exiting.")
        sys.exit(1)

    print("\n[2/7] Cleaning and seeding memory...")
    clean_project()
    seed_memory()

    print("\n[3/7] Running control arm...")
    control = run_conversation_arm("control", "http://localhost:9999", PROJECT)

    print("\n[4/7] Running treatment arm...")
    time.sleep(5)
    treatment = run_conversation_arm("treatment", PNEURAL_URL, PROJECT)

    print("\n[5/7] Running API exercises...")
    api_results = run_api_exercises()

    print("\n[6/7] Running MCP exercises...")
    mcp_results = run_mcp_exercises()

    print("\n[7/7] Running evaluation...")

    control_dir = CONVERSATION_DIR / "control"
    treatment_dir = CONVERSATION_DIR / "treatment"
    control_db = (
        Path(control["db_path"]) if control.get("db_path") else LOGS_DIR / "control_opencode.db"
    )
    treatment_db = (
        Path(treatment["db_path"])
        if treatment.get("db_path")
        else LOGS_DIR / "treatment_opencode.db"
    )

    faithfulness = run_faithfulness(control_dir, treatment_dir)
    db_inspection = run_db_inspection(
        control_db,
        treatment_db,
        control.get("session_id"),
        treatment.get("session_id"),
    )
    code_quality = run_code_quality(control_dir, treatment_dir)
    llm_judge = run_llm_judge(control_dir, treatment_dir)

    from report_generator import generate_report, save_report

    report = generate_report(
        api_exercises=api_results,
        mcp_exercises=mcp_results,
        faithfulness=faithfulness,
        db_inspection=db_inspection,
        code_quality=code_quality,
        llm_judge=llm_judge,
        control_session_id=control.get("session_id"),
        treatment_session_id=treatment.get("session_id"),
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
