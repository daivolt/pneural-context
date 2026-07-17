"""Conversation runner — sends prompts to opencode serve, then extracts responses from DB.

Strategy:
1. Send all prompts via /session/{id}/prompt_async
2. Wait for each prompt to be processed (poll DB for new messages)
3. Extract response text and metadata from the opencode SQLite DB
4. Save response text files for faithfulness/quality analysis

The opencode serve API is asynchronous — prompt_async returns 204 immediately.
Responses appear in the DB once the LLM finishes generating. We poll the DB
directly rather than the HTTP API because the DB always has the latest data.
"""

from __future__ import annotations

import json
import shutil
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
OPENCODE_DB_PATH = Path(r"C:\Users\daivolt\.local\share\opencode\opencode.db")

POLL_INTERVAL = 5.0
POLL_TIMEOUT = 180.0


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
        if isinstance(entries, list):
            for e in entries:
                eid = e.get("id") or e.get("entry_id")
                if eid:
                    client.delete(f"/api/memory/{eid}", params={"project": "poc-benchmark"})
    print("  [OK] Cleaned benchmark data")


def _read_db_responses(session_id: str, expected_turns: int) -> list[dict[str, Any]]:
    """Read responses from the opencode SQLite DB for a given session."""
    conn = sqlite3.connect(str(OPENCODE_DB_PATH))
    try:
        messages = conn.execute(
            "SELECT id, data FROM message WHERE session_id = ? ORDER BY time_created",
            (session_id,),
        ).fetchall()
        print(f"    DB: {len(messages)} messages for session {session_id}")

        results = []
        assistant_msgs = []
        for msg_id, msg_data in messages:
            if not msg_data:
                continue
            try:
                parsed = json.loads(msg_data)
            except (json.JSONDecodeError, TypeError):
                continue
            if parsed.get("role") == "assistant":
                assistant_msgs.append((msg_id, parsed))

        for msg_id, parsed in assistant_msgs:
            parts = conn.execute(
                "SELECT data FROM part WHERE message_id = ? ORDER BY time_created",
                (msg_id,),
            ).fetchall()
            texts = []
            for (part_data,) in parts:
                if not part_data:
                    continue
                try:
                    pdata = json.loads(part_data)
                    if pdata.get("type") == "text" and pdata.get("text", "").strip():
                        texts.append(pdata["text"].strip())
                except (json.JSONDecodeError, TypeError):
                    pass

            combined = "\n".join(texts)
            tokens = parsed.get("tokens", {})
            results.append(
                {
                    "text": combined,
                    "tokens": tokens,
                    "message_id": msg_id,
                    "has_pneural_ctx": "PNEURAL_CTX" in str(parsed),
                }
            )

        return results
    finally:
        conn.close()


class ConversationRunner:
    def __init__(self, arm: str, project: str = "poc-benchmark"):
        assert arm in ("control", "treatment")
        self.arm = arm
        self.project = project
        self.client = httpx.Client(base_url=OPENCODE_URL, timeout=30.0)
        self.session_id: str | None = None
        self.responses: list[dict[str, Any]] = []

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

    def send_prompt(self, text: str) -> None:
        """Send a prompt asynchronously. Does NOT wait for response."""
        if not self.session_id:
            raise RuntimeError("No session ID")
        r = self.client.post(
            f"/session/{self.session_id}/prompt_async",
            json={"parts": [{"type": "text", "text": text}]},
        )
        print(f"    [{self.arm}] prompt_async: status={r.status_code}")

    def wait_for_responses(self, num_prompts: int, timeout: float = POLL_TIMEOUT) -> list[dict]:
        """Wait until we have at least num_prompts assistant responses in the DB."""
        print(f"  [{self.arm}] Waiting for {num_prompts} responses (timeout={timeout}s)...")
        deadline = time.monotonic() + timeout
        last_count = 0

        while time.monotonic() < deadline:
            time.sleep(POLL_INTERVAL)
            remaining = deadline - time.monotonic()

            try:
                conn = sqlite3.connect(str(OPENCODE_DB_PATH))
                count = conn.execute(
                    "SELECT COUNT(*) FROM message WHERE session_id = ? AND data LIKE '%assistant%'",
                    (self.session_id,),
                ).fetchone()[0]
                conn.close()
            except Exception as e:
                print(f"    [{self.arm}] DB error: {e}")
                continue

            if count != last_count:
                print(
                    f"    [{self.arm}] {count}/{num_prompts} responses ({remaining:.0f}s remaining)"
                )
                last_count = count

            if count >= num_prompts:
                print(f"  [{self.arm}] All {num_prompts} responses received!")
                return _read_db_responses(self.session_id, num_prompts)

        print(f"  [{self.arm}] Timeout: got {last_count}/{num_prompts} responses")
        return _read_db_responses(self.session_id, num_prompts)

    def run_conversation(self, prompts: list[str]) -> list[dict]:
        """Send all prompts and wait for responses via DB polling."""
        # Send all prompts with a delay between each
        for i, prompt in enumerate(prompts):
            print(f"\n  [{self.arm}] === Turn {i + 1}/{len(prompts)} ===")
            print(f"    [{self.arm}] Prompt: {prompt[:80]}...")
            self.send_prompt(prompt)
            # Wait for the LLM to process before sending next prompt
            # (opencode processes one prompt at a time)
            wait_time = 60.0 if i == 0 else 45.0  # First prompt might take longer
            print(f"    [{self.arm}] Waiting {wait_time}s for LLM to process...")
            time.sleep(wait_time)

        # Now wait for all responses
        responses = self.wait_for_responses(len(prompts), timeout=120.0)

        # Build results
        results = []
        for i, prompt in enumerate(prompts):
            resp = responses[i] if i < len(responses) else {"text": "", "tokens": {}}
            result = {
                "turn": i + 1,
                "prompt": prompt,
                "status": "ok" if resp.get("text") else "empty",
                "text": resp.get("text", ""),
                "tokens": resp.get("tokens", {}),
                "message_id": resp.get("message_id", ""),
                "has_pneural_ctx": resp.get("has_pneural_ctx", False),
            }
            results.append(result)

            out_dir = CONVERSATION_DIR / self.arm
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / f"turn_{i + 1:02d}_prompt.txt").write_text(prompt, encoding="utf-8")
            (out_dir / f"turn_{i + 1:02d}_response.txt").write_text(
                result["text"], encoding="utf-8"
            )

        self.responses = results
        return results

    def close(self) -> None:
        self.client.close()


def copy_opencode_db(suffix: str = "treatment") -> Path:
    """Copy the opencode DB locally."""
    dest = LOGS_DIR / f"{suffix}_opencode.db"
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    src = OPENCODE_DB_PATH
    if not src.exists():
        print(f"  [WARN] opencode DB not found at {src}")
        return dest
    shutil.copy2(str(src), str(dest))
    print(f"  Copied opencode DB ({dest.stat().st_size} bytes)")
    return dest


if __name__ == "__main__":
    prompts = load_conversation()
    print(f"Loaded {len(prompts)} prompts")

    runner = ConversationRunner("treatment")
    try:
        sid = runner.create_session()
        results = runner.run_conversation(prompts)
        print(f"\nCompleted {len(results)} turns")
        for r in results:
            tokens = r.get("tokens", {})
            text_len = len(r.get("text", ""))
            ctx = "YES" if r.get("has_pneural_ctx") else "NO"
            print(
                f"  Turn {r['turn']}: status={r['status']}, "
                f"tokens_in={tokens.get('input', '?')}, "
                f"tokens_out={tokens.get('output', '?')}, "
                f"text_len={text_len}, PNEURAL_CTX={ctx}"
            )
    finally:
        runner.close()
