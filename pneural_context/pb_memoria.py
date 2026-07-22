from __future__ import annotations

import logging
from typing import Any, cast

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

    async def recall(self, query: str, project: str = "", limit: int = 5) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        params: dict[str, Any] = {"q": query, "limit": limit}
        if project:
            params["project"] = project
        try:
            resp = await client.get(f"{self.url}/recall", params=params)
            resp.raise_for_status()
            data = resp.json()
            return list(data.get("results", []))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria recall failed: %s", exc)
            return []

    async def get_review(self, project: str) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        try:
            resp = await client.get(f"{self.url}/review", params={"project": project})
            resp.raise_for_status()
            data = resp.json()
            return list(data.get("sessions", []))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria get_review failed: %s", exc)
            return []

    async def add_memory(
        self, project: str, text: str, priority: str = "normal", memory_type: str | None = None
    ) -> dict[str, Any] | None:
        client = await self._ensure_client()
        payload: dict[str, Any] = {"text": text, "priority": priority}
        if memory_type:
            payload["memory_type"] = memory_type
        try:
            resp = await client.post(f"{self.url}/memory/{project}", json=payload)
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria add_memory failed: %s", exc)
            return None

    async def get_memory_full(self, project: str) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        try:
            resp = await client.get(f"{self.url}/memory/{project}/full")
            resp.raise_for_status()
            data = resp.json()
            return list(data.get("entries", []))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria get_memory_full failed: %s", exc)
            return []

    async def get_red_ink(self, project: str, min_strength: float = 0.0) -> list[dict[str, Any]]:
        client = await self._ensure_client()
        try:
            resp = await client.get(
                f"{self.url}/red-ink/{project}", params={"min_strength": min_strength}
            )
            resp.raise_for_status()
            data = resp.json()
            return list(data.get("entries", []))
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria get_red_ink failed: %s", exc)
            return []

    async def get_context(self, project: str) -> dict[str, Any] | None:
        client = await self._ensure_client()
        try:
            resp = await client.get(f"{self.url}/ctx/{project}")
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria get_context failed: %s", exc)
            return None

    async def trigger_consolidation(self, project: str) -> dict[str, Any] | None:
        client = await self._ensure_client()
        try:
            resp = await client.post(f"{self.url}/consolidation/{project}/trigger")
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria trigger_consolidation failed: %s", exc)
            return None

    async def register_peer(self, name: str, url: str) -> dict[str, Any] | None:
        client = await self._ensure_client()
        payload = {"name": name, "url": url}
        try:
            resp = await client.post(f"{self.url}/federation/peers", json=payload)
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("Memoria register_peer failed: %s", exc)
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
