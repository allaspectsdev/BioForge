from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    workspace_id: UUID
    name: str = Field(max_length=255)
    description: str | None = None
    metadata: dict = Field(default_factory=dict)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    metadata: dict | None = None


class ProjectRead(BaseModel):
    model_config = {"from_attributes": True, "populate_by_name": True}

    id: UUID
    workspace_id: UUID
    name: str
    description: str | None
    metadata: dict = Field(default_factory=dict, alias="metadata_")
    created_at: datetime
    updated_at: datetime
