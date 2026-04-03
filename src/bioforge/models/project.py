import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioforge.models.base import BaseModel

if TYPE_CHECKING:
    from bioforge.models.sequence import Sequence
    from bioforge.models.workspace import Workspace


class Project(BaseModel):
    __tablename__ = "projects"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )

    workspace: Mapped["Workspace"] = relationship(back_populates="projects")
    sequences: Mapped[list["Sequence"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
