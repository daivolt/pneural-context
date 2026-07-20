from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher

import asyncpg

from . import pool as pool_mod
from .pool import _get_pool

logger = logging.getLogger("pneural_context.db.memory")


def _normalize(text: str) -> str:
    if not isinstance(text, str):
        return ""
    return re.sub(r"\s+", " ", text.strip().lower())


def _is_similar(text: str, existing: list[str], threshold: float = 0.8) -> bool:
    if not isinstance(text, str):
        return False
    norm = _normalize(text)
    if not norm:
        return True
    for ex in existing:
        if not isinstance(ex, str):
            continue
        if SequenceMatcher(None, norm, _normalize(ex)).quick_ratio() >= threshold:
            return True
    return False


async def add_memory_entry(
    project: str,
    text: str,
    priority: str = "normal",
    memory_type: str | None = None,
    dedup_threshold: float = 0.8,
    pool: asyncpg.Pool | None = None,
) -> int:
    p = await _get_pool(pool)
    existing_rows = await p.fetch(
        "SELECT entry FROM pb_memory WHERE project = $1",
        project,
    )
    existing_texts = [r["entry"] for r in existing_rows]
    if _is_similar(text, existing_texts, dedup_threshold):
        logger.info("Skipping duplicate memory entry for project %s", project)
        existing_ids = await p.fetch(
            "SELECT id FROM pb_memory WHERE project = $1 ORDER BY id DESC LIMIT 1",
            project,
        )
        if existing_ids:
            return int(existing_ids[0]["id"])
        return -1
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
    entry_id: int = row["id"]
    if pool_mod._embedding_client:
        try:
            vec = await pool_mod._embedding_client.embed(text)
            if vec:
                await p.execute(
                    "UPDATE pb_memory SET embedding = $1 WHERE id = $2",
                    str(vec),
                    entry_id,
                )
        except Exception:
            logger.warning("Failed to embed memory entry %d", entry_id, exc_info=True)
    return entry_id


async def get_memory_entries(project: str, pool: asyncpg.Pool | None = None) -> list[dict]:
    p = await _get_pool(pool)
    rows = await p.fetch(
        """SELECT id, project, entry, priority, memory_type, strength,
                  last_accessed, created_at
           FROM pb_memory WHERE project = $1 ORDER BY id""",
        project,
    )
    return [dict(r) for r in rows]


async def get_memory_entries_full(project: str, pool: asyncpg.Pool | None = None) -> list[dict]:
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
    return bool(result.endswith("1"))


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
    return bool(result.endswith("1"))


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
    return bool(result.endswith("1"))


async def touch_memory_access(project: str, index: int, pool: asyncpg.Pool | None = None) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_memory SET last_accessed = extract(epoch from now()) WHERE project = $1 AND id = $2",
        project,
        index,
    )
    return bool(result.endswith("1"))


async def touch_memory_by_ids(ids: list[int], pool: asyncpg.Pool | None = None) -> int:
    if not ids:
        return 0
    p = await _get_pool(pool)
    result = await p.execute(
        "UPDATE pb_memory SET last_accessed = extract(epoch from now()) WHERE id = ANY($1::bigint[])",
        ids,
    )
    count = int(result.split()[-1]) if result else 0
    return count


async def boost_memory_entry(project: str, idx: int, pool: asyncpg.Pool | None = None) -> dict:
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
    async with p.acquire() as conn:
        async with conn.transaction():
            escaped_old = old.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            row = await conn.fetchrow(
                "SELECT id, entry FROM pb_memory WHERE project = $1 AND entry ILIKE '%' || $2 || '%' ESCAPE '\\' LIMIT 1",
                project,
                escaped_old,
            )
            if not row:
                return False
            await conn.execute(
                "UPDATE pb_memory SET entry = $1 WHERE id = $2",
                new,
                row["id"],
            )
            return True


async def delete_memory_entry(project: str, index: int, pool: asyncpg.Pool | None = None) -> bool:
    p = await _get_pool(pool)
    result = await p.execute(
        "DELETE FROM pb_memory WHERE project = $1 AND id = $2",
        project,
        index,
    )
    return bool(result.endswith("1"))


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
    return [{**dict(r), "_table": "pb_memory"} for r in rows]
