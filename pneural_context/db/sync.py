from __future__ import annotations

import hashlib
import logging

import asyncpg

from ..pb_memoria import MemoriaBridge
from .memory import _normalize
from .pool import _get_pool

logger = logging.getLogger("pneural_context.db.sync")


def _content_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode()).hexdigest()


async def pull_from_memoria(
    project: str,
    memoria: MemoriaBridge,
    pool: asyncpg.Pool | None = None,
) -> int:
    p = await _get_pool(pool)
    entries = await memoria.get_memory_full(project)
    if not entries:
        return 0

    local_rows = await p.fetch(
        "SELECT entry, pb_sync_source FROM pb_memory WHERE project = $1",
        project,
    )
    local_hashes = {_content_hash(r["entry"]) for r in local_rows}

    inserted = 0
    for entry in entries:
        text = entry.get("entry", "") or entry.get("text", "")
        if not text:
            continue
        h = _content_hash(text)
        if h in local_hashes:
            continue
        priority = entry.get("priority", "normal")
        memory_type = entry.get("memory_type", "temporal")
        await p.execute(
            """INSERT INTO pb_memory (project, entry, priority, memory_type, strength, last_accessed, pb_sync_source)
               VALUES ($1, $2, $3, $4, 1.0, extract(epoch from now()), 'memoria')""",
            project,
            text,
            priority,
            memory_type,
        )
        inserted += 1

    await p.execute(
        """INSERT INTO pb_sync_state (project, peer, last_sync_at, last_sync_status, updated_at)
           VALUES ($1, 'memoria', extract(epoch from now()), 'success', extract(epoch from now()))
           ON CONFLICT (project, peer) DO UPDATE
           SET last_sync_at = extract(epoch from now()),
               last_sync_status = 'success',
               updated_at = extract(epoch from now())""",
        project,
    )

    return inserted


async def push_to_memoria(
    project: str,
    text: str,
    priority: str,
    memory_type: str | None,
    memoria: MemoriaBridge,
) -> bool:
    try:
        result = await memoria.add_memory(project, text, priority, memory_type)
        if result:
            logger.info("Pushed memory to memoria for project %s", project)
            return True
        return False
    except Exception as exc:
        logger.warning("Swallowed exception: %s", exc, exc_info=True)
        logger.warning("Failed to push memory to memoria for project %s", project, exc_info=True)
        return False
