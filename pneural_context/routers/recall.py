from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, Request

from .. import pb_db
from ..deps import PoolDep

logger = logging.getLogger("pneural_context.routers.recall")

router = APIRouter(prefix="/api/recall", tags=["recall"])


@router.get("")
async def recall(
    request: Request,
    q: str,
    project: str | None = None,
    limit: int = 5,
    source: str | None = None,
    boost: bool = True,
    semantic: bool = False,
    pool: asyncpg.Pool = PoolDep,
) -> dict:
    embedding_client = getattr(request.app.state, "embedding_client", None)
    memoria = getattr(request.app.state, "memoria", None)
    results: list[dict] = []
    if project:
        if semantic and embedding_client:
            try:
                query_vec = await embedding_client.embed(q)
                if query_vec:
                    hybrid_results = await pb_db.hybrid_search_memory(
                        project, q, query_vec, limit, pool=pool
                    )
                    for e in hybrid_results:
                        results.append(
                            {
                                "type": "memory",
                                "project": project,
                                "text": e.get("entry", ""),
                                "score": e.get("rrf_score", e.get("rank", 0)),
                                "id": e.get("id"),
                            }
                        )
                        if boost:
                            await pb_db.touch_memory_access(project, e.get("id", 0), pool=pool)
            except Exception:
                logger.warning("Semantic recall failed, falling back to text search")
        if not results:
            entries = await pb_db.get_memory_entries_full(project, pool=pool)
            for e in entries:
                if q.lower() in e.get("entry", "").lower():
                    results.append(
                        {
                            "type": "memory",
                            "project": project,
                            "text": e["entry"],
                            "score": 1.0,
                            "id": e.get("id"),
                        }
                    )
                    if boost:
                        await pb_db.touch_memory_access(project, e.get("id", 0), pool=pool)
        results = results[:limit]
    if memoria and (not source or source == "sessions"):
        try:
            mem_results = await memoria.recall(q, project=project or "", limit=limit)
            results.extend(mem_results)
        except Exception:
            logger.warning("Memoria recall failed", exc_info=True)
    return {"query": q, "results": results[:limit], "count": len(results)}
