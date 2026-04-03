import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bioforge.models.base import BaseModel


class AgentSession(BaseModel):
    __tablename__ = "agent_sessions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE")
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE")
    )
    sdk_session_id: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default="active", server_default="active")
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    total_turns: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    tool_calls: Mapped[list["AgentToolCall"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AgentToolCall(BaseModel):
    __tablename__ = "agent_tool_calls"

    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(String(255))
    tool_input: Mapped[dict | None] = mapped_column(JSONB)
    tool_output: Mapped[dict | None] = mapped_column(JSONB)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    is_error: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    session: Mapped["AgentSession"] = relationship(back_populates="tool_calls")
