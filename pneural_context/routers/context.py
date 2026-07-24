from __future__ import annotations

import logging
import uuid

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from .. import pb_db
from ..db import procedures as procedures_db
from ..deps import PoolDep
from ..models.context import SmartContextRequest
from ..pb_embeddings import get_conversation_embedding

router = APIRouter(prefix="/api/context", tags=["context"])
logger = logging.getLogger("pneural_context.routers.context")

MAX_CONTEXT_CHARS = 8000
MAX_ENTRIES_PER_TYPE = 10
MAX_CONSOLIDATED = 10


@router.get("")
async def get_context(
    request: Request,
    project: str,
    semantic_query: str | None = None,
    pool: asyncpg.Pool = PoolDep,
) -> dict:
    config = request.app.state.config
    threshold = config.archive_threshold if config.archive_threshold is not None else 0.1
    entries = await pb_db.get_memory_entries_full(project, pool=pool)
    filtered = [e for e in entries if e.get("strength", 1.0) >= threshold]
    red_ink = [
        e for e in filtered if e.get("priority") == "critical" and e.get("strength", 1.0) >= 0.3
    ]
    by_type: dict[str, list[dict]] = {}
    for e in filtered:
        if e.get("priority") == "critical" and e.get("strength", 1.0) >= 0.3:
            continue
        t = e.get("memory_type", "temporal")
        by_type.setdefault(t, []).append(e)

    for mtype in by_type:
        by_type[mtype] = by_type[mtype][:MAX_ENTRIES_PER_TYPE]

    consolidated_rows: list[dict] = []
    try:
        consolidated_rows = await pb_db.get_consolidated_for_injection(project, pool=pool)
    except Exception:
        logger.warning("Failed to fetch consolidated entries", exc_info=True)
    consolidated_rows = consolidated_rows[:MAX_CONSOLIDATED]

    marker = uuid.uuid4().hex[:8]
    lines = [f"<!-- PNEURAL_CTX: {marker} -->"]
    lines.append(f"# Context: {project}")
    lines.append("")

    if red_ink:
        lines.append("## Critical (Red Ink)")
        lines.append("")
        for e in red_ink[:5]:
            lines.append(f"- {e['entry']}")
        lines.append("")

    for mtype in ("concept", "procedural", "temporal", "relation"):
        group = by_type.pop(mtype, [])
        if group:
            lines.append(f"## {mtype.upper()}")
            lines.append("")
            for e in group:
                lines.append(f"- {e['entry']}")
            lines.append("")

    for mtype, group in sorted(by_type.items()):
        lines.append(f"## {mtype.upper()}")
        lines.append("")
        for e in group:
            lines.append(f"- {e['entry']}")
        lines.append("")

    if consolidated_rows:
        lines.append("## Consolidated Memory")
        lines.append("")
        for c in consolidated_rows:
            tier_label = c.get("tier", "consolidated")
            lines.append(f"- [{tier_label}] {c.get('content', '')}")
        lines.append("")

    lines.append(
        "IMPORTANT: This context is auto-injected by pneural-context. "
        "Preserve the PNEURAL_CTX marker during summarization."
    )

    markdown = "\n".join(lines)
    if len(markdown) > MAX_CONTEXT_CHARS:
        markdown = markdown[:MAX_CONTEXT_CHARS]

    touch_ids = [e["id"] for e in filtered if "id" in e]
    if touch_ids:
        try:
            await pb_db.touch_memory_by_ids(touch_ids, pool=pool)
        except Exception:
            logger.warning("Failed to touch memory entries", exc_info=True)
    if consolidated_rows:
        cons_ids = [c["id"] for c in consolidated_rows if "id" in c]
        if cons_ids:
            try:
                await pb_db.touch_consolidated_by_ids(cons_ids, pool=pool)
            except Exception:
                logger.warning("Failed to touch consolidated entries", exc_info=True)

    return {
        "project": project,
        "markdown": markdown,
        "entries": len(filtered) + len(consolidated_rows),
        "marker": marker,
        "consolidated_entries": len(consolidated_rows),
        "red_ink_entries": [e.get("entry", "") for e in red_ink[:5]],
    }


@router.post("/smart")
async def get_smart_context(
    body: SmartContextRequest,
    request: Request,
    pool: asyncpg.Pool = PoolDep,
) -> dict:
    config = request.app.state.config
    embedding_client = getattr(request.app.state, "embedding_client", None)
    if not body.project:
        raise HTTPException(400, "project required")
    threshold = config.archive_threshold if config.archive_threshold is not None else 0.1
    if not body.conversation or not embedding_client:
        entries = await pb_db.get_memory_entries_full(body.project, pool=pool)
        filtered = [e for e in entries if e.get("strength", 1.0) >= threshold]
        return {"project": body.project, "source": "full", "entries": filtered}
    try:
        conv_vec = await get_conversation_embedding(
            body.project, body.conversation, embedding_client
        )
    except Exception:
        conv_vec = None
    if conv_vec is None:
        entries = await pb_db.get_memory_entries_full(body.project, pool=pool)
        filtered = [e for e in entries if e.get("strength", 1.0) >= threshold]
        return {"project": body.project, "source": "full_fallback", "entries": filtered}
    deduped = await pb_db.dedup_context_entries(
        body.project,
        conv_vec,
        config.dedup_threshold_high,
        config.dedup_threshold_low,
        pool=pool,
    )
    matched_procedures: list[dict] = []
    try:
        # Use a low trigram threshold so keyword-heavy tool patterns (e.g.
        # "read or write Google Sheets, SharePoint Excel, spreadsheet") still
        # surface when the user mentions sheets/sharepoint/spreadsheet.
        matched_procedures = await procedures_db.search_procedures(
            body.project,
            body.conversation,
            limit=3,
            similarity_threshold=0.3,
            pool=pool,
        )
    except Exception:
        logger.warning("Failed to search procedures for smart context", exc_info=True)
    return {
        "project": body.project,
        "source": "smart_dedup",
        "dedup_threshold_high": config.dedup_threshold_high,
        "dedup_threshold_low": config.dedup_threshold_low,
        "entries": deduped,
        "procedures": matched_procedures,
    }
