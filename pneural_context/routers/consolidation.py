from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Request

from .. import pb_db
from ..deps import PoolDep
from ..pb_engine import run_consolidation

router = APIRouter(prefix="/api/consolidation", tags=["consolidation"])


@router.post("")
async def trigger_consolidation(body: dict, request: Request, pool: asyncpg.Pool = PoolDep) -> dict:
    project = body.get("project", "")
    llm_client = getattr(request.app.state, "llm_client", None)
    return await run_consolidation(project, llm=llm_client, pool=pool)


@router.get("")
async def get_consolidation(
    project: str, tier: str | None = None, pool: asyncpg.Pool = PoolDep
) -> list[dict]:
    return await pb_db.get_consolidated(project, tier=tier, pool=pool)


@router.get("/status")
async def consolidation_status(project: str, pool: asyncpg.Pool = PoolDep) -> dict:
    entries = await pb_db.get_consolidated(project, pool=pool)
    tiers: dict[str, int] = {}
    for e in entries:
        t = e.get("tier", "consolidated")
        tiers[t] = tiers.get(t, 0) + 1
    return {"project": project, "tiers": tiers, "total": len(entries)}
