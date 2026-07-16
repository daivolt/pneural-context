from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from pneural_context.pb_embeddings import (
    EmbeddingClient,
    OllamaEmbeddingClient,
    PythonEmbeddingClient,
    _cache_key,
    _conversation_cache,
    _evict_cache,
    create_embedding_client,
)


class TestEmbeddingClient:
    def test_init(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        assert client.backend == "ollama"
        assert client.model == "nomic"

    @pytest.mark.asyncio
    async def test_embed_delegates(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        mock_inner = AsyncMock()
        mock_inner.embed = AsyncMock(return_value=[0.1, 0.2])
        client._client = mock_inner
        result = await client.embed("test text")
        assert result == [0.1, 0.2]

    @pytest.mark.asyncio
    async def test_embed_failure_returns_none(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        mock_inner = AsyncMock()
        mock_inner.embed = AsyncMock(side_effect=Exception("fail"))
        client._client = mock_inner
        result = await client.embed("test text")
        assert result is None

    @pytest.mark.asyncio
    async def test_embed_batch_delegates(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        mock_inner = AsyncMock()
        mock_inner.embed_batch = AsyncMock(return_value=[[0.1], [0.2]])
        client._client = mock_inner
        result = await client.embed_batch(["a", "b"])
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_embed_batch_failure(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        mock_inner = AsyncMock()
        mock_inner.embed_batch = AsyncMock(side_effect=Exception("fail"))
        client._client = mock_inner
        result = await client.embed_batch(["a", "b"])
        assert result == [None, None]

    @pytest.mark.asyncio
    async def test_close(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        mock_inner = AsyncMock()
        client._client = mock_inner
        await client.close()
        mock_inner.close.assert_called_once()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_no_client(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        await client.close()

    def test_get_client_ollama(self):
        client = EmbeddingClient("ollama", "http://localhost:11434", "nomic", 768, 32)
        inner = client._get_client()
        assert isinstance(inner, OllamaEmbeddingClient)

    def test_get_client_python(self):
        client = EmbeddingClient("python", "http://localhost:11434", "all-MiniLM-L6-v2", 384, 32)
        inner = client._get_client()
        assert isinstance(inner, PythonEmbeddingClient)


class TestOllamaEmbeddingClient:
    def test_init(self):
        client = OllamaEmbeddingClient("http://localhost:11434", "nomic")
        assert client.url == "http://localhost:11434"
        assert client.model == "nomic"


class TestConversationCache:
    def setup_method(self):
        _conversation_cache.clear()

    def test_cache_key_deterministic(self):
        key1 = _cache_key("project", "text")
        key2 = _cache_key("project", "text")
        assert key1 == key2

    def test_cache_key_different_inputs(self):
        key1 = _cache_key("project1", "text")
        key2 = _cache_key("project2", "text")
        assert key1 != key2

    def test_evict_cache_removes_expired(self):
        _conversation_cache["old"] = ([0.1], time.time() - 600)
        _conversation_cache["new"] = ([0.2], time.time())
        _evict_cache()
        assert "old" not in _conversation_cache
        assert "new" in _conversation_cache

    def test_evict_cache_respects_max_size(self):
        for i in range(10001):
            _conversation_cache[f"key_{i}"] = ([0.1], time.time())
        _evict_cache()
        assert len(_conversation_cache) <= 10000


class TestCreateEmbeddingClient:
    def test_create_with_empty_backend(self):
        config = MagicMock()
        config.embed_backend = ""
        result = create_embedding_client(config)
        assert result is None

    def test_create_with_ollama(self):
        config = MagicMock()
        config.embed_backend = "ollama"
        config.embed_url = "http://localhost:11434"
        config.embed_model = "nomic"
        config.embed_dimensions = 768
        config.embed_batch_size = 32
        result = create_embedding_client(config)
        assert isinstance(result, EmbeddingClient)
        assert result.backend == "ollama"

    @pytest.mark.asyncio
    async def test_get_conversation_embedding(self):
        from pneural_context.pb_embeddings import get_conversation_embedding

        mock_client = AsyncMock(spec=EmbeddingClient)
        mock_client.embed = AsyncMock(return_value=[0.1, 0.2, 0.3])
        _conversation_cache.clear()
        result = await get_conversation_embedding("p", "test conversation", mock_client)
        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_get_conversation_embedding_returns_none_on_failure(self):
        from pneural_context.pb_embeddings import get_conversation_embedding

        mock_client = AsyncMock(spec=EmbeddingClient)
        mock_client.embed = AsyncMock(return_value=None)
        _conversation_cache.clear()
        result = await get_conversation_embedding("p", "test conversation", mock_client)
        assert result is None
