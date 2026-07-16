from __future__ import annotations

from pydantic import BaseModel


class AddProcedureRequest(BaseModel):
    project: str = ""
    task_pattern: str = ""
    task_type: str | None = None
    steps: list[str] = []
    proven_by: str = ""


class OutcomeRequest(BaseModel):
    success: bool = True
    proven_by: str = ""
