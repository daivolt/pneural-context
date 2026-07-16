from __future__ import annotations

import asyncpg

from .pool import _get_pool


async def get_all_projects(pool: asyncpg.Pool | None = None) -> list[str]:
    p = await _get_pool(pool)
    rows = await p.fetch("SELECT DISTINCT project FROM pb_memory ORDER BY project")
    return [r["project"] for r in rows]
