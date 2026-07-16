from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class RecordCostRequest(BaseModel):
    project: str = ""
    session_id: str = ""
    tokens_injected: int = 0
    tokens_saved_injection: int = 0
    tokens_saved_forgetting: int = 0
    context_type: str = "full"
    task_outcome: str = ""
    breakdown: dict[str, Any] | None = None
