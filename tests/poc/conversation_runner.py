"""Conversation runner — sends prompts to opencode serve, captures responses + metadata."""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any

import httpx

OPENCODE_URL = "http://localhost:4096"
PNEURAL_URL = "http://localhost:8779"
CONVERSATION_FILE = Path(__file__).parent / "conversation.json"
LOGS_DIR = Path(__file__).parent / "logs"
CONVERSATION_DIR = Path(__file__).parent / "conversation"
OPENCODE_DB_PATH_WIN = r"C:\Users\daivolt\AppData\Local\opencode\opencode.db"


def load_conversation() -> list[str]:
    return json.loads(CONVERSATION_FILE.read_text())


def seed_memory(entries: list[dict] | None = None) -> list[str]:
    if entries is None:
        seed_file = Path(__file__).parent / "seed_data.json"
        entries = json.loads(seed_file.read_text())
    ids = []
    with httpx.Client(base_url=PNEURAL_URL, timeout=30) as client:
        for entry in entries:
            r = client.post("/api/memory", json={"project": "poc-benchmark", **entry})
            if r.status_code == 200:
                ids.append(r.json()["id"])
            else:
                print(f"  [WARN] Failed to seed: {r.status_code} {r.text[:200]}")
    return ids


def clean_benchmark_data() -> None:
    with httpx.Client(base_url=PNEURAL_URL, timeout=30) as client:
        r = client.get("/api/memory", params={"project": "poc-benchmark"})
        if r.status_code != 200:
            return
        entries = r.json()
        for e in entries:
            eid = e.get("id") or e.get("entry_id")
            if eid:
                client.delete(f"/api/memory/{eid}", params={"project": "poc-benchmark"})
    print("  [OK] Cleaned benchmark data")


class ConversationRunner:
    def __init__(self, arm: str, project: str = "poc-benchmark"):
        assert arm in ("control", "treatment")
        self.arm = arm
        self.project = project
        self.client = httpx.Client(base_url=OPENCODE_URL, timeout=180.0)
        self.session_id: str | None = None
        self.responses: list[dict[str, Any]] = []
        self.session_info: dict | None = None

    def create_session(self) -> str:
        r = self.client.post("/session", json={"title": f"poc-benchmark-{self.arm}"})
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Failed to create session: {r.status_code} {r.text[:500]}")
        data = r.json()
        self.session_id = data.get("id") or data.get("session_id")
        if not self.session_id:
            raise RuntimeError(f"No session ID in response: {data}")
        print(f"  [{self.arm}] Created session: {self.session_id}")
        return self.session_id

    def send_message(
        self, text: str, poll_timeout: float = 120.0, poll_interval: float = 3.0
    ) -> dict:
        if not self.session_id:
            raise RuntimeError("No session ID — call create_session() first")

        r = self.client.post(
            f"/session/{self.session_id}/prompt_async",
            json={"parts": [{"type": "text", "text": text}]},
        )
        if r.status_code not in (200, 204):
            return {"status": "error", "code": r.status_code, "text": r.text[:500]}

        deadline = time.monotonic() + poll_timeout
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            msgs_r = self.client.get(f"/session/{self.session_id}/message")
            if msgs_r.status_code != 200:
                continue
            msgs = msgs_r.json()
            if not isinstance(msgs, list) or len(msgs) < 2:
                continue
            last = msgs[-1]
            parts = last.get("parts", [])
            texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
            combined = " ".join(texts).strip()
            if combined:
                info = last.get("info", {})
                return {
                    "status": "ok",
                    "text": combined,
                    "parts": parts,
                    "role": info.get("role", ""),
                    "tokens": info.get("tokens", {}),
                    "message_id": last.get("id", ""),
                }

        return {"status": "timeout", "text": "", "tokens": {}}

    def run_conversation(self, prompts: list[str]) -> list[dict]:
        results = []
        for i, prompt in enumerate(prompts):
            print(f"  [{self.arm}] Turn {i+1}/{len(prompts)}: {prompt[:60]}...")
            start = time.monotonic()
            result = self.send_message(prompt)
            elapsed = time.monotonic() - start
            result["turn"] = i + 1
            result["prompt"] = prompt
            result["elapsed_seconds"] = round(elapsed, 2)
            results.append(result)

            out_dir = CONVERSATION_DIR / self.arm
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"turn_{i+1:02d}_prompt.txt").write_text(prompt)
            (out_dir / f"turn_{i+1:02d}_response.txt").write_text(result.get("text", ""))

            time.sleep(5)

        self.responses = results
        return results

    def get_session_info(self) -> dict:
        if not self.session_id:
            return {}
        r = self.client.get(f"/session/{self.session_id}")
        if r.status_code == 200:
            self.session_info = r.json()
        return self.session_info or {}

    def close(self) -> None:
        self.client.close()


def copy_opencode_db(arm: str) -> Path:
    dest = LOGS_DIR / f"{arm}_opencode.db"
    import subprocess

    result = subprocess.run(
        [
            "sshpass",
            "-p",
            "icaro9$d",
            "scp",
            "-o",
            "StrictHostKeyChecking=no",
            f"daivolt@10.42.0.89:{OPENCODE_DB_PATH_WIN.replace(chr(92), '/')}",
            str(dest),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        print(f"  [WARN] Failed to copy opencode DB: {result.stderr[:200]}")
    return dest


def query_opencode_db(db_path: Path, session_id: str) -> dict:
    if not db_path.exists():
        return {"error": f"DB not found at {db_path}"}
    results: dict[str, Any] = {}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, type, seq, time_created FROM session_message WHERE session_id = ? ORDER BY seq",
            (session_id,),
        ).fetchall()
        results["messages"] = [dict(r) for r in rows]

        compaction_rows = conn.execute(
            "SELECT id, type, seq, data FROM session_message WHERE session_id = ? AND type = 'compaction' ORDER BY seq",
            (session_id,),
        ).fetchall()
        results["compaction_messages"] = [dict(r) for r in compaction_rows]
        for cm in results["compaction_messages"]:
            if cm.get("data"):
                try:
                    cm["data_parsed"] = json.loads(cm["data"])
                except (json.JSONDecodeError, TypeError):
                    pass

        system_rows = conn.execute(
            "SELECT id, type, seq, data FROM session_message WHERE session_id = ? AND type = 'system' ORDER BY seq",
            (session_id,),
        ).fetchall()
        results["system_messages"] = [dict(r) for r in system_rows]

        has_ctx = False
        for row in results.get("compaction_messages", []):
            data_str = str(row.get("data", "")) + str(row.get("data_parsed", ""))
            if "PNEURAL_CTX" in data_str:
                has_ctx = True
        for row in results.get("system_messages", []):
            data_str = str(row.get("data", ""))
            if "PNEURAL_CTX" in data_str:
                has_ctx = True
        results["pneural_ctx_found_in_db"] = has_ctx
    finally:
        conn.close()
    return results


if __name__ == "__main__":
    prompts = load_conversation()
    print(f"Loaded {len(prompts)} prompts")

    runner = ConversationRunner("treatment")
    try:
        sid = runner.create_session()
        results = runner.run_conversation(prompts)
        print(f"\nCompleted {len(results)} turns")
        for r in results:
            status = r.get("status", "unknown")
            tokens = r.get("tokens", {})
            print(
                f"  Turn {r['turn']}: {status}, tokens_in={tokens.get('input', '?')}, tokens_out={tokens.get('output', '?')}"
            )
    finally:
        runner.close()
