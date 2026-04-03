from sqlalchemy import Boolean, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from bioforge.models.base import BaseModel


class InstalledModule(BaseModel):
    __tablename__ = "installed_modules"

    name: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
