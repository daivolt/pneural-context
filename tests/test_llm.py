from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from pneural_context.pb_llm import LLMClient


@pytest.fixture
def llm_client():
    return LLMClient(url="http://localhost:12345/v1", model="test-model")


class TestLLMClient:
    def test_init(self, llm_client):
        assert llm_client.url == "http://localhost:12345/v1"
        assert llm_client.model == "test-model"
        assert llm_client._session is None

    @pytest.mark.asyncio
    async def test_classify_valid(self, llm_client):
        llm_client._chat = AsyncMock(return_value="concept")
        result = await llm_client.classify("some memory text")
        assert result == "concept"

    @pytest.mark.asyncio
    async def test_classify_invalid_fallback(self, llm_client):
        llm_client._chat = AsyncMock(return_value="this is a concept about things")
        result = await llm_client.classify("some memory text")
        assert result == "concept"

    @pytest.mark.asyncio
    async def test_classify_no_match(self, llm_client):
        llm_client._chat = AsyncMock(return_value="xyzzy")
        result = await llm_client.classify("some memory text")
        assert result == "temporal"

    @pytest.mark.asyncio
    async def test_consolidate_json(self, llm_client):
        llm_client._chat = AsyncMock(
            return_value='{"insights": ["test insight"], "patterns": [], "type": "concept", "priority": "normal"}'
        )
        result = await llm_client.consolidate([{"entry": "test", "memory_type": "concept"}])
        assert "insights" in result
        assert result["type"] == "concept"

    @pytest.mark.asyncio
    async def test_consolidate_markdown_json(self, llm_client):
        llm_client._chat = AsyncMock(
            return_value='```json\n{"insights": ["test"], "patterns": [], "type": "concept", "priority": "normal"}\n```'
        )
        result = await llm_client.consolidate([{"entry": "test", "memory_type": "concept"}])
        assert "insights" in result

    @pytest.mark.asyncio
    async def test_consolidate_invalid_json(self, llm_client):
        llm_client._chat = AsyncMock(return_value="not json at all")
        result = await llm_client.consolidate([{"entry": "test", "memory_type": "concept"}])
        assert result["insights"] == ["not json at all"]

    @pytest.mark.asyncio
    async def test_extract_procedure_json(self, llm_client):
        llm_client._chat = AsyncMock(
            return_value='{"task_pattern": "deploy app", "steps": ["step1", "step2"], "type": "devops"}'
        )
        result = await llm_client.extract_procedure("deploy app", result="success")
        assert result["task_pattern"] == "deploy app"

    @pytest.mark.asyncio
    async def test_extract_procedure_with_steps(self, llm_client):
        llm_client._chat = AsyncMock(return_value="invalid json")
        result = await llm_client.extract_procedure("task", steps=["a", "b"])
        assert "steps" in result

    @pytest.mark.asyncio
    async def test_generate_briefing(self, llm_client):
        llm_client._chat = AsyncMock(return_value="Briefing text")
        result = await llm_client.generate_briefing("context info")
        assert result == "Briefing text"

    @pytest.mark.asyncio
    async def test_summarize_session(self, llm_client):
        llm_client._chat = AsyncMock(return_value="Short summary")
        result = await llm_client.summarize_session(
            "Test Session", [{"role": "user", "content": "hello"}]
        )
        assert result == "Short summary"

    @pytest.mark.asyncio
    async def test_summarize_session_truncates(self, llm_client):
        long_result = "x" * 600
        llm_client._chat = AsyncMock(return_value=long_result)
        result = await llm_client.summarize_session("Test", [{"role": "user", "content": "hi"}])
        assert len(result) <= 503

    @pytest.mark.asyncio
    async def test_summarize_session_empty_messages(self, llm_client):
        result = await llm_client.summarize_session("Empty Session", [])
        assert result == "Empty Session"

    @pytest.mark.asyncio
    async def test_close(self, llm_client):
        mock_session = AsyncMock()
        mock_session.closed = False
        llm_client._session = mock_session
        await llm_client.close()
        mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_session_creates_new(self, llm_client):
        session = await llm_client._ensure_session()
        assert session is not None
        await session.close()
