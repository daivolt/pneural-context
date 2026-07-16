"""Test 06: MCP server tools — spawn MCP subprocess, call tools, verify HTTP side effects.

Uses asyncio subprocess for Windows compatibility. The MCP Python SDK v1.28+
uses newline-delimited JSON (not Content-Length framing), so we send/receive
one JSON object per line. The server may also send notifications (e.g.
notifications/initialized after initialize) which we skip when looking for
responses.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import time

import pytest

PROJECT = "poc-test"
PNEURAL_URL = "http://localhost:8779"

MCP_ENV = {
    "PNEURAL_URL": PNEURAL_URL,
    "PB_MEMORY": "true",
    "PB_RECALL": "true",
    "PB_RED_INK": "true",
    "PB_BRIEFING": "true",
    "PB_PROCEDURAL": "true",
    "PB_TYPED_SECTIONS": "true",
    "PB_CONSOLIDATION": "true",
    "PB_ANCHORS": "true",
    "PB_DECAY": "true",
    "PB_COSTS": "true",
}


async def _mcp_call(messages: list[dict], timeout: float = 15.0) -> list[dict | None]:
    """Spawn an MCP subprocess, send messages, collect responses.

    Uses newline-delimited JSON protocol (MCP SDK v1.28+).
    After sending each message, we read lines until we get a response
    with a matching id (skipping notifications which have no id field).
    """
    env = {**os.environ, **MCP_ENV}
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "pneural_context.mcp_server.server",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    await asyncio.sleep(3)

    results: list[dict | None] = []

    for msg in messages:
        payload = json.dumps(msg, separators=(",", ":")) + "\n"

        try:
            proc.stdin.write(payload.encode("utf-8"))
            await proc.stdin.drain()
        except ConnectionResetError:
            results.append({"error": "ConnectionResetError writing to MCP stdin"})
            break

        # Read lines until we get a response with a matching id
        # Notifications (no id field) are skipped
        msg_id = msg.get("id")
        found = False
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            try:
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining <= 0:
                    break
                line = await asyncio.wait_for(
                    proc.stdout.readline(), timeout=min(remaining, timeout)
                )
                if not line:
                    results.append({"error": "MCP stdout closed"})
                    found = True
                    break
            except TimeoutError:
                results.append({"error": "timeout reading MCP response"})
                found = True
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            try:
                response = json.loads(line_str)
            except json.JSONDecodeError:
                continue

            # Skip notifications (no "id" field)
            if "id" not in response:
                continue

            # Check if this response matches our request id
            if response.get("id") == msg_id:
                if "result" in response:
                    results.append(response["result"])
                elif "error" in response:
                    results.append({"error": response["error"]})
                else:
                    results.append(response)
                found = True
                break
            # Response with different id — still capture it
            elif "result" in response:
                results.append(response["result"])
                found = True
                break
            elif "error" in response:
                results.append({"error": response["error"]})
                found = True
                break

        if not found:
            results.append({"error": "no matching response received"})

    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=5)
    except (TimeoutError, ProcessLookupError):
        try:
            proc.kill()
            await proc.wait()
        except ProcessLookupError:
            pass

    return results


def mcp_call(messages: list[dict]) -> list[dict | None]:
    """Sync wrapper for _mcp_call."""
    return asyncio.run(_mcp_call(messages))


INIT_MSG = {
    "jsonrpc": "2.0",
    "id": 0,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "poc-test", "version": "1.0.0"},
    },
}

INITIALIZED_MSG = {
    "jsonrpc": "2.0",
    "method": "notifications/initialized",
}

TOOLS_LIST_MSG = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list",
    "params": {},
}


def test_mcp_initialize(tel):
    results = mcp_call([INIT_MSG])
    result = results[0] if results else None
    tel.record(
        "test_06_mcp_tools", "initialize_ok", result is not None and "error" not in (result or {})
    )
    assert result is not None, f"MCP initialize failed: {results}"
    assert "error" not in (result or {}), f"MCP initialize error: {result}"


def test_mcp_list_tools(tel):
    results = mcp_call([INIT_MSG, INITIALIZED_MSG, TOOLS_LIST_MSG])
    init_result = results[0] if len(results) > 0 else None
    tools_result = results[-1] if len(results) > 1 else None

    tel.record(
        "test_06_mcp_tools",
        "initialize_for_list_ok",
        init_result is not None and "error" not in (init_result or {}),
    )

    if tools_result and "tools" in tools_result:
        tools = tools_result["tools"]
        tool_names = [t["name"] for t in tools]
        tel.record("test_06_mcp_tools", "tools_listed", len(tools))
        tel.record("test_06_mcp_tools", "tool_names", tool_names)
        assert len(tools) >= 10, f"Expected at least 10 MCP tools, got {len(tools)}"
    else:
        tel.record("test_06_mcp_tools", "tools_list_error", str(tools_result)[:200])
        pytest.fail(f"tools/list failed: {tools_result}")


def test_mcp_add_memory(api, tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "pb_add_memory",
            "arguments": {
                "project": PROJECT,
                "text": "MCP test: pneural-context supports MCP tool calls",
                "priority": "normal",
            },
        },
    }
    results = mcp_call([INIT_MSG, INITIALIZED_MSG, call_msg])
    result = results[-1] if results else None
    tel.record("test_06_mcp_tools", "add_memory_result", _truncate(str(result)[:300]))

    time.sleep(1)
    memories = api.get("/api/memory", params={"project": PROJECT}).json()
    mcp_entries = [m for m in memories if "MCP test" in m.get("entry", "")]
    tel.record("test_06_mcp_tools", "mcp_entry_found_via_api", len(mcp_entries))
    assert len(mcp_entries) > 0, "MCP add_memory should create entry visible via REST API"


def test_mcp_get_memory(tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "pb_get_memory",
            "arguments": {"project": PROJECT},
        },
    }
    results = mcp_call([INIT_MSG, INITIALIZED_MSG, call_msg])
    result = results[-1] if results else None
    tel.record("test_06_mcp_tools", "get_memory_result", _truncate(str(result)[:300]))


def test_mcp_recall(tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "pb_recall",
            "arguments": {"q": "MCP test", "project": PROJECT, "limit": 5},
        },
    }
    results = mcp_call([INIT_MSG, INITIALIZED_MSG, call_msg])
    result = results[-1] if results else None
    tel.record("test_06_mcp_tools", "recall_result", _truncate(str(result)[:300]))


def test_mcp_decay_status(tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "pb_decay_status",
            "arguments": {"project": PROJECT},
        },
    }
    results = mcp_call([INIT_MSG, INITIALIZED_MSG, call_msg])
    result = results[-1] if results else None
    tel.record("test_06_mcp_tools", "decay_status_result", _truncate(str(result)[:300]))


def _truncate(s: str, max_len: int = 200) -> str:
    return s[:max_len] + "..." if len(s) > max_len else s
