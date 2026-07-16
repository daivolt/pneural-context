from __future__ import annotations

import asyncpg
from fastapi import APIRouter, HTTPException, Request

from .. import pb_db
from ..deps import PoolDep
from ..models.memory import (
    AddMemoryRequest,
    BoostRequest,
    ClassifyRequest,
    ReplaceRequest,
    TouchRequest,
)
from ..pb_engine import auto_classify
from ..pb_llm import LLMClient

router = APIRouter(prefix="/api/memory", tags=["memory"])


@router.post("")
async def add_memory(body: AddMemoryRequest, pool: asyncpg.Pool = PoolDep) -> dict:
    entry_id = await pb_db.add_memory_entry(
        body.project, body.text, body.priority, body.memory_type, pool=pool
    )
    return {"id": entry_id, "project": body.project, "text": body.text, "priority": body.priority}


@router.get("")
async def get_memory(project: str, pool: asyncpg.Pool = PoolDep) -> list[dict]:
    return await pb_db.get_memory_entries(project, pool=pool)


@router.get("/full")
async def get_memory_full(project: str, pool: asyncpg.Pool = PoolDep) -> list[dict]:
    return await pb_db.get_memory_entries_full(project, pool=pool)


@router.get("/red-ink")
async def get_red_ink(
    project: str, min_strength: float = 0.0, pool: asyncpg.Pool = PoolDep
) -> list[dict]:
    return await pb_db.get_red_ink(project, min_strength=min_strength, pool=pool)


@router.get("/type/{memory_type}")
async def get_memory_by_type(
    project: str, memory_type: str, pool: asyncpg.Pool = PoolDep
) -> list[dict]:
    return await pb_db.get_memory_by_type(project, memory_type, pool=pool)


@router.patch("/{index}/priority")
async def update_priority(index: int, body: dict, pool: asyncpg.Pool = PoolDep) -> dict:
    project = body.get("project", "")
    priority = body.get("priority", "normal")
    ok = await pb_db.update_memory_priority(project, index, priority, pool=pool)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@router.patch("/{index}/type")
async def update_type(index: int, body: dict, pool: asyncpg.Pool = PoolDep) -> dict:
    project = body.get("project", "")
    memory_type = body.get("memory_type", "temporal")
    ok = await pb_db.update_memory_type(project, index, memory_type, pool=pool)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@router.delete("/{entry_id}")
async def delete_memory(entry_id: int, project: str = "", pool: asyncpg.Pool = PoolDep) -> dict:
    ok = await pb_db.delete_memory_entry(project, entry_id, pool=pool)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@router.post("/touch")
async def touch_memory(body: TouchRequest, pool: asyncpg.Pool = PoolDep) -> dict:
    if body.ids:
        count = await pb_db.touch_memory_by_ids(body.ids, pool=pool)
        return {"touched": count}
    if body.index is not None:
        ok = await pb_db.touch_memory_access(body.project, body.index, pool=pool)
        return {"ok": ok}
    raise HTTPException(400, "index or ids required")


@router.post("/boost")
async def boost_memory(body: BoostRequest, pool: asyncpg.Pool = PoolDep) -> dict:
    result = await pb_db.boost_memory_entry(body.project, body.index, pool=pool)
    if result is None:
        raise HTTPException(404, "Entry not found")
    return result


@router.post("/replace")
async def replace_memory(body: ReplaceRequest, pool: asyncpg.Pool = PoolDep) -> dict:
    ok = await pb_db.replace_memory_entry(body.project, body.old, body.new, pool=pool)
    return {"ok": ok}


@router.post("/classify")
async def classify_memory(
    body: ClassifyRequest, request: Request, pool: asyncpg.Pool = PoolDep
) -> dict:
    llm_client: LLMClient | None = getattr(request.app.state, "llm_client", None)
    return await auto_classify(body.project, llm=llm_client, pool=pool)
