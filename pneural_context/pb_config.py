from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass
class PBConfig:
    database_url: str = ""
    llm_url: str = "http://localhost:12345/v1"
    llm_model: str = "local-model"
    llm_api_key: str = ""
    llm_launch_cmd: str = ""
    host: str = "0.0.0.0"
    port: int = 8777
    memoria_url: str = ""
    memoria_enabled: bool = False
    decay_interval_seconds: float = 21600.0
    consolidation_interval_seconds: float = 21600.0
    archive_threshold: float = 0.1
    embed_backend: str = "ollama"
    embed_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    embed_dimensions: int = 768
    embed_batch_size: int = 32
    dedup_threshold_high: float = 0.85
    dedup_threshold_low: float = 0.55
    dedup_conversation_messages: int = 10
    api_key: str = ""

    @classmethod
    def from_env(cls) -> PBConfig:
        return cls(
            database_url=os.environ.get("PNEURAL_DATABASE_URL", ""),
            llm_url=os.environ.get("PNEURAL_LLM_URL", "http://localhost:12345/v1"),
            llm_model=os.environ.get("PNEURAL_LLM_MODEL", "local-model"),
            llm_api_key=os.environ.get("PNEURAL_LLM_API_KEY", ""),
            llm_launch_cmd=os.environ.get("PNEURAL_LLM_LAUNCH_CMD", ""),
            host=os.environ.get("PNEURAL_HOST", "0.0.0.0"),
            port=int(os.environ.get("PNEURAL_PORT", "8777")),
            memoria_url=os.environ.get("PNEURAL_MEMORIA_URL", ""),
            memoria_enabled=os.environ.get("PNEURAL_MEMORIA_ENABLED", "").lower()
            in ("1", "true", "yes"),
            decay_interval_seconds=float(os.environ.get("PNEURAL_DECAY_INTERVAL", "21600")),
            consolidation_interval_seconds=float(
                os.environ.get("PNEURAL_CONSOLIDATION_INTERVAL", "21600")
            ),
            archive_threshold=float(os.environ.get("PNEURAL_ARCHIVE_THRESHOLD", "0.1")),
            embed_backend=os.environ.get("PNEURAL_EMBED_BACKEND", "ollama"),
            embed_url=os.environ.get("PNEURAL_EMBED_URL", "http://localhost:11434"),
            embed_model=os.environ.get("PNEURAL_EMBED_MODEL", "nomic-embed-text"),
            embed_dimensions=int(os.environ.get("PNEURAL_EMBED_DIMENSIONS", "768")),
            embed_batch_size=int(os.environ.get("PNEURAL_EMBED_BATCH_SIZE", "32")),
            dedup_threshold_high=float(os.environ.get("PNEURAL_DEDUP_THRESHOLD_HIGH", "0.85")),
            dedup_threshold_low=float(os.environ.get("PNEURAL_DEDUP_THRESHOLD_LOW", "0.55")),
            dedup_conversation_messages=int(
                os.environ.get("PNEURAL_DEDUP_CONVERSATION_MESSAGES", "10")
            ),
            api_key=os.environ.get("PNEURAL_API_KEY", ""),
        )

    @classmethod
    def load_from_file(cls, path: str) -> PBConfig:
        with open(path) as f:
            data = json.load(f)
        base = cls.from_env()
        for k, v in data.items():
            if hasattr(base, k):
                setattr(base, k, v)
        return base
