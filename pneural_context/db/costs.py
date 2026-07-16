from __future__ import annotations

import json

import asyncpg

from .pool import _get_pool


async def record_memory_cost(
    project: str,
    session_id: str = "",
    tokens_injected: int = 0,
    tokens_saved_injection: int = 0,
    tokens_saved_forgetting: int = 0,
    context_type: str = "full",
    task_outcome: str = "",
    breakdown: dict | None = None,
    pool: asyncpg.Pool | None = None,
) -> int:
    p = await _get_pool(pool)
    bd = json.dumps(breakdown) if breakdown else None
    row = await p.fetchrow(
        """INSERT INTO pb_memory_costs
           (session_id, project, tokens_injected, tokens_saved_injection,
            tokens_saved_forgetting, context_type, task_outcome, breakdown)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb)
           RETURNING id""",
        session_id,
        project,
        tokens_injected,
        tokens_saved_injection,
        tokens_saved_forgetting,
        context_type,
        task_outcome or None,
        bd,
    )
    return row["id"]


async def get_memory_costs(
    project: str, days: int = 30, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, session_id, project, tokens_injected,
                  tokens_saved_injection, tokens_saved_forgetting,
                  context_type, task_outcome, created_at, breakdown
           FROM pb_memory_costs
           WHERE project = $1
                 AND created_at > extract(epoch from now()) - $2 * 86400
           ORDER BY created_at DESC""",
        project,
        days,
    )
    return [dict(r) for r in rows]


async def get_memory_cost_summary(
    project: str, days: int = 30, pool: asyncpg.Pool | None = None
) -> dict:
    p = await _get_pool(pool)
    row = await p.fetchrow(
        """SELECT
               COUNT(*) as total_records,
               SUM(tokens_injected) as total_injected,
               SUM(tokens_saved_injection) as total_saved_injection,
               SUM(tokens_saved_forgetting) as total_saved_forgetting,
               AVG(tokens_injected) as avg_injected
           FROM pb_memory_costs
           WHERE project = $1
                 AND created_at > extract(epoch from now()) - $2 * 86400""",
        project,
        days,
    )
    return dict(row) if row else {}
