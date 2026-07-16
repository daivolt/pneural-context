from __future__ import annotations

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from .. import pb_db
from ..deps import PoolDep

router = APIRouter(prefix="/api/reindex", tags=["reindex"])

TABLE_MAP = {
    "memory": ("pb_memory", "entry"),
    "consolidated": ("pb_consolidated_memory", "content"),
    "procedures": ("pb_procedural_memory", "task_pattern"),
    "papers": ("pb_papers", "text"),
}


@router.post("")
async def reindex(
    body: dict,
    request: Request,
    pool: asyncpg.Pool = PoolDep,
) -> dict:
    config = request.app.state.config
    embedding_client = getattr(request.app.state, "embedding_client", None)
    table = body.get("table", "all")
    valid_tables = {"memory", "consolidated", "procedures", "papers", "all"}
    if table not in valid_tables:
        raise HTTPException(400, f"table must be one of {valid_tables}")
    if not embedding_client:
        raise HTTPException(503, "Embedding client not configured")
    results: dict[str, dict] = {}
    tables_to_reindex = list(TABLE_MAP.keys()) if table == "all" else [table]
    for t in tables_to_reindex:
        db_table, text_col = TABLE_MAP[t]
        try:
            count = await pb_db.reindex_table(
                db_table, text_col, config.embed_batch_size, pool=pool
            )
            results[t] = {"reindexed": count}
        except Exception as e:
            results[t] = {"error": str(e)}
    return {"ok": True, "results": results}
