from __future__ import annotations

import asyncpg

from ..pb_embeddings import EmbeddingClient

_pool: asyncpg.Pool | None = None
_embedding_client: EmbeddingClient | None = None


def init_pool(pool: asyncpg.Pool) -> None:
    global _pool
    _pool = pool


def init_embedding_client(client: EmbeddingClient | None) -> None:
    global _embedding_client
    _embedding_client = client


async def _get_pool(pool: asyncpg.Pool | None = None) -> asyncpg.Pool:
    p = pool or _pool
    if p is None:
        raise RuntimeError("Database pool not initialized")
    return p
