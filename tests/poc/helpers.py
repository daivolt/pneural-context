"""PoC test helpers — opencode session/message utilities."""

from __future__ import annotations

import time

import httpx


def oc_create_session(oc: httpx.Client, title: str = "poc-test") -> str | None:
    r = oc.post("/session", json={"title": title})
    if r.status_code not in (200, 201):
        return None
    data = r.json()
    return data.get("id") or data.get("session_id")


def oc_send_message(
    oc: httpx.Client, sid: str, text: str, poll_timeout: float = 60.0, poll_interval: float = 2.0
) -> dict | None:
    r = oc.post(
        f"/session/{sid}/prompt_async",
        json={"parts": [{"type": "text", "text": text}]},
    )
    if r.status_code not in (200, 204):
        return {"status_code": r.status_code, "error": r.text[:500]}

    deadline = time.monotonic() + poll_timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        msgs_r = oc.get(f"/session/{sid}/message")
        if msgs_r.status_code != 200:
            continue
        msgs = msgs_r.json()
        if not isinstance(msgs, list) or len(msgs) < 2:
            continue
        last = msgs[-1]
        parts = last.get("parts", [])
        if parts:
            texts = [p.get("text", "") for p in parts if p.get("type") == "text"]
            combined = " ".join(texts)
            if combined.strip():
                return {
                    "status_code": 200,
                    "role": last.get("info", {}).get("role", ""),
                    "text": combined,
                    "parts": parts,
                    "tokens": last.get("info", {}).get("tokens", {}),
                }

    return {"status_code": 200, "text": "", "polled_timeout": True}
