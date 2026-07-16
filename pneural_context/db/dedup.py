from __future__ import annotations

import asyncpg

from .pool import _get_pool


async def dedup_context_entries(
    project: str,
    conversation_vec: list[float],
    threshold_high: float = 0.85,
    threshold_low: float = 0.55,
    limit: int = 200,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    vec_str = str(conversation_vec)
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  1 - (embedding <=> $2::vector) AS similarity
           FROM pb_memory
           WHERE project = $1 AND embedding IS NOT NULL
           ORDER BY embedding <=> $2::vector
           LIMIT $3""",
        project,
        vec_str,
        limit,
    )
    deduped: list[dict] = []
    for r in rows:
        entry = dict(r)
        sim = entry.get("similarity", 0.0) or 0.0
        if (
            entry.get("priority") == "critical"
            and entry.get("strength", 1.0) >= 0.3
            or threshold_low <= sim < threshold_high
        ):
            deduped.append(entry)
    return deduped
