from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class RecordSessionRequest(BaseModel):
    project: str = Field(..., min_length=1)
    session_id: str = ""
    title: str = ""
    messages: list[dict] = Field(..., min_length=1)
    memory_type: Literal["red", "concept", "procedural", "temporal", "relation"] = "temporal"

    @field_validator("messages")
    @classmethod
    def messages_must_be_nonempty(cls, v: list[dict]) -> list[dict]:
        if not v:
            raise ValueError("messages must be a non-empty list")
        return v
