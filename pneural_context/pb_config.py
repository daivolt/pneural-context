from __future__ import annotations

import json
import os
from dataclasses import dataclass, field


@dataclass
class PBConfig:
    database_url: str = ""
    llm_url: str = "http://localhost:12345/v1"
    llm_model: str = "local-model"
    llm_api_key: str = ""
    host: str = "0.0.0.0"
    port: int = 8777
    memoria_url: str = ""
    memoria_enabled: bool = False
    decay_interval_seconds: float = 21600.0
    consolidation_interval_seconds: float = 21600.0
    archive_threshold: float = 0.1

    @classmethod
    def from_env(cls) -> PBConfig:
        return cls(
            database_url=os.environ.get("PNEURAL_DATABASE_URL", ""),
            llm_url=os.environ.get("PNEURAL_LLM_URL", "http://localhost:12345/v1"),
            llm_model=os.environ.get("PNEURAL_LLM_MODEL", "local-model"),
            llm_api_key=os.environ.get("PNEURAL_LLM_API_KEY", ""),
            host=os.environ.get("PNEURAL_HOST", "0.0.0.0"),
            port=int(os.environ.get("PNEURAL_PORT", "8777")),
            memoria_url=os.environ.get("PNEURAL_MEMORIA_URL", ""),
            memoria_enabled=os.environ.get("PNEURAL_MEMORIA_ENABLED", "").lower()
            in ("1", "true", "yes"),
            decay_interval_seconds=float(
                os.environ.get("PNEURAL_DECAY_INTERVAL", "21600")
            ),
            consolidation_interval_seconds=float(
                os.environ.get("PNEURAL_CONSOLIDATION_INTERVAL", "21600")
            ),
            archive_threshold=float(os.environ.get("PNEURAL_ARCHIVE_THRESHOLD", "0.1")),
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
