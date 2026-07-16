from __future__ import annotations

from pydantic import BaseModel, Field


class SmartContextRequest(BaseModel):
    project: str = Field(..., min_length=1)
    conversation: str = ""
