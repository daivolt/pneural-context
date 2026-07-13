from __future__ import annotations

import logging
from typing import Any

try:
    import httpx

    HAS_HTTPX = True
except ImportError:
    HAS_HTTPX = False

logger = logging.getLogger("pneural_context.pb_memoria")


class MemoriaBridge:
    def __init__(self, url: str):
        if not HAS_HTTPX:
            raise ImportError(
                "httpx is required for Memoria integration. Install with: pip install pneural-context[memoria]"
            )
        self.url = url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def recall(
        self, query: str, project: str = "", limit: int = 5
    ) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        params: dict[str, Any] = {"q": query, "limit": limit}
        if project:
            params["project"] = project
        resp = await client.get(f"{self.url}/api/recall", params=params)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])

    async def get_sessions(self, project: str) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        resp = await client.get(f"{self.url}/api/sessions", params={"project": project})
        resp.raise_for_status()
        data = resp.json()
        return data.get("sessions", [])

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
