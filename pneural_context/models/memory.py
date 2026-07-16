from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AddMemoryRequest(BaseModel):
    project: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    priority: Literal["critical", "important", "normal"] = "normal"
    memory_type: str | None = None


class TouchRequest(BaseModel):
    project: str = ""
    index: int | None = None
    ids: list[int] | None = None


class BoostRequest(BaseModel):
    project: str = ""
    index: int


class ReplaceRequest(BaseModel):
    project: str = ""
    old: str = Field(..., min_length=1)
    new: str = Field(..., min_length=1)


class ClassifyRequest(BaseModel):
    project: str = ""
