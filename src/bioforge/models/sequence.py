import uuid
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioforge.models.base import BaseModel

if TYPE_CHECKING:
    from bioforge.models.project import Project


class Sequence(BaseModel):
    __tablename__ = "sequences"
    __table_args__ = (
        CheckConstraint("sequence_type IN ('dna', 'rna', 'protein')", name="ck_sequence_type"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    sequence_type: Mapped[str] = mapped_column(String(20))
    sequence_data: Mapped[str] = mapped_column(Text)
    storage_key: Mapped[str | None] = mapped_column(String(512))
    length: Mapped[int] = mapped_column(Integer)
    gc_content: Mapped[float | None] = mapped_column(Float)
    annotations: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    source_format: Mapped[str | None] = mapped_column(String(20))
    checksum: Mapped[str | None] = mapped_column(String(64))

    project: Mapped["Project"] = relationship(back_populates="sequences")
