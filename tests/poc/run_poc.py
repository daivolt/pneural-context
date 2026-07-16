#!/usr/bin/env python3
"""PoC Orchestrator — setup, run pytest, export telemetry report.

Usage:
    python run_poc.py              # Run all PoC tests
    python run_poc.py --test 02    # Run specific test phase
    python run_poc.py --clean      # Clean test data from pneural-context
    python run_poc.py --compare report_a.json report_b.json
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

PNEURAL_URL = os.environ.get("PNEURAL_POC_URL", "http://localhost:8779")
PROJECT = os.environ.get("PNEURAL_POC_PROJECT", "poc-test")
POC_DIR = Path(__file__).parent
REPORTS_DIR = POC_DIR / "reports"


def wait_for_service(url: str, name: str, timeout: int = 30) -> bool:
    """Wait for a service to become available."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = httpx.get(url, timeout=5)
            if r.status_code < 500:
                print(f"  [OK] {name} is up ({url})")
                return True
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
        time.sleep(2)
    print(f"  [FAIL] {name} not available at {url} after {timeout}s")
    return False


def setup_opencode_on_ryzen() -> None:
    """Create opencode.json and plugin directory on ryzen via SSH."""
    import subprocess as sp

    ryan_ssh = "sshpass -p 'icaro9$d' ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no daivolt@10.42.0.89"

    opencode_json = r"""{
  "$schema": "https://opencode.ai/config.json",
  "model": "llamacpp/qwen2.5-coder-7b",
  "provider": {
    "llamacpp": {
      "name": "llama.cpp",
      "npm": "@ai-sdk/openai-compatible",
      "options": {
        "baseURL": "http://localhost:8080/v1"
      },
      "models": {
        "qwen2.5-coder-7b": {
          "name": "qwen2.5-coder-7b-instruct"
        }
      }
    }
  },
  "plugin": [
    "C:\\Users\\daivolt\\.config\\opencode\\plugins\\pneural-context-plugin"
  ]
}"""

    print("\n[1/5] Creating opencode.json on ryzen...")
    cmd = f'''{ryan_ssh} "powershell -Command \\"Set-Content -Path 'C:\\Users\\daivolt\\.config\\opencode\\opencode.json' -Value '{opencode_json.replace("'", "\\'")}'  -Encoding UTF8\\""'''
    sp.run(cmd, shell=True, capture_output=True)

    print("[2/5] Creating plugin directory on ryzen...")
    sp.run(
        f'''{ryan_ssh} "powershell -Command \\"New-Item -ItemType Directory -Path 'C:\\Users\\daivolt\\.config\\opencode\\plugins\\pneural-context-plugin' -Force | Out-Null\\""''',
        shell=True,
        capture_output=True,
    )

    print("[3/5] Copying plugin files to ryzen...")
    local_plugin = (
        Path(__file__).parent.parent.parent / "plugins" / "opencode" / "pneural-context.mjs"
    )
    if local_plugin.exists():
        sp.run(
            f"sshpass -p 'icaro9$d' scp -o StrictHostKeyChecking=no {local_plugin} daivolt@10.42.0.89:'C:\\Users\\daivolt\\.config\\opencode\\plugins\\pneural-context-plugin\\index.mjs'",
            shell=True,
            capture_output=True,
        )

    package_json = '{"name": "pneural-context-plugin", "main": "index.mjs"}'
    sp.run(
        f'''{ryan_ssh} "powershell -Command \\"Set-Content -Path 'C:\\Users\\daivolt\\.config\\opencode\\plugins\\pneural-context-plugin\\package.json' -Value '{package_json}'\\""''',
        shell=True,
        capture_output=True,
    )

    print("[4/5] Setting project config on ryzen...")
    sp.run(
        f'''{ryan_ssh} "powershell -Command \\"Set-Content -Path 'C:\\pneural-context\\.pneural-context.json' -Value '{{\"project\": \"poc-test\"}}'\\""''',
        shell=True,
        capture_output=True,
    )

    print("[5/5] Verifying ryzen services...")
    for url, name in [
        ("http://10.42.0.89:8779/health", "pneural-context"),
        ("http://10.42.0.89:8080/v1/models", "llama.cpp"),
        ("http://10.42.0.89:11434/api/tags", "ollama"),
    ]:
        try:
            r = httpx.get(url, timeout=10)
            print(f"  [OK] {name}: {r.status_code}")
        except Exception as e:
            print(f"  [WARN] {name}: {e}")


def clean_test_data() -> None:
    """Remove all test data for project poc-test from pneural-context."""
    print(f"\nCleaning test data for project '{PROJECT}'...")
    with httpx.Client(base_url=PNEURAL_URL, timeout=30) as client:
        entries = client.get("/api/memory", params={"project": PROJECT}).json()
        count = 0
        for e in entries:
            try:
                r = client.delete(f"/api/memory/{e['id']}", params={"project": PROJECT})
                if r.status_code == 200:
                    count += 1
            except Exception:
                pass
        print(f"  Deleted {count} memory entries")

        try:
            client.post("/api/consolidation", json={"project": PROJECT})
        except Exception:
            pass

        costs = client.get("/api/costs", params={"project": PROJECT, "days": 365}).json()
        print(
            f"  Found {len(costs) if isinstance(costs, list) else '?'} cost records (not deleted — inspect manually)"
        )


def run_tests(test_filter: str | None = None) -> int:
    """Run pytest on the PoC tests."""
    REPORTS_DIR.mkdir(exist_ok=True)

    print("\n" + "=" * 60)
    print("pneural-context PoC Test Suite")
    print("=" * 60)

    print("\nChecking services...")
    services = [
        (f"{PNEURAL_URL}/health", "pneural-context"),
    ]
    for url, name in services:
        if not wait_for_service(url, name):
            print(f"\nERROR: {name} is not available. Start it and try again.")
            return 1

    cmd = [sys.executable, "-m", "pytest", "-v", "--tb=short", "-s"]
    if test_filter:
        cmd.append(
            f"tests/poc/test_{test_filter}_*.py"
            if len(test_filter) == 2
            else f"tests/poc/{test_filter}"
        )
    else:
        cmd.append("tests/poc/")
    cmd.extend(["--project-dir", str(POC_DIR.parent.parent)])

    print(f"\nRunning: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(POC_DIR.parent.parent))
    return result.returncode


def compare_reports(path_a: str, path_b: str) -> None:
    """Compare two telemetry reports."""
    from telemetry import compare_runs

    diff = compare_runs(path_a, path_b)
    print("\n" + "=" * 60)
    print(f"Comparing: {diff['run_a']} vs {diff['run_b']}")
    print("=" * 60)
    for test_name, metrics in diff.get("tests", {}).items():
        print(f"\n  {test_name}:")
        for key, values in metrics.items():
            delta = values.get("delta", "")
            pct = values.get("pct_change", "")
            print(f"    {key}: {values['a']} → {values['b']}  (Δ={delta}, {pct}%)")
    if "summary" in diff:
        print("\n  Summary:")
        for key, values in diff["summary"].items():
            print(f"    {key}: {values['a']} → {values['b']}  (Δ={values['delta']})")


def main():
    parser = argparse.ArgumentParser(description="pneural-context PoC test orchestrator")
    parser.add_argument("--test", help="Run specific test phase (e.g., '02' for test_02)")
    parser.add_argument("--setup", action="store_true", help="Setup opencode on ryzen")
    parser.add_argument("--clean", action="store_true", help="Clean test data from pneural-context")
    parser.add_argument(
        "--compare", nargs=2, metavar=("REPORT_A", "REPORT_B"), help="Compare two telemetry reports"
    )
    args = parser.parse_args()

    if args.clean:
        clean_test_data()
        return 0
    if args.compare:
        compare_reports(args.compare[0], args.compare[1])
        return 0
    if args.setup:
        setup_opencode_on_ryzen()
        return 0

    return run_tests(args.test)


if __name__ == "__main__":
    sys.exit(main())
