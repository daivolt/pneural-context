from __future__ import annotations

import asyncpg
from fastapi import APIRouter

from .. import pb_db
from ..deps import PoolDep

router = APIRouter(prefix="/api/papers", tags=["papers"])


@router.get("/search")
async def search_papers(q: str, limit: int = 5, pool: asyncpg.Pool = PoolDep) -> list[dict]:
    return await pb_db.search_papers(q, limit=limit, pool=pool)
