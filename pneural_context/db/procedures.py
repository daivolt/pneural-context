from __future__ import annotations

import json
import logging
import math
import re

import asyncpg

from . import pool as pool_mod
from .pool import _get_pool

logger = logging.getLogger("pneural_context.db.procedures")

_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "you",
        "your",
        "can",
        "could",
        "how",
        "what",
        "this",
        "that",
        "from",
        "via",
        "please",
        "user",
        "assistant",
        "let",
        "lets",
        "ill",
        "want",
        "need",
        "would",
        "should",
        "now",
    }
)


def _norm(word: str) -> str:
    # Light plural normalization: "sheets"->"sheet" but "class"->"class".
    if len(word) > 3 and word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def _tokens(text: str) -> set[str]:
    return {
        _norm(w)
        for w in re.findall(r"[a-z0-9]+", text.lower())
        if len(w) > 2 and w not in _STOPWORDS
    }


async def match_procedures(
    project: str,
    conversation: str,
    limit: int = 3,
    min_overlap: int = 2,
    min_ratio: float = 0.2,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    """Match procedures to conversation via token overlap.

    Deterministic alternative to trigram search for long conversations:
    pg_trgm similarity between a long conversation and a short task pattern
    is inherently low, so we score by how many pattern tokens appear in the
    conversation instead.
    """
    procs = await list_procedures(project, pool=pool)
    conv_tokens = _tokens(conversation)
    if not conv_tokens:
        return []
    scored: list[dict] = []
    for p in procs:
        pat_tokens = _tokens(p.get("task_pattern", ""))
        if not pat_tokens:
            continue
        overlap = len(pat_tokens & conv_tokens)
        ratio = overlap / len(pat_tokens)
        if overlap >= min_overlap and ratio >= min_ratio:
            scored.append({**p, "match_score": round(ratio, 3)})
    scored.sort(key=lambda x: (-x["match_score"], -x.get("reinforcement_score", 0)))
    return scored[:limit]


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
    proc_id: int = row["id"]
    if pool_mod._embedding_client:
        try:
            embed_text = f"{task_pattern} {' '.join(steps)}"
            vec = await pool_mod._embedding_client.embed(embed_text)
            if vec:
                await p.execute(
                    "UPDATE pb_procedural_memory SET embedding = $1 WHERE id = $2",
                    str(vec),
                    proc_id,
                )
        except Exception:
            logger.warning("Failed to embed procedure %d", proc_id, exc_info=True)
    return proc_id


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
    async with p.acquire() as conn, conn.transaction():
        await conn.execute(f"SET LOCAL pg_trgm.similarity_threshold = {float(threshold)}")
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
        return [{**dict(r), "_table": "pb_procedural_memory"} for r in rows]


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
                accuracy = new_succ / (new_succ + new_fail) if new_succ + new_fail > 0 else 0.5
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
            if row2 and row2["fail_count"] > row2["success_count"] * 2 and row2["fail_count"] > 5:
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
    return bool(result.endswith("1"))
