from __future__ import annotations

import asyncpg
from fastapi import APIRouter

from ..deps import PoolDep
from ..pb_engine import generate_anchors

router = APIRouter(prefix="/api/anchors", tags=["anchors"])


@router.get("")
async def anchors(project: str, pool: asyncpg.Pool = PoolDep) -> dict:
    return await generate_anchors(project, pool=pool)
