from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from ..pb_dashboard import render_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard() -> HTMLResponse:
    return HTMLResponse(render_dashboard())


@router.get("/dashboard/{project}", response_class=HTMLResponse)
async def dashboard_project(project: str) -> HTMLResponse:
    return HTMLResponse(render_dashboard(project=project))
