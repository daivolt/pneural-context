from __future__ import annotations

import time

import asyncpg

from .pool import _get_pool


async def apply_decay(
    decay_factor: float = 0.95,
    recent_threshold_seconds: float = 3600.0,
    pool: asyncpg.Pool | None = None,
) -> dict:
    p = await _get_pool(pool)
    total = await p.fetchval("SELECT COUNT(*) FROM pb_memory")
    red_ink = await p.fetchval("SELECT COUNT(*) FROM pb_memory WHERE priority = 'critical'")
    recent_cutoff = time.time() - recent_threshold_seconds
    await p.execute(
        """UPDATE pb_memory SET strength = strength * $1
           WHERE priority != 'critical'
             AND (pb_sync_source IS NULL OR pb_sync_source = 'local')
             AND (last_accessed IS NULL OR last_accessed < $2)""",
        decay_factor,
        recent_cutoff,
    )
    await p.execute(
        """UPDATE pb_memory SET strength = GREATEST(strength * $1, 0.5)
           WHERE priority = 'critical'
             AND (pb_sync_source IS NULL OR pb_sync_source = 'local')
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


async def archive_decay(threshold: float = 0.1, pool: asyncpg.Pool | None = None) -> dict:
    p = await _get_pool(pool)
    async with p.acquire() as conn:
        async with conn.transaction():
            rows = await conn.fetch(
                """SELECT id, project, entry, priority, memory_type, strength, created_at
                   FROM pb_memory
                   WHERE strength < $1 AND priority != 'critical'
                     AND (pb_sync_source IS NULL OR pb_sync_source = 'local')""",
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
            c_remaining = await conn.fetchval("SELECT COUNT(*) FROM pb_consolidated_memory")
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
    async with p.acquire() as conn, conn.transaction():
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


async def restore_archived(archive_id: int, pool: asyncpg.Pool | None = None) -> dict | None:
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
            await conn.execute("DELETE FROM pb_memory_archive WHERE id = $1", archive_id)
    return {
        "id": new_row["id"],
        "project": row["project"],
        "entry": row["entry"],
        "restored": True,
    }
