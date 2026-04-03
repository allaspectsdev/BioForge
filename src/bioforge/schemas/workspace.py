from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(max_length=255)
    description: str | None = None
    settings: dict = Field(default_factory=dict)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    settings: dict | None = None


class WorkspaceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    name: str
    description: str | None
    settings: dict
    created_at: datetime
    updated_at: datetime
