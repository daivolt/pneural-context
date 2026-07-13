"""
pb_server — FastAPI server for pneural-context.

Mountable as a sub-app or run standalone. Provides REST API for all
Paper Brain operations: memory, procedures, consolidation, decay, costs, anchors, briefing.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
import uvicorn
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import pb_db
from .pb_config import PBConfig
from .pb_engine import (
    auto_classify,
    generate_anchors,
    generate_briefing,
    run_consolidation,
)
from .pb_llm import LLMClient
from .pb_memoria import MemoriaBridge

logger = logging.getLogger("pneural_context.pb_server")

CONFIG_PATH = Path(
    os.environ.get(
        "PNEURAL_CONFIG_FILE", str(Path.home() / ".pneural-context" / "config.json")
    )
)

config: PBConfig = PBConfig.from_env()
llm_client: LLMClient | None = None
memoria: MemoriaBridge | None = None
_pool: asyncpg.Pool | None = None
_background_tasks: list[asyncio.Task] = []


def _load_config_file() -> dict:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    return {}


def _save_config_file(data: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_config_file()
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2))


def _apply_config_update(updates: dict):
    global config, llm_client, memoria
    for k, v in updates.items():
        if k == "llm_api_key" or k == "database_url":
            continue
        if hasattr(config, k):
            setattr(config, k, v)
    if any(k.startswith("llm_") for k in updates):
        llm_client = LLMClient(
            url=config.llm_url, model=config.llm_model, api_key=config.llm_api_key
        )
    if any(k.startswith("memoria_") for k in updates):
        if config.memoria_enabled and config.memoria_url:
            memoria = MemoriaBridge(config.memoria_url)
        else:
            memoria = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool, llm_client, memoria, config
    config = PBConfig.from_env()
    config_path = os.environ.get("PNEURAL_CONFIG_FILE")
    if config_path and Path(config_path).exists():
        config = PBConfig.load_from_file(config_path)

    if not config.database_url:
        config.database_url = os.environ.get("DATABASE_URL", "")
    if not config.database_url:
        raise RuntimeError("PNEURAL_DATABASE_URL or DATABASE_URL must be set")

    _pool = await asyncpg.create_pool(config.database_url, min_size=2, max_size=10)
    pb_db.init_pool(_pool)

    llm_client = LLMClient(
        url=config.llm_url, model=config.llm_model, api_key=config.llm_api_key
    )

    if config.memoria_enabled and config.memoria_url:
        memoria = MemoriaBridge(config.memoria_url)

    schema_path = Path(__file__).parent / "pb_schema.sql"
    if schema_path.exists():
        async with _pool.acquire() as conn:
            with open(schema_path) as f:
                await conn.execute(f.read())
        logger.info("Database schema applied")

    if config.decay_interval_seconds > 0:
        task = asyncio.create_task(_decay_loop(config.decay_interval_seconds))
        _background_tasks.append(task)
    if config.consolidation_interval_seconds > 0:
        task = asyncio.create_task(
            _consolidation_loop(config.consolidation_interval_seconds)
        )
        _background_tasks.append(task)

    logger.info(f"pneural-context server started on {config.host}:{config.port}")
    yield

    for task in _background_tasks:
        task.cancel()
    if _pool:
        await _pool.close()
    if memoria:
        await memoria.close()


app = FastAPI(
    title="pneural-context",
    version="0.1.0a1",
    description="Persistent neural context for LLMs",
    lifespan=lifespan,
)


async def _decay_loop(interval: float):
    while True:
        try:
            await asyncio.sleep(interval)
            result = await pb_db.apply_decay(pool=_pool)
            archive_result = await pb_db.archive_decay(
                pool=_pool, threshold=config.archive_threshold
            )
            logger.info(f"Decay cycle: {result}, archive: {archive_result}")
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Decay loop error")


async def _consolidation_loop(interval: float):
    while True:
        try:
            await asyncio.sleep(interval)
            projects = await pb_db.get_all_projects(pool=_pool)
            for project in projects:
                result = await run_consolidation(project, llm=llm_client, pool=_pool)
                logger.info(f"Consolidation for {project}: {result}")
        except asyncio.CancelledError:
            break
        except Exception:
            logger.exception("Consolidation loop error")


# ── Health ────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0a1"}


# ── Memory ────────────────────────────────────────────────────


@app.post("/api/memory")
async def add_memory(request: Request):
    body = await request.json()
    project = body.get("project", "")
    text = body.get("text", "")
    priority = body.get("priority", "normal")
    memory_type = body.get("memory_type")
    if not project or not text:
        raise HTTPException(400, "project and text required")
    entry_id = await pb_db.add_memory_entry(
        project, text, priority, memory_type, pool=_pool
    )
    return {"id": entry_id, "project": project, "text": text, "priority": priority}


@app.get("/api/memory")
async def get_memory(project: str, pool=None):
    entries = await pb_db.get_memory_entries(project, pool=_pool)
    return entries


@app.get("/api/memory/full")
async def get_memory_full(project: str):
    entries = await pb_db.get_memory_entries_full(project, pool=_pool)
    return entries


@app.get("/api/memory/red-ink")
async def get_red_ink(project: str, min_strength: float = 0.0):
    entries = await pb_db.get_red_ink(project, min_strength=min_strength, pool=_pool)
    return entries


@app.get("/api/memory/type/{memory_type}")
async def get_memory_by_type(project: str, memory_type: str):
    entries = await pb_db.get_memory_by_type(project, memory_type, pool=_pool)
    return entries


@app.patch("/api/memory/{index}/priority")
async def update_priority(index: int, request: Request):
    body = await request.json()
    project = body.get("project", "")
    priority = body.get("priority", "normal")
    ok = await pb_db.update_memory_priority(project, index, priority, pool=_pool)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@app.patch("/api/memory/{index}/type")
async def update_type(index: int, request: Request):
    body = await request.json()
    project = body.get("project", "")
    memory_type = body.get("memory_type", "temporal")
    ok = await pb_db.update_memory_type(project, index, memory_type, pool=_pool)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@app.delete("/api/memory/{entry_id}")
async def delete_memory(entry_id: int, request: Request):
    body = (
        await request.json()
        if request.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    project = body.get("project", "")
    ok = await pb_db.delete_memory_entry(project, entry_id, pool=_pool)
    if not ok:
        raise HTTPException(404, "Entry not found")
    return {"ok": True}


@app.get("/api/projects")
async def list_projects():
    return await pb_db.get_all_projects(pool=_pool)


@app.post("/api/memory/touch")
async def touch_memory(request: Request):
    body = await request.json()
    project = body.get("project", "")
    index = body.get("index")
    ids = body.get("ids")
    if ids:
        count = await pb_db.touch_memory_by_ids(ids, pool=_pool)
        return {"touched": count}
    if index is not None:
        ok = await pb_db.touch_memory_access(project, index, pool=_pool)
        return {"ok": ok}
    raise HTTPException(400, "index or ids required")


@app.post("/api/memory/boost")
async def boost_memory(request: Request):
    body = await request.json()
    project = body.get("project", "")
    index = body.get("index")
    if index is None:
        raise HTTPException(400, "index required")
    ok = await pb_db.touch_memory_access(project, index, pool=_pool)
    return {"ok": ok}


@app.post("/api/memory/replace")
async def replace_memory(request: Request):
    body = await request.json()
    project = body.get("project", "")
    old = body.get("old", "")
    new = body.get("new", "")
    ok = await pb_db.replace_memory_entry(project, old, new, pool=_pool)
    return {"ok": ok}


@app.post("/api/memory/classify")
async def classify_memory(request: Request):
    body = await request.json()
    project = body.get("project", "")
    result = await auto_classify(project, llm=llm_client, pool=_pool)
    return result


# ── Context ────────────────────────────────────────────────────


@app.get("/api/context")
async def get_context(project: str):
    threshold = config.archive_threshold or 0.1
    entries = await pb_db.get_memory_entries_full(project, pool=_pool)
    filtered = [e for e in entries if e.get("strength", 1.0) >= threshold]
    red_ink = [
        e
        for e in filtered
        if e.get("priority") == "critical" and e.get("strength", 1.0) >= 0.3
    ]
    by_type: dict[str, list[dict]] = {}
    for e in filtered:
        if e.get("priority") == "critical" and e.get("strength", 1.0) >= 0.3:
            continue
        t = e.get("memory_type", "temporal")
        by_type.setdefault(t, []).append(e)

    consolidated_rows = []
    try:
        consolidated_rows = await pb_db.get_consolidated_for_injection(
            project, pool=_pool
        )
    except Exception:
        pass

    marker = uuid.uuid4().hex[:8]
    lines = [f"<!-- PNEURAL_CTX: {marker} -->"]
    lines.append(f"# Context: {project}")
    lines.append("")

    if red_ink:
        lines.append("## Critical (Red Ink)")
        lines.append("")
        for e in red_ink:
            lines.append(f"- {e['entry']}")
        lines.append("")

    for mtype in ("concept", "temporal", "relation"):
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

    touch_ids = [e["id"] for e in filtered if "id" in e]
    if touch_ids:
        try:
            await pb_db.touch_memory_by_ids(touch_ids, pool=_pool)
        except Exception:
            pass
    if consolidated_rows:
        cons_ids = [c["id"] for c in consolidated_rows if "id" in c]
        if cons_ids:
            try:
                await pb_db.touch_consolidated_by_ids(cons_ids, pool=_pool)
            except Exception:
                pass

    typed_sections: dict[str, list[str]] = {}
    for mtype, group in by_type.items():
        typed_sections[mtype] = [e["entry"] for e in group]
    for mtype in ("concept", "temporal", "relation"):
        group = [
            e
            for e in filtered
            if e.get("memory_type", "temporal") == mtype
            and e.get("priority") != "critical"
        ]
        if group:
            typed_sections[mtype] = [e["entry"] for e in group]

    markdown = "\n".join(lines)
    return {
        "project": project,
        "markdown": markdown,
        "entries": len(filtered) + len(consolidated_rows),
        "marker": marker,
        "typed_sections": typed_sections,
        "consolidated_entries": len(consolidated_rows),
        "red_ink_entries": [e.get("entry", "") for e in red_ink],
    }


# ── Recall ────────────────────────────────────────────────────


@app.get("/api/recall")
async def recall(
    q: str,
    project: str | None = None,
    limit: int = 5,
    source: str | None = None,
    enrich: bool = True,
    boost: bool = True,
):
    results = []
    if project:
        entries = await pb_db.get_memory_entries_full(project, pool=_pool)
        for e in entries:
            if q.lower() in e.get("entry", "").lower():
                results.append(
                    {
                        "type": "memory",
                        "project": project,
                        "text": e["entry"],
                        "score": 1.0,
                        "id": e.get("id"),
                    }
                )
                if boost:
                    await pb_db.touch_memory_access(project, e.get("id", 0), pool=_pool)
        results = results[:limit]
    if memoria and (not source or source == "sessions"):
        try:
            mem_results = await memoria.recall(q, project=project, limit=limit)
            results.extend(mem_results)
        except Exception:
            pass
    return {"query": q, "results": results[:limit], "count": len(results)}


# ── Procedural Memory ──────────────────────────────────────────


@app.post("/api/procedures")
async def add_procedure(request: Request):
    body = await request.json()
    project = body.get("project", "")
    task_pattern = body.get("task_pattern", "")
    task_type = body.get("task_type")
    steps = body.get("steps", [])
    proven_by = body.get("proven_by", "")
    proc_id = await pb_db.add_procedure(
        project, task_pattern, task_type, steps, proven_by, pool=_pool
    )
    return {"id": proc_id}


@app.get("/api/procedures")
async def list_procedures(project: str, retired: bool = False):
    procs = await pb_db.list_procedures(project, retired=retired, pool=_pool)
    return procs


@app.get("/api/procedures/search")
async def search_procedures(project: str, query: str, limit: int = 5):
    procs = await pb_db.search_procedures(project, query, limit=limit, pool=_pool)
    return procs


@app.post("/api/procedures/{proc_id}/outcome")
async def procedure_outcome(proc_id: int, request: Request):
    body = await request.json()
    success = body.get("success", True)
    proven_by = body.get("proven_by", "")
    result = await pb_db.update_procedure_outcome(
        proc_id, success, proven_by, pool=_pool
    )
    if not result:
        raise HTTPException(404, "Procedure not found")
    return result


@app.post("/api/procedures/{proc_id}/retire")
async def retire_procedure(proc_id: int):
    ok = await pb_db.retire_procedure(proc_id, pool=_pool)
    return {"ok": ok}


# ── Consolidation ─────────────────────────────────────────────


@app.post("/api/consolidation")
async def trigger_consolidation(request: Request):
    body = await request.json()
    project = body.get("project", "")
    result = await run_consolidation(project, llm=llm_client, pool=_pool)
    return result


@app.get("/api/consolidation")
async def get_consolidation(project: str, tier: str | None = None):
    entries = await pb_db.get_consolidated(project, tier=tier, pool=_pool)
    return entries


@app.get("/api/consolidation/status")
async def consolidation_status(project: str):
    entries = await pb_db.get_consolidated(project, pool=_pool)
    tiers = {}
    for e in entries:
        t = e.get("tier", "consolidated")
        tiers[t] = tiers.get(t, 0) + 1
    return {"project": project, "tiers": tiers, "total": len(entries)}


# ── Decay ──────────────────────────────────────────────────────


@app.post("/api/decay")
async def trigger_decay():
    result = await pb_db.apply_decay(pool=_pool)
    return result


@app.post("/api/decay/archive")
async def trigger_archive_decay(threshold: float = 0.1):
    result = await pb_db.archive_decay(pool=_pool, threshold=threshold)
    return result


@app.get("/api/decay/status")
async def decay_status(project: str):
    return await pb_db.get_decay_status(project, pool=_pool)


# ── Archive ────────────────────────────────────────────────────


@app.get("/api/archive/search")
async def search_archive(project: str, q: str, limit: int = 5):
    return await pb_db.search_archived(project, q, limit=limit, pool=_pool)


# ── Cost Analytics ─────────────────────────────────────────────


@app.post("/api/costs")
async def record_cost(request: Request):
    body = await request.json()
    await pb_db.record_memory_cost(
        project=body.get("project", ""),
        session_id=body.get("session_id", ""),
        tokens_injected=body.get("tokens_injected", 0),
        tokens_saved_injection=body.get("tokens_saved_injection", 0),
        tokens_saved_forgetting=body.get("tokens_saved_forgetting", 0),
        context_type=body.get("context_type", "full"),
        task_outcome=body.get("task_outcome", ""),
        breakdown=body.get("breakdown"),
        pool=_pool,
    )
    return {"ok": True}


@app.get("/api/costs")
async def get_costs(project: str, days: int = 30):
    return await pb_db.get_memory_costs(project, days=days, pool=_pool)


@app.get("/api/costs/summary")
async def cost_summary(project: str, days: int = 30):
    return await pb_db.get_memory_cost_summary(project, days=days, pool=_pool)


@app.get("/api/costs/trends")
async def cost_trends(project: str, days: int = 30):
    costs = await pb_db.get_memory_costs(project, days=days, pool=_pool)
    return {
        "project": project,
        "days": days,
        "records": len(costs),
        "data": costs[:100],
    }


# ── Anchors & Briefing ────────────────────────────────────────


@app.get("/api/anchors")
async def anchors(project: str):
    return await generate_anchors(project, pool=_pool)


@app.get("/api/briefing")
async def briefing(project: str, task: str = ""):
    return await generate_briefing(project, task, llm=llm_client, pool=_pool)


# ── Papers ─────────────────────────────────────────────────────


@app.get("/api/papers/search")
async def search_papers(q: str, limit: int = 5):
    return await pb_db.search_papers(q, limit=limit, pool=_pool)


# ── Config ─────────────────────────────────────────────────────


@app.get("/api/config")
async def get_config():
    stored = _load_config_file()
    current = {
        k: v
        for k, v in config.__dict__.items()
        if k not in ("llm_api_key", "database_url")
    }
    current["stored_config"] = stored
    current["llm_api_key_set"] = bool(config.llm_api_key)
    current["database_url_set"] = bool(config.database_url)
    return current


@app.patch("/api/config")
async def update_config(request: Request):
    body = await request.json()
    safe_fields = {
        "llm_url",
        "llm_model",
        "host",
        "port",
        "memoria_url",
        "memoria_enabled",
        "decay_interval_seconds",
        "consolidation_interval_seconds",
        "archive_threshold",
    }
    updates = {k: v for k, v in body.items() if k in safe_fields}
    if not updates:
        raise HTTPException(400, "No valid config fields to update")
    _save_config_file(updates)
    _apply_config_update(updates)
    return {"ok": True, "updated": list(updates.keys())}


# ── Dashboard (HTML) ──────────────────────────────────────────


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    from .pb_dashboard import render_dashboard

    return HTMLResponse(render_dashboard())


@app.get("/dashboard/{project}", response_class=HTMLResponse)
async def dashboard_project(project: str):
    from .pb_dashboard import render_dashboard

    return HTMLResponse(render_dashboard(project=project))


def create_app(config_override: PBConfig | None = None) -> FastAPI:
    global config
    if config_override:
        config = config_override
    return app


def main():
    cfg = PBConfig.from_env()
    uvicorn.run(
        "pneural_context.pb_server:app",
        host=cfg.host,
        port=cfg.port,
        reload=False,
    )


if __name__ == "__main__":
    main()
