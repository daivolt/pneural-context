from __future__ import annotations

import json
from pathlib import Path

_TEMPLATE = Path(__file__).parent / "static" / "dashboard.html"
_TEMPLATE_CACHE: str | None = None


def render_dashboard(project: str | None = None) -> str:
    global _TEMPLATE_CACHE
    if _TEMPLATE_CACHE is None:
        _TEMPLATE_CACHE = _TEMPLATE.read_text()
    proj = project or ""
    return _TEMPLATE_CACHE.replace(
        "{{PROJECT_JSON}}", json.dumps(proj).replace("<", "\\x3c").replace(">", "\\x3e")
    )
