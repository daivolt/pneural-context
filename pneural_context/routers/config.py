from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from ..models.config import ConfigUpdateRequest

logger = logging.getLogger("pneural_context.routers.config")

router = APIRouter(prefix="/api/config", tags=["config"])

CONFIG_PATH = Path(
    os.environ.get("PNEURAL_CONFIG_FILE", str(Path.home() / ".pneural-context" / "config.json"))
)


def _load_config_file() -> dict[str, object]:
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())  # type: ignore[no-any-return]
        except Exception:
            logger.warning("Failed to load config file", exc_info=True)
    return {}


def _save_config_file(data: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_config_file()
    existing.update(data)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2))


@router.get("")
async def get_config(request: Request) -> dict:
    config = request.app.state.config
    stored = _load_config_file()
    safe_stored = {k: v for k, v in stored.items() if k not in ("llm_api_key", "database_url")}
    current = {k: v for k, v in config.__dict__.items() if k not in ("llm_api_key", "database_url")}
    current["stored_config"] = safe_stored
    current["llm_api_key_set"] = bool(config.llm_api_key)
    current["database_url_set"] = bool(config.database_url)
    return current


@router.patch("")
async def update_config(body: ConfigUpdateRequest, request: Request) -> dict:
    from .. import pb_db
    from ..pb_embeddings import create_embedding_client
    from ..pb_llm import LLMClient
    from ..pb_memoria import MemoriaBridge

    config = request.app.state.config

    updates: dict[str, object] = {}
    for field_name, value in body.model_dump(exclude_none=True).items():
        if value is None:
            continue
        updates[field_name] = value

    if not updates:
        raise HTTPException(400, "No valid config fields to update")

    _save_config_file(updates)

    for k, v in updates.items():
        if k in ("llm_api_key", "database_url"):
            continue
        if hasattr(config, k):
            setattr(config, k, v)

    if any(k.startswith("llm_") for k in updates):
        request.app.state.llm_client = LLMClient(
            url=config.llm_url, model=config.llm_model, api_key=config.llm_api_key
        )
    if any(k.startswith("embed_") for k in updates):
        embedding_client = create_embedding_client(config)
        request.app.state.embedding_client = embedding_client
        if embedding_client:
            pb_db.init_embedding_client(embedding_client)
    if any(k.startswith("memoria_") for k in updates):
        if config.memoria_enabled and config.memoria_url:
            request.app.state.memoria = MemoriaBridge(config.memoria_url)
        else:
            request.app.state.memoria = None

    return {"ok": True, "updated": list(updates.keys())}
