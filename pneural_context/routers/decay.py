from __future__ import annotations

import asyncpg
from fastapi import APIRouter

from .. import pb_db
from ..deps import PoolDep

router = APIRouter(prefix="/api/decay", tags=["decay"])


@router.post("")
async def trigger_decay(pool: asyncpg.Pool = PoolDep) -> dict:
    return await pb_db.apply_decay(pool=pool)


@router.post("/archive")
async def trigger_archive_decay(threshold: float = 0.1, pool: asyncpg.Pool = PoolDep) -> dict:
    return await pb_db.archive_decay(pool=pool, threshold=threshold)


@router.get("/status")
async def decay_status(project: str, pool: asyncpg.Pool = PoolDep) -> dict:
    return await pb_db.get_decay_status(project, pool=pool)
