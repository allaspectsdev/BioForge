import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioforge.models.base import BaseModel
from bioforge.models.pipeline import PipelineRun


class StepExecution(BaseModel):
    __tablename__ = "step_executions"

    pipeline_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("pipeline_runs.id", ondelete="CASCADE")
    )
    step_name: Mapped[str] = mapped_column(String(255))
    step_type: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="pending", server_default="pending")
    inputs: Mapped[dict | None] = mapped_column(JSONB)
    outputs: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)

    pipeline_run: Mapped["PipelineRun"] = relationship(back_populates="step_executions")
