from __future__ import annotations

import asyncpg

from .pool import _get_pool


async def search_papers(q: str, limit: int = 5, pool: asyncpg.Pool | None = None) -> list[dict]:
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
    return [{**dict(r), "_table": "pb_papers"} for r in rows]
