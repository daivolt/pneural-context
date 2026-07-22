from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from pneural_context.pb_memoria import MemoriaBridge


def _make_bridge() -> MemoriaBridge:
    return MemoriaBridge(url="http://localhost:9999")


def _mock_response(json_data: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json = MagicMock(return_value=json_data)
    return resp


def _attach_client(bridge: MemoriaBridge) -> AsyncMock:
    mock_client = AsyncMock()
    mock_client.is_closed = False
    bridge._client = mock_client
    return mock_client


@pytest.mark.asyncio
async def test_recall():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(return_value=_mock_response({"results": [{"id": 1, "entry": "test"}]}))
    result = await bridge.recall("test query", project="p")
    assert result == [{"id": 1, "entry": "test"}]
    client.get.assert_awaited_once()
    call_url = client.get.call_args[0][0]
    assert call_url == "http://localhost:9999/recall"
    await bridge.close()


@pytest.mark.asyncio
async def test_recall_error_returns_empty():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(side_effect=httpx.RequestError("connection error"))
    result = await bridge.recall("test query", project="p")
    assert result == []
    await bridge.close()


@pytest.mark.asyncio
async def test_get_review():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(return_value=_mock_response({"sessions": [{"id": "s1"}]}))
    result = await bridge.get_review("p")
    assert result == [{"id": "s1"}]
    call_url = client.get.call_args[0][0]
    assert call_url == "http://localhost:9999/review"
    await bridge.close()


@pytest.mark.asyncio
async def test_add_memory():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.post = AsyncMock(return_value=_mock_response({"status": "ok", "index": 5}))
    result = await bridge.add_memory(
        "p", "hello world", priority="important", memory_type="concept"
    )
    assert result == {"status": "ok", "index": 5}
    call_url = client.post.call_args[0][0]
    assert call_url == "http://localhost:9999/memory/p"
    payload = client.post.call_args[1]["json"]
    assert payload["text"] == "hello world"
    assert payload["priority"] == "important"
    assert payload["memory_type"] == "concept"
    await bridge.close()


@pytest.mark.asyncio
async def test_add_memory_error_returns_none():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.post = AsyncMock(side_effect=httpx.RequestError("fail"))
    result = await bridge.add_memory("p", "text")
    assert result is None
    await bridge.close()


@pytest.mark.asyncio
async def test_get_memory_full():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(return_value=_mock_response({"entries": [{"idx": 0, "text": "m1"}]}))
    result = await bridge.get_memory_full("p")
    assert result == [{"idx": 0, "text": "m1"}]
    call_url = client.get.call_args[0][0]
    assert call_url == "http://localhost:9999/memory/p/full"
    await bridge.close()


@pytest.mark.asyncio
async def test_get_red_ink():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(return_value=_mock_response({"entries": [{"idx": 0, "text": "red"}]}))
    result = await bridge.get_red_ink("p", min_strength=0.5)
    assert result == [{"idx": 0, "text": "red"}]
    call_args = client.get.call_args
    assert call_args[0][0] == "http://localhost:9999/red-ink/p"
    assert call_args[1]["params"]["min_strength"] == 0.5
    await bridge.close()


@pytest.mark.asyncio
async def test_get_context():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(
        return_value=_mock_response({"markdown": "# context", "typed_sections": {}})
    )
    result = await bridge.get_context("p")
    assert result == {"markdown": "# context", "typed_sections": {}}
    call_url = client.get.call_args[0][0]
    assert call_url == "http://localhost:9999/ctx/p"
    await bridge.close()


@pytest.mark.asyncio
async def test_trigger_consolidation():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.post = AsyncMock(return_value=_mock_response({"status": "ok", "promoted": 3}))
    result = await bridge.trigger_consolidation("p")
    assert result == {"status": "ok", "promoted": 3}
    call_url = client.post.call_args[0][0]
    assert call_url == "http://localhost:9999/consolidation/p/trigger"
    await bridge.close()


@pytest.mark.asyncio
async def test_register_peer():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.post = AsyncMock(return_value=_mock_response({"status": "registered"}))
    result = await bridge.register_peer("pneural-context", "http://localhost:8778")
    assert result == {"status": "registered"}
    call_url = client.post.call_args[0][0]
    assert call_url == "http://localhost:9999/federation/peers"
    payload = client.post.call_args[1]["json"]
    assert payload == {"name": "pneural-context", "url": "http://localhost:8778"}
    await bridge.close()


@pytest.mark.asyncio
async def test_close():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    await bridge.close()
    client.aclose.assert_awaited_once()


@pytest.mark.asyncio
async def test_close_no_client():
    bridge = _make_bridge()
    bridge._client = None
    await bridge.close()


@pytest.mark.asyncio
async def test_ensure_client_creates_new():
    bridge = _make_bridge()
    client = await bridge._ensure_client()
    assert client is not None
    await client.aclose()


@pytest.mark.asyncio
async def test_recall_no_project_param():
    bridge = _make_bridge()
    client = _attach_client(bridge)
    client.get = AsyncMock(return_value=_mock_response({"results": []}))
    await bridge.recall("test query")
    call_kwargs = client.get.call_args[1]
    assert "project" not in call_kwargs.get("params", {})
    await bridge.close()
