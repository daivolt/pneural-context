from __future__ import annotations

import json
import logging
import math
import time
from typing import Any

import asyncpg

logger = logging.getLogger("pneural_context.pb_db")

_pool: asyncpg.Pool | None = None


def init_pool(pool: asyncpg.Pool):
    global _pool
    _pool = pool


async def _get_pool(pool: asyncpg.Pool | None = None) -> asyncpg.Pool:
    p = pool or _pool
    if p is None:
        raise RuntimeError("Database pool not initialized")
    return p


# ── Memory ─────────────────────────────────────────────────────


async def add_memory_entry(
    project: str,
    text: str,
    priority: str = "normal",
    memory_type: str | None = None,
    pool: asyncpg.Pool | None = None,
) -> int:
    p = await _get_pool(pool)
    mt = memory_type or ("red" if priority == "critical" else "temporal")
    row = await p.fetchrow(
        """INSERT INTO pb_memory (project, entry, priority, memory_type, strength, last_accessed)
           VALUES ($1, $2, $3, $4, 1.0, extract(epoch from now()))
           RETURNING id""",
        project,
        text,
        priority,
        mt,
    )
    return row["id"]


async def get_memory_entries(
    project: str, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  last_accessed, created_at
           FROM pb_memory WHERE project = $1 ORDER BY id""",
        project,
    )
    return [dict(r) for r in rows]


async def get_memory_entries_full(
    project: str, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  last_accessed, created_at, search_enrichments
           FROM pb_memory WHERE project = $1 ORDER BY id""",
        project,
    )
    return [dict(r) for r in rows]


async def get_red_ink(
    project: str, min_strength: float = 0.0, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  last_accessed, created_at
           FROM pb_memory
           WHERE project = $1 AND priority = 'critical' AND strength >= $2
           ORDER BY strength DESC""",
        project,
        min_strength,
    )
    return [dict(r) for r in rows]


async def get_memory_by_type(
    project: str, memory_type: str, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  last_accessed, created_at
           FROM pb_memory
           WHERE project = $1 AND memory_type = $2
           ORDER BY id""",
        project,
        memory_type,
    )
    return [dict(r) for r in rows]


async def update_memory_priority(
    project: str, index: int, priority: str, pool: asyncpg.Pool | None = None
) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_memory SET priority = $1 WHERE project = $2 AND id = $3",
        priority,
        project,
        index,
    )
    return result.endswith("1")


async def update_memory_type(
    project: str, index: int, memory_type: str, pool: asyncpg.Pool | None = None
) -> bool:
    valid = ("red", "concept", "procedural", "temporal", "relation")
    if memory_type not in valid:
        raise ValueError(f"memory_type must be one of {valid}, got {memory_type!r}")
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_memory SET memory_type = $1 WHERE project = $2 AND id = $3",
        memory_type,
        project,
        index,
    )
    return result.endswith("1")


async def update_memory_type_by_id(
    entry_id: int, memory_type: str, pool: asyncpg.Pool | None = None
) -> bool:
    valid = ("red", "concept", "procedural", "temporal", "relation")
    if memory_type not in valid:
        raise ValueError(f"memory_type must be one of {valid}, got {memory_type!r}")
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_memory SET memory_type = $1 WHERE id = $2",
        memory_type,
        entry_id,
    )
    return result.endswith("1")


async def touch_memory_access(
    project: str, index: int, pool: asyncpg.Pool | None = None
) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        """UPDATE pb_memory
           SET last_accessed = extract(epoch from now()),
               strength = LEAST(1.0, strength + 0.3)
           WHERE project = $1 AND id = $2""",
        project,
        index,
    )
    return result.endswith("1")


async def touch_memory_by_ids(ids: list[int], pool: asyncpg.Pool | None = None) -> int:
    if not ids:
        return 0
    p = await _get_pool(pool)
    result = await p.execute(
        """UPDATE pb_memory
           SET last_accessed = extract(epoch from now()),
               strength = LEAST(1.0, strength + 0.3)
           WHERE id = ANY($1::bigint[])""",
        ids,
    )
    count = int(result.split()[-1]) if result else 0
    return count


async def boost_memory_entry(
    project: str, idx: int, pool: asyncpg.Pool | None = None
) -> dict:
    p = await _get_pool(pool)
    row = await p.fetchrow(
        """UPDATE pb_memory
           SET strength = LEAST(1.0, strength + 0.3),
               last_accessed = extract(epoch from now())
           WHERE project = $1 AND id = $2
           RETURNING id, strength""",
        project,
        idx,
    )
    if not row:
        return {"updated": False}
    return {"id": row["id"], "strength": float(row["strength"]), "updated": True}


async def replace_memory_entry(
    project: str, old: str, new: str, pool: asyncpg.Pool | None = None
) -> bool:
    p = await _get_pool(pool)
    async with p.acquire() as conn, conn.transaction():
        escaped_old = old.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        row = await conn.fetchrow(
            "SELECT id, entry FROM pb_memory WHERE project = $1 AND entry ILIKE '%' || $2 || '%' ESCAPE '\\' LIMIT 1",
            project,
            escaped_old,
        )
    if not row:
        return False
    await p.execute(
        "UPDATE pb_memory SET entry = $1 WHERE id = $2",
        new,
        row["id"],
    )
    return True


async def delete_memory_entry(
    project: str, index: int, pool: asyncpg.Pool | None = None
) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        "DELETE FROM pb_memory WHERE project = $1 AND id = $2",
        project,
        index,
    )
    return result.endswith("1")


async def get_memory_entry_id(
    project: str, index: int, pool: asyncpg.Pool | None = None
) -> int | None:
    p = await _get_pool(pool)
    row = await p.fetchrow(
        "SELECT id FROM pb_memory WHERE project = $1 AND id = $2",
        project,
        index,
    )
    return row["id"] if row else None


async def get_memory_char_count(project: str, pool: asyncpg.Pool | None = None) -> int:
    p = await _get_pool(pool)
    row = await p.fetchrow(
        "SELECT COALESCE(SUM(LENGTH(entry)), 0) as total FROM pb_memory WHERE project = $1",
        project,
    )
    return row["total"] if row else 0


async def search_memory(
    project: str,
    query: str,
    limit: int = 5,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  similarity(entry, $2) AS rank
           FROM pb_memory
           WHERE project = $1 AND (entry % $2 OR entry ILIKE '%' || $3 || '%' ESCAPE '\\')
           ORDER BY rank DESC LIMIT $4""",
        project,
        query,
        escaped,
        limit,
    )
    return [dict(r) for r in rows]


# ── Procedural Memory ──────────────────────────────────────────


async def add_procedure(
    project: str,
    task_pattern: str,
    task_type: str | None,
    steps: list[str],
    proven_by: str = "",
    pool: asyncpg.Pool | None = None,
) -> int:
    p = await _get_pool(pool)
    proven = [proven_by] if proven_by else []
    row = await p.fetchrow(
        """INSERT INTO pb_procedural_memory (project, task_pattern, task_type, steps, proven_by)
           VALUES ($1, $2, $3, $4::jsonb, $5)
           RETURNING id""",
        project,
        task_pattern,
        task_type,
        json.dumps(steps),
        proven,
    )
    return row["id"]


async def list_procedures(
    project: str, retired: bool = False, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, task_pattern, task_type, steps, success_count,
                  fail_count, reinforcement_score, last_success_at, proven_by,
                  created_at, retired
           FROM pb_procedural_memory
           WHERE project = $1 AND retired = $2
           ORDER BY reinforcement_score DESC""",
        project,
        retired,
    )
    return [dict(r) for r in rows]


async def search_procedures(
    project: str,
    query: str,
    limit: int = 5,
    similarity_threshold: float | None = None,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    threshold = similarity_threshold if similarity_threshold is not None else 0.1
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    async with p.acquire() as conn:
        async with conn.transaction():
            await conn.execute("SET LOCAL pg_trgm.similarity_threshold = $1", threshold)
            rows = await conn.fetch(
                """SELECT id, project, task_pattern, task_type, steps, success_count,
                          fail_count, reinforcement_score, proven_by, created_at, retired,
                          similarity(task_pattern, $2) as sim
                   FROM pb_procedural_memory
                   WHERE project = $1 AND retired = false
                         AND (task_pattern % $2 OR task_pattern ILIKE '%' || $4 || '%' ESCAPE '\\')
                   ORDER BY similarity(task_pattern, $2) DESC
                   LIMIT $3""",
                project,
                query,
                limit,
                escaped,
            )
            return [dict(r) for r in rows]


async def update_procedure_outcome(
    proc_id: int,
    success: bool,
    proven_by: str = "",
    pool: asyncpg.Pool | None = None,
) -> dict | None:
    p = await _get_pool(pool)
    async with p.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT success_count, fail_count FROM pb_procedural_memory WHERE id = $1",
                proc_id,
            )
            if not row:
                return None
            cur_succ = row["success_count"]
            cur_fail = row["fail_count"]
            if success:
                new_succ = cur_succ + 1
                new_fail = cur_fail
                accuracy = (
                    new_succ / (new_succ + new_fail) if new_succ + new_fail > 0 else 0.5
                )
                new_score = accuracy * math.log(new_succ + 1)
                new_score = round(max(0.0, min(1.0, new_score)), 6)
                if proven_by:
                    row2 = await conn.fetchrow(
                        """UPDATE pb_procedural_memory
                           SET success_count = $1, fail_count = $2,
                               reinforcement_score = $3, last_success_at = extract(epoch from now()),
                               proven_by = array_append(proven_by, $4)
                           WHERE id = $5 RETURNING *""",
                        new_succ,
                        new_fail,
                        new_score,
                        proven_by,
                        proc_id,
                    )
                else:
                    row2 = await conn.fetchrow(
                        """UPDATE pb_procedural_memory
                           SET success_count = $1, fail_count = $2,
                               reinforcement_score = $3, last_success_at = extract(epoch from now())
                           WHERE id = $4 RETURNING *""",
                        new_succ,
                        new_fail,
                        new_score,
                        proc_id,
                    )
            else:
                new_succ = cur_succ
                new_fail = cur_fail + 1
                accuracy = new_succ / (new_succ + new_fail) if new_succ > 0 else 0.0
                new_score = accuracy * math.log(new_succ + 1)
                new_score = round(max(0.0, min(1.0, new_score)), 6)
                row2 = await conn.fetchrow(
                    """UPDATE pb_procedural_memory
                       SET success_count = $1, fail_count = $2, reinforcement_score = $3
                       WHERE id = $4 RETURNING *""",
                    new_succ,
                    new_fail,
                    new_score,
                    proc_id,
                )
            if (
                row2
                and row2["fail_count"] > row2["success_count"] * 2
                and row2["fail_count"] > 5
            ):
                await conn.execute(
                    "UPDATE pb_procedural_memory SET retired = TRUE WHERE id = $1",
                    proc_id,
                )
            return dict(row2) if row2 else None


async def retire_procedure(proc_id: int, pool: asyncpg.Pool | None = None) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_procedural_memory SET retired = true WHERE id = $1",
        proc_id,
    )
    return result.endswith("1")


# ── Consolidated Memory ────────────────────────────────────────


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
        raise ValueError(
            f"memory_type must be one of {valid_types}, got {memory_type!r}"
        )
    valid_priorities = ("critical", "important", "normal")
    if priority not in valid_priorities:
        raise ValueError(
            f"priority must be one of {valid_priorities}, got {priority!r}"
        )
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
    return row["id"]


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


async def touch_consolidated_by_ids(
    ids: list[int], pool: asyncpg.Pool | None = None
) -> int:
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


# ── Decay & Archive ────────────────────────────────────────────


async def apply_decay(
    decay_factor: float = 0.95,
    recent_threshold_seconds: float = 3600.0,
    pool: asyncpg.Pool | None = None,
) -> dict:
    p = await _get_pool(pool)
    total = await p.fetchval("SELECT COUNT(*) FROM pb_memory")
    red_ink = await p.fetchval(
        "SELECT COUNT(*) FROM pb_memory WHERE priority = 'critical'"
    )
    recent_cutoff = time.time() - recent_threshold_seconds
    await p.execute(
        """UPDATE pb_memory SET strength = strength * $1
           WHERE priority != 'critical'
             AND (last_accessed IS NULL OR last_accessed < $2)""",
        decay_factor,
        recent_cutoff,
    )
    await p.execute(
        """UPDATE pb_memory SET strength = GREATEST(strength * $1, 0.5)
           WHERE priority = 'critical'
             AND (last_accessed IS NULL OR last_accessed < $2)""",
        decay_factor,
        recent_cutoff,
    )
    consolidated_total = await p.fetchval("SELECT COUNT(*) FROM pb_consolidated_memory")
    consolidated_red = await p.fetchval(
        "SELECT COUNT(*) FROM pb_consolidated_memory WHERE priority = 'critical'"
    )
    await p.execute(
        """UPDATE pb_consolidated_memory SET strength = strength * $1
           WHERE priority != 'critical'
             AND (last_accessed IS NULL OR last_accessed < $2)""",
        decay_factor,
        recent_cutoff,
    )
    await p.execute(
        """UPDATE pb_consolidated_memory SET strength = GREATEST(strength * $1, 0.5)
           WHERE priority = 'critical'
             AND (last_accessed IS NULL OR last_accessed < $2)""",
        decay_factor,
        recent_cutoff,
    )
    return {
        "total": total,
        "decayed": total - red_ink,
        "red_ink_protected": red_ink,
        "consolidated_total": consolidated_total,
        "consolidated_decayed": consolidated_total - consolidated_red,
        "consolidated_red_ink_protected": consolidated_red,
    }


async def archive_decay(
    threshold: float = 0.1, pool: asyncpg.Pool | None = None
) -> dict:
    p = await _get_pool(pool)
    async with p.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """SELECT id, project, entry, priority, memory_type, strength, created_at
                   FROM pb_memory
                   WHERE strength < $1 AND priority != 'critical'""",
                threshold,
            )
            for row in rows:
                await conn.execute(
                    """INSERT INTO pb_memory_archive
                       (original_id, project, entry, priority, memory_type, strength, created_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    row["id"],
                    row["project"],
                    row["entry"],
                    row["priority"],
                    row["memory_type"],
                    row["strength"],
                    row["created_at"],
                )
            if rows:
                ids = [row["id"] for row in rows]
                await conn.execute(
                    "DELETE FROM pb_memory WHERE id = ANY($1::bigint[]) AND priority != 'critical'",
                    ids,
                )
            c_rows = await conn.fetch(
                """SELECT id, project, content, priority, memory_type, strength, created_at
                   FROM pb_consolidated_memory
                   WHERE strength < $1 AND priority != 'critical'""",
                threshold,
            )
            for row in c_rows:
                await conn.execute(
                    """INSERT INTO pb_memory_archive
                       (original_id, project, entry, priority, memory_type, strength, created_at)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    row["id"],
                    row["project"],
                    row["content"],
                    row["priority"],
                    row["memory_type"],
                    row["strength"],
                    row["created_at"],
                )
            if c_rows:
                c_ids = [row["id"] for row in c_rows]
                await conn.execute(
                    "DELETE FROM pb_consolidated_memory WHERE id = ANY($1::int[]) AND priority != 'critical'",
                    c_ids,
                )
            remaining = await conn.fetchval("SELECT COUNT(*) FROM pb_memory")
            c_remaining = await conn.fetchval(
                "SELECT COUNT(*) FROM pb_consolidated_memory"
            )
            return {
                "archived": len(rows),
                "consolidated_archived": len(c_rows),
                "remaining": remaining,
                "consolidated_remaining": c_remaining,
            }


async def get_decay_status(project: str, pool: asyncpg.Pool | None = None) -> dict:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, entry, priority, memory_type, strength, last_accessed,
                  EXTRACT(EPOCH FROM now()) - last_accessed as age_seconds
           FROM pb_memory WHERE project = $1
           ORDER BY strength ASC""",
        project,
    )
    fading = [dict(r) for r in rows if r["strength"] < 0.4]
    stable = [dict(r) for r in rows if r["strength"] >= 0.4]
    return {
        "project": project,
        "total": len(rows),
        "fading": fading[:50],
        "stable_count": len(stable),
        "fading_count": len(fading),
    }


async def archive_memory_entry(entry_id: int, pool: asyncpg.Pool | None = None) -> bool:
    p = await _get_pool(pool)
    row = await p.fetchrow(
        "SELECT id, project, entry, priority, memory_type, strength, created_at FROM pb_memory WHERE id = $1",
        entry_id,
    )
    if not row:
        return False
    async with p.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO pb_memory_archive
                   (original_id, project, entry, priority, memory_type, strength, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                row["id"],
                row["project"],
                row["entry"],
                row["priority"],
                row["memory_type"],
                row["strength"],
                row["created_at"],
            )
            await conn.execute("DELETE FROM pb_memory WHERE id = $1", entry_id)
    return True


async def search_archived(
    project: str, query: str = "", limit: int = 20, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    if query:
        escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        rows = await p.fetch(
            """SELECT id, original_id, project, entry, priority, memory_type,
                      strength, archived_at
               FROM pb_memory_archive
               WHERE project = $1 AND (entry ILIKE '%' || $2 || '%' ESCAPE '\\' OR entry % $3)
               ORDER BY archived_at DESC LIMIT $4""",
            project,
            escaped,
            query,
            limit,
        )
    else:
        rows = await p.fetch(
            """SELECT id, original_id, project, entry, priority, memory_type,
                      strength, archived_at
               FROM pb_memory_archive
               WHERE project = $1
               ORDER BY archived_at DESC LIMIT $2""",
            project,
            limit,
        )
    return [dict(r) for r in rows]


async def restore_archived(
    archive_id: int, pool: asyncpg.Pool | None = None
) -> dict | None:
    p = await _get_pool(pool)
    row = await p.fetchrow(
        "SELECT id, original_id, project, entry, priority, memory_type, strength FROM pb_memory_archive WHERE id = $1",
        archive_id,
    )
    if not row:
        return None
    async with p.acquire() as conn:
        async with conn.transaction():
            new_row = await conn.fetchrow(
                """INSERT INTO pb_memory (project, entry, priority, memory_type, strength, last_accessed)
                   VALUES ($1, $2, $3, $4, $5, extract(epoch from now()))
                   RETURNING id""",
                row["project"],
                row["entry"],
                row["priority"],
                row["memory_type"],
                min(row["strength"] + 0.2, 1.0),
            )
            await conn.execute(
                "DELETE FROM pb_memory_archive WHERE id = $1", archive_id
            )
    return {
        "id": new_row["id"],
        "project": row["project"],
        "entry": row["entry"],
        "restored": True,
    }


# ── Cost Analytics ──────────────────────────────────────────────


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


# ── Papers ─────────────────────────────────────────────────────


async def search_papers(
    q: str, limit: int = 5, pool: asyncpg.Pool | None = None
) -> list[dict]:
    p = await _get_pool(pool)
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = await p.fetch(
        """SELECT id, filename, folder, title,
                  LEFT(text, 500) as snippet
           FROM pb_papers
           WHERE title ILIKE '%' || $1 || '%' ESCAPE '\\'
              OR text ILIKE '%' || $1 || '%' ESCAPE '\\'
              OR enriched_text ILIKE '%' || $1 || '%' ESCAPE '\\'
           ORDER BY id DESC LIMIT $2""",
        escaped,
        limit,
    )
    return [dict(r) for r in rows]


# ── Utility ────────────────────────────────────────────────────


async def get_all_projects(pool: asyncpg.Pool | None = None) -> list[str]:
    p = await _get_pool(pool)
    rows = await p.fetch("SELECT DISTINCT project FROM pb_memory ORDER BY project")
    return [r["project"] for r in rows]
