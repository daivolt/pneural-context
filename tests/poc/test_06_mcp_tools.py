"""Test 06: MCP server tools — spawn MCP subprocess, call tools, verify HTTP side effects."""

from __future__ import annotations

import json
import subprocess
import sys
import time

import pytest

PROJECT = "poc-test"
PNEURAL_URL = "http://localhost:8779"


@pytest.fixture(scope="module")
def mcp_process():
    env = {
        **dict(__import__("os").environ),
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
    proc = subprocess.Popen(
        [sys.executable, "-m", "pneural_context.mcp_server.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )
    time.sleep(3)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


def test_mcp_initialize(mcp_process, tel):
    init_msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "poc-test", "version": "1.0.0"},
        },
    }
    try:
        result = _send_mcp(mcp_process, init_msg)
        tel.record("test_06_mcp_tools", "initialize_ok", result is not None)
    except Exception as e:
        tel.record("test_06_mcp_tools", "initialize_error", str(e))


def test_mcp_list_tools(mcp_process, tel):
    list_msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    result = _send_mcp(mcp_process, list_msg)
    if result and "tools" in result:
        tools = result["tools"]
        tool_names = [t["name"] for t in tools]
        tel.record("test_06_mcp_tools", "tools_listed", len(tools))
        tel.record("test_06_mcp_tools", "tool_names", tool_names)
        assert len(tools) >= 10, f"Expected at least 10 MCP tools, got {len(tools)}"
    else:
        tel.record("test_06_mcp_tools", "tools_list_error", str(result)[:200])


@pytest.mark.skipif(
    sys.platform == "win32", reason="MCP stdio subprocess I/O not supported on Windows"
)
def test_mcp_add_memory(mcp_process, api, tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 3,
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
    result = _send_mcp(mcp_process, call_msg)
    tel.record("test_06_mcp_tools", "add_memory_result", _truncate(str(result)[:300]))

    time.sleep(1)
    memories = api.get("/api/memory", params={"project": PROJECT}).json()
    mcp_entries = [m for m in memories if "MCP test" in m.get("entry", "")]
    tel.record("test_06_mcp_tools", "mcp_entry_found_via_api", len(mcp_entries))
    assert len(mcp_entries) > 0, "MCP add_memory should create entry visible via REST API"


def test_mcp_get_memory(mcp_process, tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "pb_get_memory",
            "arguments": {"project": PROJECT},
        },
    }
    result = _send_mcp(mcp_process, call_msg)
    tel.record("test_06_mcp_tools", "get_memory_result", _truncate(str(result)[:300]))


def test_mcp_recall(mcp_process, tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "pb_recall",
            "arguments": {"q": "MCP test", "project": PROJECT, "limit": 5},
        },
    }
    result = _send_mcp(mcp_process, call_msg)
    tel.record("test_06_mcp_tools", "recall_result", _truncate(str(result)[:300]))


def test_mcp_decay_status(mcp_process, tel):
    call_msg = {
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "pb_decay_status",
            "arguments": {"project": PROJECT},
        },
    }
    result = _send_mcp(mcp_process, call_msg)
    tel.record("test_06_mcp_tools", "decay_status_result", _truncate(str(result)[:300]))


def _send_mcp(proc, msg: dict) -> dict | None:
    payload = json.dumps(msg)
    content = f"Content-Length: {len(payload)}\r\n\r\n{payload}"
    try:
        proc.stdin.write(content.encode("utf-8"))
        proc.stdin.flush()
        response_line = b""
        while True:
            chunk = proc.stdout.read(1)
            if not chunk:
                return None
            response_line += chunk
            if response_line.endswith(b"\r\n\r\n"):
                break
        length_str = response_line.decode("utf-8")
        length = int(length_str.split("Content-Length: ")[1].split("\r\n")[0])
        body = proc.stdout.read(length)
        response = json.loads(body.decode("utf-8"))
        if "result" in response:
            return response["result"]
        if "error" in response:
            return {"error": response["error"]}
        return response
    except Exception as e:
        return {"exception": str(e)}


def _truncate(s: str, max_len: int = 200) -> str:
    return s[:max_len] + "..." if len(s) > max_len else s
