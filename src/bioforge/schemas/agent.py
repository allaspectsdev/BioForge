"""Pydantic schemas for agent API endpoints."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentQuery(BaseModel):
    """Backward-compatible single-turn query."""

    prompt: str
    workspace_id: UUID
    project_id: UUID


class AgentResponse(BaseModel):
    """Response from a single-turn query."""

    result: Any
    session_id: UUID | None = None


class CreateSessionRequest(BaseModel):
    """Request to create a new agent conversation session."""

    workspace_id: UUID
    project_id: UUID


class CreateSessionResponse(BaseModel):
    """Response after creating a new session."""

    session_id: UUID
    workspace_id: UUID
    project_id: UUID
    created_at: datetime


class SendMessageRequest(BaseModel):
    """Send a message within an existing session."""

    prompt: str


class SendMessageResponse(BaseModel):
    """Response from a session message."""

    session_id: UUID
    text: str
    turns_used: int
    tool_calls: list[dict] = Field(default_factory=list)


class ConversationMessage(BaseModel):
    """A single message in the conversation history."""

    role: str
    content: Any
    timestamp: str


class ConversationHistoryResponse(BaseModel):
    """Full conversation history for a session."""

    session_id: UUID
    messages: list[ConversationMessage]


class AgentSessionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    workspace_id: UUID
    project_id: UUID
    status: str
    total_cost_usd: float
    total_turns: int
    created_at: datetime
