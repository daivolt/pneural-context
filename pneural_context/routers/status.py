from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api/status", tags=["status"])

_disabled_projects: set[str] = set()


@router.get("")
async def pneural_status(project: str = "") -> dict:
    return {"project": project, "enabled": project not in _disabled_projects}


@router.post("/disable")
async def disable_pneural(body: dict) -> dict:
    project = body.get("project", "")
    if project:
        _disabled_projects.add(project)
    return {"project": project, "enabled": False}


@router.post("/enable")
async def enable_pneural(body: dict) -> dict:
    project = body.get("project", "")
    _disabled_projects.discard(project)
    return {"project": project, "enabled": True}


@router.post("/toggle")
async def toggle_pneural(body: dict) -> dict:
    project = body.get("project", "")
    if project in _disabled_projects:
        _disabled_projects.discard(project)
        return {"project": project, "enabled": True}
    else:
        _disabled_projects.add(project)
        return {"project": project, "enabled": False}
