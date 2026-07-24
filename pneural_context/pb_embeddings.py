from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import aiohttp

logger = logging.getLogger("pneural_context.pb_embeddings")


class EmbeddingClient:
    def __init__(self, backend: str, url: str, model: str, dimensions: int, batch_size: int):
        self.backend = backend
        self.url = url.rstrip("/")
        self.model = model
        self.dimensions = dimensions
        self.batch_size = batch_size
        self._client: OllamaEmbeddingClient | PythonEmbeddingClient | None = None

    def _get_client(self) -> OllamaEmbeddingClient | PythonEmbeddingClient:
        if self._client is None:
            if self.backend == "python":
                self._client = PythonEmbeddingClient(self.model, self.dimensions)
            else:
                self._client = OllamaEmbeddingClient(self.url, self.model)
        return self._client

    async def embed(self, text: str) -> list[float] | None:
        try:
            return await self._get_client().embed(text)
        except Exception as exc:
            logger.warning("Swallowed exception: %s", exc, exc_info=True)
            logger.warning("Embedding failed for text (%d chars)", len(text), exc_info=True)
            return None

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        try:
            return await self._get_client().embed_batch(texts)
        except Exception as exc:
            logger.warning("Swallowed exception: %s", exc, exc_info=True)
            logger.warning("Batch embedding failed (%d texts)", len(texts), exc_info=True)
            return [None] * len(texts)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


class OllamaEmbeddingClient:
    def __init__(self, url: str, model: str):
        self.url = url.rstrip("/")
        self.model = model
        self._session: aiohttp.ClientSession | None = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def embed(self, text: str) -> list[float]:
        session = await self._ensure_session()
        async with session.post(
            f"{self.url}/api/embeddings",
            json={"model": self.model, "prompt": text},
        ) as resp:
            resp.raise_for_status()
            data = await resp.json()
            return list(data["embedding"])

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        results: list[list[float] | None] = []
        for text in texts:
            try:
                vec = await self.embed(text)
                results.append(vec)
            except Exception as exc:
                logger.warning("Swallowed exception: %s", exc, exc_info=True)
                logger.warning("Ollama embed failed for text (%d chars)", len(text))
                results.append(None)
        return results

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()


class PythonEmbeddingClient:
    def __init__(self, model: str, dimensions: int):
        self.model = model
        self.dimensions = dimensions
        self._model: Any = None

    def _load_model(self) -> None:
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model)
            except ImportError:
                raise RuntimeError(
                    "sentence-transformers not installed. "
                    "Install with: pip install pneural-context[embeddings]"
                ) from None

    async def embed(self, text: str) -> list[float]:
        self._load_model()
        import asyncio

        loop = asyncio.get_running_loop()
        vec = await loop.run_in_executor(None, self._model.encode, text)
        return list(vec.tolist())

    async def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        self._load_model()
        import asyncio

        loop = asyncio.get_running_loop()
        vectors = await loop.run_in_executor(None, self._model.encode, texts)
        results: list[list[float] | None] = []
        for i, vec in enumerate(vectors):
            try:
                results.append(vec.tolist() if hasattr(vec, "tolist") else list(vec))
            except Exception as exc:
                logger.warning("Swallowed exception: %s", exc, exc_info=True)
                logger.warning("Python embed failed at index %d", i)
                results.append(None)
        return results

    async def close(self) -> None:
        pass


_conversation_cache: dict[str, tuple[list[float], float]] = {}
_CACHE_TTL = 300.0
_CACHE_MAX_SIZE = 10000


def _evict_cache() -> None:
    now = time.time()
    expired = [k for k, (_, ts) in _conversation_cache.items() if now - ts >= _CACHE_TTL]
    for k in expired:
        del _conversation_cache[k]
    if len(_conversation_cache) > _CACHE_MAX_SIZE:
        sorted_keys = sorted(_conversation_cache.keys(), key=lambda k: _conversation_cache[k][1])
        to_remove = len(_conversation_cache) - _CACHE_MAX_SIZE
        for k in sorted_keys[:to_remove]:
            del _conversation_cache[k]


def _cache_key(project: str, conversation: str) -> str:
    raw = f"{project}:{conversation}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def get_conversation_embedding(
    project: str, conversation: str, client: EmbeddingClient
) -> list[float] | None:
    key = _cache_key(project, conversation)
    now = time.time()
    if key in _conversation_cache:
        cached_vec, ts = _conversation_cache[key]
        if now - ts < _CACHE_TTL:
            return cached_vec
    result = await client.embed(conversation)
    if result is None:
        return None
    _conversation_cache[key] = (result, now)
    _evict_cache()
    return result


def create_embedding_client(config: Any) -> EmbeddingClient | None:
    if not config.embed_backend:
        return None
    try:
        return EmbeddingClient(
            backend=config.embed_backend,
            url=config.embed_url,
            model=config.embed_model,
            dimensions=config.embed_dimensions,
            batch_size=config.embed_batch_size,
        )
    except Exception as exc:
        logger.warning("Swallowed exception: %s", exc, exc_info=True)
        logger.warning("Failed to create embedding client", exc_info=True)
        return None
