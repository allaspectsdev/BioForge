import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioforge.models.base import BaseModel

if TYPE_CHECKING:
    from bioforge.models.project import Project


class Workspace(BaseModel):
    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    owner_id: Mapped[uuid.UUID | None] = mapped_column()
    settings: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    projects: Mapped[list["Project"]] = relationship(
        back_populates="workspace", cascade="all, delete-orphan"
    )
