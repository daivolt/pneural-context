from __future__ import annotations

import asyncpg
from fastapi import Depends, Request

from .pb_config import PBConfig
from .pb_embeddings import EmbeddingClient
from .pb_llm import LLMClient
from .pb_memoria import MemoriaBridge


async def get_pool(request: Request) -> asyncpg.Pool:
    pool: asyncpg.Pool | None = request.app.state.pool
    if pool is None:
        raise RuntimeError("Database pool not initialized")
    return pool


def get_config(request: Request) -> PBConfig:
    config: PBConfig | None = request.app.state.config
    if config is None:
        raise RuntimeError("Config not initialized")
    return config


def get_llm_client(request: Request) -> LLMClient | None:
    return getattr(request.app.state, "llm_client", None)


def get_embedding_client(request: Request) -> EmbeddingClient | None:
    return getattr(request.app.state, "embedding_client", None)


def get_memoria(request: Request) -> MemoriaBridge | None:
    return getattr(request.app.state, "memoria", None)


PoolDep = Depends(get_pool)
ConfigDep = Depends(get_config)
LLMDep = Depends(get_llm_client)
EmbeddingDep = Depends(get_embedding_client)
MemoriaDep = Depends(get_memoria)
