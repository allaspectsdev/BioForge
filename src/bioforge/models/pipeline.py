import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioforge.models.base import BaseModel


class PipelineDefinition(BaseModel):
    __tablename__ = "pipeline_definitions"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    definition: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    runs: Mapped[list["PipelineRun"]] = relationship(
        back_populates="pipeline_definition", cascade="all, delete-orphan"
    )


class PipelineRun(BaseModel):
    __tablename__ = "pipeline_runs"

    definition_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_definitions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    inputs: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    pipeline_definition: Mapped["PipelineDefinition"] = relationship(back_populates="runs")
    step_executions: Mapped[list["StepExecution"]] = relationship(
        back_populates="pipeline_run", cascade="all, delete-orphan"
    )
