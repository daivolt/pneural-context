from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Request

from ..deps import PoolDep
from ..pb_engine import generate_briefing

router = APIRouter(prefix="/api/briefing", tags=["briefing"])


@router.get("")
async def briefing(
    request: Request, project: str, task: str = "", pool: asyncpg.Pool = PoolDep
) -> dict:
    llm_client = getattr(request.app.state, "llm_client", None)
    return await generate_briefing(project, task, llm=llm_client, pool=pool)
