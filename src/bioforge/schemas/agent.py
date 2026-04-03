from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentQuery(BaseModel):
    prompt: str
    workspace_id: UUID
    project_id: UUID


class AgentResponse(BaseModel):
    result: Any
    session_id: UUID | None = None


class AgentSessionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    workspace_id: UUID
    project_id: UUID
    status: str
    total_cost_usd: float
    total_turns: int
    created_at: datetime
