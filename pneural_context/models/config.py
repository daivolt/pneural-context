from __future__ import annotations

from pydantic import BaseModel


class ConfigUpdateRequest(BaseModel):
    llm_url: str | None = None
    llm_model: str | None = None
    host: str | None = None
    port: int | None = None
    memoria_url: str | None = None
    memoria_enabled: bool | None = None
    decay_interval_seconds: float | None = None
    consolidation_interval_seconds: float | None = None
    archive_threshold: float | None = None
    embed_backend: str | None = None
    embed_url: str | None = None
    embed_model: str | None = None
    embed_dimensions: int | None = None
    embed_batch_size: int | None = None
    dedup_threshold_high: float | None = None
    dedup_threshold_low: float | None = None
    dedup_conversation_messages: int | None = None
