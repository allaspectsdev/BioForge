import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bioforge.models.base import BaseModel


class Result(BaseModel):
    __tablename__ = "results"

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    pipeline_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("pipeline_runs.id")
    )
    result_type: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255))
    summary: Mapped[dict | None] = mapped_column(JSONB)
    data: Mapped[dict | None] = mapped_column(JSONB)
    storage_key: Mapped[str | None] = mapped_column(String(512))
