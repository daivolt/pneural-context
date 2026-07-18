from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/errors", tags=["errors"])


@router.post("")
async def log_error(body: dict, request: Request) -> dict:
    """Log an error from any source (plugin, MCP, API, server)."""
    pool = request.app.state.pool
    if not pool:
        return {"status": "no db"}
    project = body.get("project", "unknown")
    session_id = body.get("session_id", str(uuid4())[:8])
    source = body.get("source", "plugin")
    level = body.get("level", "error")
    message = body.get("message", "")
    stack = body.get("stack", "")

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO pb_errors (project, session_id, source, level, message, stack)
               VALUES ($1, $2, $3, $4, $5, $6)""",
            project,
            session_id,
            source,
            level,
            message,
            stack,
        )
    return {"status": "logged", "project": project, "session_id": session_id}


@router.get("")
async def list_errors(
    request: Request,
    project: str = "",
    limit: int = 50,
    level: str = "",
) -> list[dict]:
    pool = request.app.state.pool
    if not pool:
        return []
    query = (
        "SELECT id, project, session_id, source, level, message, stack, created_at FROM pb_errors"
    )
    params: list = []
    conditions: list[str] = []
    if project:
        conditions.append(f"project = ${len(params) + 1}")
        params.append(project)
    if level:
        conditions.append(f"level = ${len(params) + 1}")
        params.append(level)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += f" ORDER BY created_at DESC LIMIT {int(limit)}"
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *params)
    return [dict(r) for r in rows]


@router.delete("")
async def clear_errors(request: Request, project: str = "") -> dict:
    pool = request.app.state.pool
    if not pool:
        return {"status": "no db"}
    if project:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM pb_errors WHERE project = $1", project)
        return {"status": "cleared", "project": project}
    else:
        async with pool.acquire() as conn:
            await conn.execute("DELETE FROM pb_errors")
        return {"status": "cleared", "project": "*"}
