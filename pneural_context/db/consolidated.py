from __future__ import annotations

import logging

import asyncpg

from .pool import _embedding_client, _get_pool

logger = logging.getLogger("pneural_context.db.consolidated")


async def add_consolidated(
    project: str,
    tier: str,
    content: str,
    memory_type: str = "concept",
    priority: str = "normal",
    source_sessions: list[str] | None = None,
    source_episode_ids: list[str] | None = None,
    strength: float = 1.0,
    pool: asyncpg.Pool | None = None,
) -> int:
    valid_tiers = ("immediate", "consolidated", "timeless")
    if tier not in valid_tiers:
        raise ValueError(f"tier must be one of {valid_tiers}, got {tier!r}")
    valid_types = ("red", "concept", "procedural", "temporal", "relation")
    if memory_type not in valid_types:
        raise ValueError(f"memory_type must be one of {valid_types}, got {memory_type!r}")
    valid_priorities = ("critical", "important", "normal")
    if priority not in valid_priorities:
        raise ValueError(f"priority must be one of {valid_priorities}, got {priority!r}")
    p = await _get_pool(pool)
    row = await p.fetchrow(
        """INSERT INTO pb_consolidated_memory
           (project, tier, content, source_sessions, source_episode_ids,
            memory_type, priority, strength)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
           RETURNING id""",
        project,
        tier,
        content,
        source_sessions or [],
        source_episode_ids or [],
        memory_type,
        priority,
        strength,
    )
    consol_id = row["id"]
    if _embedding_client:
        try:
            vec = await _embedding_client.embed(content)
            if vec:
                await p.execute(
                    "UPDATE pb_consolidated_memory SET embedding = $1 WHERE id = $2",
                    str(vec),
                    consol_id,
                )
        except Exception:
            logger.warning("Failed to embed consolidated entry %d", consol_id, exc_info=True)
    return consol_id


async def add_consolidated_entry(
    project: str,
    tier: str,
    content: str,
    memory_type: str = "concept",
    priority: str = "normal",
    source_sessions: list[str] | None = None,
    source_episode_ids: list[str] | None = None,
    strength: float = 1.0,
    pool: asyncpg.Pool | None = None,
) -> int:
    return await add_consolidated(
        project,
        tier,
        content,
        memory_type,
        priority,
        source_sessions,
        source_episode_ids,
        strength,
        pool,
    )


async def get_consolidated(
    project: str,
    tier: str | None = None,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    if tier:
        rows = await p.fetch(
            """SELECT id, project, tier, content, source_sessions,
                      source_episode_ids, memory_type, priority, strength,
                      created_at, last_accessed
               FROM pb_consolidated_memory
               WHERE project = $1 AND tier = $2
               ORDER BY created_at DESC""",
            project,
            tier,
        )
    else:
        rows = await p.fetch(
            """SELECT id, project, tier, content, source_sessions,
                      source_episode_ids, memory_type, priority, strength,
                      created_at, last_accessed
               FROM pb_consolidated_memory
               WHERE project = $1
               ORDER BY tier, created_at DESC""",
            project,
        )
    return [dict(r) for r in rows]


async def get_consolidated_by_tier(
    project: str, tier: str, pool: asyncpg.Pool | None = None
) -> list[dict]:
    return await get_consolidated(project, tier, pool)


async def get_consolidated_for_injection(
    project: str, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, tier, content, memory_type, priority, strength
           FROM pb_consolidated_memory
           WHERE project = $1 AND strength >= 0.3
           ORDER BY
               CASE priority
                   WHEN 'critical' THEN 0
                   WHEN 'important' THEN 1
                   ELSE 2
               END,
               strength DESC""",
        project,
    )
    return [dict(r) for r in rows]


async def promote_consolidated(
    entry_id: int, new_tier: str, pool: asyncpg.Pool | None = None
) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_consolidated_memory SET tier = $1 WHERE id = $2",
        new_tier,
        entry_id,
    )
    return result.endswith("1")


async def touch_consolidated_by_ids(ids: list[int], pool: asyncpg.Pool | None = None) -> int:
    if not ids:
        return 0
    p = await _get_pool(pool)
    result = await p.execute(
        """UPDATE pb_consolidated_memory
           SET last_accessed = extract(epoch from now()),
               strength = LEAST(strength + 0.3, 1.0)
           WHERE id = ANY($1::int[])""",
        ids,
    )
    count = int(result.split()[-1]) if result else 0
    return count
