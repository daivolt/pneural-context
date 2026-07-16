"""Conversation runner — sends prompts to opencode serve, captures responses + metadata."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

import httpx

OPENCODE_URL = "http://localhost:4096"
PNEURAL_URL = "http://localhost:8779"
CONVERSATION_FILE = Path(__file__).parent / "conversation.json"
LOGS_DIR = Path(__file__).parent / "logs"
CONVERSATION_DIR = Path(__file__).parent / "conversation"
OPENCODE_DB_PATH = Path(r"C:\Users\daivolt\.local\share\opencode\opencode.db")


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
        last_msg_count = 0
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            msgs_r = self.client.get(f"/session/{self.session_id}/message")
            if msgs_r.status_code != 200:
                continue
            msgs = msgs_r.json()
            if not isinstance(msgs, list) or len(msgs) < 2:
                continue

            if len(msgs) <= last_msg_count:
                continue
            last_msg_count = len(msgs)

            last = msgs[-1]
            data_str = str(last.get("data", ""))
            if '"role":"assistant"' not in data_str and '"role": "assistant"' not in data_str:
                continue

            all_parts = []
            for m in msgs:
                d = m.get("data", "")
                if isinstance(d, str) and '"role":"assistant"' in d or '"role": "assistant"' in d:
                    try:
                        parsed = json.loads(d)
                        if parsed.get("role") == "assistant":
                            pass
                    except (json.JSONDecodeError, TypeError):
                        pass

            combined_text = ""
            parts_r = self.client.get(f"/session/{self.session_id}/part")
            if parts_r.status_code == 200:
                all_parts = parts_r.json()
                if isinstance(all_parts, list):
                    for p in all_parts:
                        pd = p.get("data", "")
                        if isinstance(pd, str):
                            try:
                                parsed = json.loads(pd)
                                if parsed.get("type") == "text" and parsed.get("text"):
                                    combined_text += parsed["text"] + "\n"
                            except (json.JSONDecodeError, TypeError):
                                pass
            else:
                for m in msgs:
                    d = m.get("data", "")
                    if isinstance(d, str):
                        try:
                            parsed = json.loads(d)
                            if parsed.get("role") == "assistant":
                                tokens = parsed.get("tokens", {})
                                return {
                                    "status": "ok",
                                    "text": combined_text.strip() or "[response captured in DB]",
                                    "parts": [],
                                    "role": "assistant",
                                    "tokens": tokens,
                                    "message_id": m.get("id", ""),
                                }
                        except (json.JSONDecodeError, TypeError):
                            pass

            if combined_text.strip():
                last_msg = msgs[-1]
                try:
                    msg_data = json.loads(last_msg.get("data", "{}"))
                    tokens = msg_data.get("tokens", {})
                except (json.JSONDecodeError, TypeError):
                    tokens = {}
                return {
                    "status": "ok",
                    "text": combined_text.strip(),
                    "parts": [],
                    "role": "assistant",
                    "tokens": tokens,
                    "message_id": last_msg.get("id", ""),
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


def query_opencode_db(db_path: Path, session_id: str) -> dict:
    if not db_path.exists():
        return {"error": f"DB not found at {db_path}"}
    from db_inspector import inspect_opencode_db

    return inspect_opencode_db(db_path, session_id)


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
