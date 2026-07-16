from __future__ import annotations

import asyncpg

from .papers import search_papers
from .pool import _embedding_client, _get_pool
from .procedures import search_procedures


async def vector_search_memory(
    project: str,
    query_vec: list[float],
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    vec_str = str(query_vec)
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
    return [{**dict(r), "_table": "pb_memory"} for r in rows]


async def vector_search_consolidated(
    project: str,
    query_vec: list[float],
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    vec_str = str(query_vec)
    rows = await p.fetch(
        """SELECT id, project, tier, content, memory_type, priority, strength,
                  1 - (embedding <=> $2::vector) AS similarity
           FROM pb_consolidated_memory
           WHERE project = $1 AND embedding IS NOT NULL
           ORDER BY embedding <=> $2::vector
           LIMIT $3""",
        project,
        vec_str,
        limit,
    )
    return [{**dict(r), "_table": "pb_consolidated_memory"} for r in rows]


async def vector_search_procedures(
    project: str,
    query_vec: list[float],
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    vec_str = str(query_vec)
    rows = await p.fetch(
        """SELECT id, project, task_pattern, task_type, steps, reinforcement_score,
                  1 - (embedding <=> $2::vector) AS similarity
           FROM pb_procedural_memory
           WHERE project = $1 AND embedding IS NOT NULL AND NOT retired
           ORDER BY embedding <=> $2::vector
           LIMIT $3""",
        project,
        vec_str,
        limit,
    )
    return [{**dict(r), "_table": "pb_procedural_memory"} for r in rows]


async def vector_search_papers(
    query_vec: list[float],
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    vec_str = str(query_vec)
    rows = await p.fetch(
        """SELECT id, filename, folder, title,
                  LEFT(text, 500) as snippet,
                  1 - (embedding <=> $1::vector) AS similarity
           FROM pb_papers
           WHERE embedding IS NOT NULL
           ORDER BY embedding <=> $1::vector
           LIMIT $2""",
        vec_str,
        limit,
    )
    return [{**dict(r), "_table": "pb_papers"} for r in rows]


def _rrf_merge(*result_sets: list[dict], k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    entries: dict[str, dict] = {}
    for results in result_sets:
        for rank, row in enumerate(results):
            rid = row.get("id")
            table = row.get("_table", "unknown")
            if rid is None:
                continue
            key = f"{table}:{rid}"
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            entries[key] = row
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [{**entries[key], "rrf_score": score} for key, score in ranked]


async def hybrid_search_memory(
    project: str,
    query: str,
    query_vec: list[float] | None = None,
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    trigram_rows = await p.fetch(
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
    trigram_results = [{**dict(r), "_table": "pb_memory"} for r in trigram_rows]
    if query_vec is None:
        return trigram_results
    vector_results = await vector_search_memory(project, query_vec, limit, pool)
    return _rrf_merge(trigram_results, vector_results)[:limit]


async def hybrid_search_consolidated(
    project: str,
    query: str,
    query_vec: list[float] | None = None,
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    p = await _get_pool(pool)
    escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    trigram_rows = await p.fetch(
        """SELECT id, project, tier, content, memory_type, priority, strength,
                  similarity(content, $2) AS rank
           FROM pb_consolidated_memory
           WHERE project = $1
             AND (content % $2 OR content ILIKE '%' || $3 || '%' ESCAPE '\\')
           ORDER BY rank DESC LIMIT $4""",
        project,
        query,
        escaped,
        limit,
    )
    trigram_results = [{**dict(r), "_table": "pb_consolidated_memory"} for r in trigram_rows]
    if query_vec is None:
        return trigram_results
    vector_results = await vector_search_consolidated(project, query_vec, limit, pool)
    return _rrf_merge(trigram_results, vector_results)[:limit]


async def hybrid_search_procedures(
    project: str,
    query: str,
    query_vec: list[float] | None = None,
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    trigram_results = await search_procedures(project, query, limit, pool=pool)
    if query_vec is None:
        return trigram_results
    vector_results = await vector_search_procedures(project, query_vec, limit, pool)
    return _rrf_merge(trigram_results, vector_results)[:limit]


async def hybrid_search_papers(
    query: str,
    query_vec: list[float] | None = None,
    limit: int = 10,
    pool: asyncpg.Pool | None = None,
) -> list[dict]:
    trigram_results = await search_papers(query, limit, pool)
    if query_vec is None:
        return trigram_results
    vector_results = await vector_search_papers(query_vec, limit, pool)
    return _rrf_merge(trigram_results, vector_results)[:limit]


_ALLOWED_TABLES = {
    "pb_memory": "entry",
    "pb_consolidated_memory": "content",
    "pb_procedural_memory": "task_pattern",
    "pb_papers": "text",
}


async def reindex_table(
    table: str,
    text_column: str,
    batch_size: int = 32,
    pool: asyncpg.Pool | None = None,
) -> int:
    p = await _get_pool(pool)
    if _embedding_client is None:
        raise RuntimeError("Embedding client not initialized")
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Invalid table: {table!r}. Must be one of {sorted(_ALLOWED_TABLES)}")
    expected_col = _ALLOWED_TABLES[table]
    if text_column != expected_col:
        raise ValueError(
            f"Invalid column {text_column!r} for table {table!r}. Expected {expected_col!r}"
        )
    count = 0
    while True:
        rows = await p.fetch(
            "SELECT id, entry FROM pb_memory WHERE embedding IS NULL ORDER BY id LIMIT $1"
            if table == "pb_memory"
            else "SELECT id, content FROM pb_consolidated_memory WHERE embedding IS NULL ORDER BY id LIMIT $1"
            if table == "pb_consolidated_memory"
            else "SELECT id, task_pattern FROM pb_procedural_memory WHERE embedding IS NULL ORDER BY id LIMIT $1"
            if table == "pb_procedural_memory"
            else "SELECT id, text FROM pb_papers WHERE embedding IS NULL ORDER BY id LIMIT $1",
            batch_size,
        )
        if not rows:
            break
        col = expected_col
        texts = [r[col] for r in rows]
        vectors = await _embedding_client.embed_batch(texts)
        update_sql = f"UPDATE {table} SET embedding = $1 WHERE id = $2"
        for i, row in enumerate(rows):
            vec = vectors[i] if i < len(vectors) else None
            if vec:
                await p.execute(update_sql, str(vec), row["id"])
                count += 1
    return count
