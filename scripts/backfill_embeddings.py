#!/usr/bin/env python3
"""Backfill embeddings for pb_memory and pb_procedural_memory via Ollama."""

from __future__ import annotations

import argparse
import asyncio
import os
from pathlib import Path

import asyncpg

from pneural_context.db import pool as pool_mod
from pneural_context.db.search import reindex_table
from pneural_context.pb_embeddings import EmbeddingClient


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key not in os.environ:
            os.environ[key] = value


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--table", choices=["pb_memory", "pb_procedural_memory", "both"], default="both"
    )
    args = parser.parse_args()

    _load_env(Path(__file__).resolve().parent.parent / ".env")
    database_url = os.environ["PNEURAL_DATABASE_URL"]
    embed_url = os.environ.get("PNEURAL_EMBED_URL", "http://localhost:11434")
    embed_model = os.environ.get("PNEURAL_EMBED_MODEL", "nomic-embed-text")
    embed_dims = int(os.environ.get("PNEURAL_EMBED_DIMENSIONS", "768"))

    pool = await asyncpg.create_pool(database_url)
    pool_mod.init_pool(pool)
    client = EmbeddingClient(
        backend="ollama",
        url=embed_url,
        model=embed_model,
        dimensions=embed_dims,
        batch_size=32,
    )
    # smoke test the embedding service
    probe = await client.embed("health probe")
    if not probe:
        raise RuntimeError(f"Embedding service unavailable at {embed_url} (model {embed_model})")
    print(f"embedding service OK ({embed_model}, dims={len(probe)})")
    pool_mod.init_embedding_client(client)

    tables = ["pb_memory", "pb_procedural_memory"] if args.table == "both" else [args.table]
    for table in tables:
        col = "entry" if table == "pb_memory" else "task_pattern"
        before = await pool.fetchval(f"SELECT COUNT(*) FROM {table} WHERE embedding IS NULL")
        n = await reindex_table(table, col, batch_size=32, pool=pool)
        after = await pool.fetchval(f"SELECT COUNT(*) FROM {table} WHERE embedding IS NULL")
        print(f"{table}: backfilled {n} (null {before} -> {after})")

    await client.close()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
