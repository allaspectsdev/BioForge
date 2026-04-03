from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PipelineStepConfig(BaseModel):
    step_type: str
    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, str] = Field(default_factory=dict)
    container: str | None = None


class PipelineCreate(BaseModel):
    project_id: UUID
    name: str = Field(max_length=255)
    description: str | None = None
    steps: list[PipelineStepConfig]


class PipelineRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    definition: dict
    version: int
    created_at: datetime
    updated_at: datetime


class PipelineRunCreate(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)


class PipelineRunRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    definition_id: UUID
    status: str
    inputs: dict | None
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None
    created_at: datetime


class StepExecutionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    step_name: str
    step_type: str
    status: str
    inputs: dict | None
    outputs: dict | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    error_message: str | None
