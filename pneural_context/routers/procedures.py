from __future__ import annotations

import logging

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from .. import pb_db
from ..deps import PoolDep
from ..models.procedures import AddProcedureRequest, OutcomeRequest

logger = logging.getLogger("pneural_context.routers.procedures")

router = APIRouter(prefix="/api/procedures", tags=["procedures"])


@router.post("")
async def add_procedure(body: AddProcedureRequest, pool: asyncpg.Pool = PoolDep) -> dict:
    proc_id = await pb_db.add_procedure(
        body.project, body.task_pattern, body.task_type, body.steps, body.proven_by, pool=pool
    )
    return {"id": proc_id}


@router.get("")
async def list_procedures(
    project: str, retired: bool = False, pool: asyncpg.Pool = PoolDep
) -> list[dict]:
    return await pb_db.list_procedures(project, retired=retired, pool=pool)


@router.get("/search")
async def search_procedures(
    request: Request,
    project: str,
    query: str,
    limit: int = 5,
    semantic: bool = False,
    pool: asyncpg.Pool = PoolDep,
) -> list[dict]:
    embedding_client = getattr(request.app.state, "embedding_client", None)
    if semantic and embedding_client:
        try:
            query_vec = await embedding_client.embed(query)
            if query_vec:
                return await pb_db.hybrid_search_procedures(
                    project, query, query_vec, limit, pool=pool
                )
        except Exception:
            logger.warning("Semantic procedure search failed, falling back to text")
    return await pb_db.search_procedures(project, query, limit=limit, pool=pool)


@router.post("/{proc_id}/outcome")
async def procedure_outcome(
    proc_id: int, body: OutcomeRequest, pool: asyncpg.Pool = PoolDep
) -> dict:
    result = await pb_db.update_procedure_outcome(proc_id, body.success, body.proven_by, pool=pool)
    if not result:
        raise HTTPException(404, "Procedure not found")
    return result


@router.post("/{proc_id}/retire")
async def retire_procedure(proc_id: int, pool: asyncpg.Pool = PoolDep) -> dict:
    ok = await pb_db.retire_procedure(proc_id, pool=pool)
    return {"ok": ok}
