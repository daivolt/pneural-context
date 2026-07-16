from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import uvicorn
from fastapi import FastAPI

from . import pb_db
from .pb_config import PBConfig
from .pb_embeddings import EmbeddingClient, create_embedding_client
from .pb_engine import run_consolidation
from .pb_llm import LLMClient
from .pb_memoria import MemoriaBridge
from .routers import (
    anchors,
    archive,
    briefing,
    config,
    consolidation,
    context,
    costs,
    dashboard,
    decay,
    health,
    memory,
    papers,
    procedures,
    projects,
    recall,
    reindex,
    session,
)

logger = logging.getLogger("pneural_context.server")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    config: PBConfig = app.state.config

    if not config.database_url:
        config.database_url = os.environ.get("DATABASE_URL", "")
    if not config.database_url:
        raise RuntimeError("PNEURAL_DATABASE_URL or DATABASE_URL must be set")

    pool = await asyncpg.create_pool(config.database_url, min_size=2, max_size=10)
    app.state.pool = pool
    pb_db.init_pool(pool)

    app.state.llm_client = LLMClient(
        url=config.llm_url, model=config.llm_model, api_key=config.llm_api_key
    )

    embedding_client: EmbeddingClient | None = create_embedding_client(config)
    app.state.embedding_client = embedding_client
    if embedding_client:
        pb_db.init_embedding_client(embedding_client)
        logger.info("Embedding client initialized (backend=%s)", config.embed_backend)

    if config.memoria_enabled and config.memoria_url:
        app.state.memoria = MemoriaBridge(config.memoria_url)
    else:
        app.state.memoria = None

    schema_path = Path(__file__).parent / "pb_schema.sql"
    if schema_path.exists():
        async with pool.acquire() as conn:
            with open(schema_path) as f:
                await conn.execute(f.read())
        logger.info("Database schema applied")

    if embedding_client:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT a.atttypmod FROM pg_attribute a "
                "JOIN pg_class c ON a.attrelid = c.oid "
                "JOIN pg_type t ON a.atttypid = t.oid "
                "WHERE c.relname = 'pb_memory' AND a.attname = 'embedding' AND t.typname = 'vector'"
            )
            if row:
                db_dims = row["atttypmod"]
                if db_dims != config.embed_dimensions:
                    raise RuntimeError(
                        f"Embedding dimension mismatch: config={config.embed_dimensions}, "
                        f"DB schema={db_dims}. Change PNEURAL_EMBED_DIMENSIONS or recreate schema."
                    )
        logger.info("Embedding dimension validated (%d)", config.embed_dimensions)

    background_tasks: list[asyncio.Task] = []
    if config.decay_interval_seconds > 0:
        task = asyncio.create_task(_decay_loop(config.decay_interval_seconds, pool, config))
        background_tasks.append(task)
        app.state.background_tasks = background_tasks
    if config.consolidation_interval_seconds > 0:
        task = asyncio.create_task(
            _consolidation_loop(config.consolidation_interval_seconds, pool, app.state.llm_client)
        )
        background_tasks.append(task)
        app.state.background_tasks = background_tasks

    logger.info("pneural-context server started on %s:%s", config.host, config.port)
    yield

    for task in background_tasks:
        task.cancel()
    if app.state.llm_client:
        await app.state.llm_client.close()
    if app.state.embedding_client:
        await app.state.embedding_client.close()
    if pool:
        await pool.close()
    if app.state.memoria:
        await app.state.memoria.close()


async def _decay_loop(interval: float, pool: asyncpg.Pool, config: PBConfig) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            result = await pb_db.apply_decay(pool=pool)
            archive_result = await pb_db.archive_decay(
                pool=pool, threshold=config.archive_threshold
            )
            logger.info("Decay cycle: %s, archive: %s", result, archive_result)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Decay loop error")


async def _consolidation_loop(
    interval: float, pool: asyncpg.Pool, llm_client: LLMClient | None
) -> None:
    while True:
        try:
            await asyncio.sleep(interval)
            projects = await pb_db.get_all_projects(pool=pool)
            for project in projects:
                result = await run_consolidation(project, llm=llm_client, pool=pool)
                logger.info("Consolidation for %s: %s", project, result)
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Consolidation loop error")


def create_app(config_override: PBConfig | None = None) -> FastAPI:
    app_config = config_override or PBConfig.from_env()

    config_path = os.environ.get("PNEURAL_CONFIG_FILE")
    if config_path and Path(config_path).exists():
        app_config = PBConfig.load_from_file(config_path)

    app = FastAPI(
        title="pneural-context",
        version="0.1.0a1",
        description="Persistent neural context for LLMs",
        lifespan=lifespan,
    )

    app.state.config = app_config
    app.state.pool = None
    app.state.llm_client = None
    app.state.embedding_client = None
    app.state.memoria = None
    app.state.background_tasks = []

    app.include_router(health.router)
    app.include_router(memory.router)
    app.include_router(context.router)
    app.include_router(recall.router)
    app.include_router(procedures.router)
    app.include_router(consolidation.router)
    app.include_router(decay.router)
    app.include_router(archive.router)
    app.include_router(costs.router)
    app.include_router(session.router)
    app.include_router(anchors.router)
    app.include_router(briefing.router)
    app.include_router(papers.router)
    app.include_router(reindex.router)
    app.include_router(config.router)
    app.include_router(dashboard.router)
    app.include_router(projects.router)

    return app


app = create_app()


def main() -> None:
    cfg = PBConfig.from_env()
    uvicorn.run(
        "pneural_context.server:app",
        host=cfg.host,
        port=cfg.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
