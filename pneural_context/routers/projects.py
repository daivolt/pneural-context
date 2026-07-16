from __future__ import annotations

import asyncpg
from fastapi import APIRouter

from .. import pb_db
from ..deps import PoolDep

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
async def list_projects(pool: asyncpg.Pool = PoolDep) -> list[str]:
    return await pb_db.get_all_projects(pool=pool)
