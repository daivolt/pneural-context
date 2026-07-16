from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from pneural_context.pb_memoria import MemoriaBridge


@pytest.mark.asyncio
async def test_recall():
    bridge = MemoriaBridge(url="http://localhost:9999")
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"results": [{"id": 1, "entry": "test"}]})
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False
    bridge._client = mock_client
    result = await bridge.recall("test query", project="p")
    assert len(result) == 1
    await bridge.close()


@pytest.mark.asyncio
async def test_get_sessions():
    bridge = MemoriaBridge(url="http://localhost:9999")
    mock_client = AsyncMock()
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json = MagicMock(return_value={"sessions": [{"id": "s1"}]})
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.is_closed = False
    bridge._client = mock_client
    result = await bridge.get_sessions("p")
    assert len(result) == 1
    await bridge.close()


@pytest.mark.asyncio
async def test_close():
    bridge = MemoriaBridge(url="http://localhost:9999")
    mock_client = AsyncMock()
    mock_client.is_closed = False
    bridge._client = mock_client
    await bridge.close()
    mock_client.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_close_no_client():
    bridge = MemoriaBridge(url="http://localhost:9999")
    bridge._client = None
    await bridge.close()


@pytest.mark.asyncio
async def test_ensure_client_creates_new():
    bridge = MemoriaBridge(url="http://localhost:9999")
    client = await bridge._ensure_client()
    assert client is not None
    await client.aclose()
