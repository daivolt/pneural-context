from __future__ import annotations

import secrets
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class ApiKeyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Any:
        config = getattr(request.app.state, "config", None)
        api_key: str = getattr(config, "api_key", "") if config else ""

        if api_key and request.url.path.startswith("/api/"):
            header_key = request.headers.get("x-api-key", "")
            query_key = request.query_params.get("api_key", "")
            provided = header_key or query_key
            if not provided:
                return JSONResponse(
                    status_code=401,
                    content={
                        "detail": "Missing API key. Set X-API-Key header or api_key query param."
                    },
                )
            if not secrets.compare_digest(provided, api_key):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid API key."},
                )

        return await call_next(request)
