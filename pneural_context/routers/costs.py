from __future__ import annotations

import asyncpg
from fastapi import APIRouter

from .. import pb_db
from ..deps import PoolDep
from ..models.costs import RecordCostRequest

router = APIRouter(prefix="/api/costs", tags=["costs"])


@router.post("")
async def record_cost(body: RecordCostRequest, pool: asyncpg.Pool = PoolDep) -> dict:
    await pb_db.record_memory_cost(
        project=body.project,
        session_id=body.session_id,
        tokens_injected=body.tokens_injected,
        tokens_saved_injection=body.tokens_saved_injection,
        tokens_saved_forgetting=body.tokens_saved_forgetting,
        context_type=body.context_type,
        task_outcome=body.task_outcome,
        breakdown=body.breakdown,
        pool=pool,
    )
    return {"ok": True}


@router.get("")
async def get_costs(project: str, days: int = 30, pool: asyncpg.Pool = PoolDep) -> list[dict]:
    return await pb_db.get_memory_costs(project, days=days, pool=pool)


@router.get("/summary")
async def cost_summary(project: str, days: int = 30, pool: asyncpg.Pool = PoolDep) -> dict:
    return await pb_db.get_memory_cost_summary(project, days=days, pool=pool)


@router.get("/trends")
async def cost_trends(project: str, days: int = 30, pool: asyncpg.Pool = PoolDep) -> dict:
    costs = await pb_db.get_memory_costs(project, days=days, pool=pool)
    return {
        "project": project,
        "days": days,
        "records": len(costs),
        "data": costs[:100],
    }
