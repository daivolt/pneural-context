from __future__ import annotations

import asyncio
import logging

import asyncpg
from fastapi import APIRouter, Request

from .. import pb_db
from ..deps import PoolDep
from ..models.session import RecordSessionRequest

logger = logging.getLogger("pneural_context.routers.session")

router = APIRouter(prefix="/api/session", tags=["session"])

_SESSION_SUMMARY_TIMEOUT = 30


@router.post("/record")
async def record_session(
    body: RecordSessionRequest,
    request: Request,
    pool: asyncpg.Pool = PoolDep,
) -> dict:
    llm_client = getattr(request.app.state, "llm_client", None)
    summary = ""
    if llm_client:
        try:
            summary = await asyncio.wait_for(
                llm_client.summarize_session(body.title, body.messages),
                timeout=_SESSION_SUMMARY_TIMEOUT,
            )
        except TimeoutError:
            logger.warning("Session summarization timed out after %ds", _SESSION_SUMMARY_TIMEOUT)
        except Exception:
            logger.warning("Session summarization failed, storing raw title")
    if not summary:
        summary = body.title or f"Session {body.session_id[:8] if body.session_id else 'unknown'}"
    entry_id = await pb_db.add_memory_entry(
        body.project, summary, "normal", body.memory_type, pool=pool
    )
    return {
        "id": entry_id,
        "project": body.project,
        "summary": summary,
        "stored": True,
    }
