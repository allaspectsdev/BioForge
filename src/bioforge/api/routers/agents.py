"""Agent API endpoints with multi-turn session support."""

from datetime import datetime, timezone, UTC
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from bioforge.api.deps import get_settings
from bioforge.core.config import Settings
from bioforge.modules.registry import ModuleRegistry
from bioforge.schemas.agent import (
    AgentQuery,
    AgentResponse,
    ConversationHistoryResponse,
    ConversationMessage,
    CreateSessionRequest,
    CreateSessionResponse,
    SendMessageRequest,
    SendMessageResponse,
)

router = APIRouter()

# In-memory singleton agent instance. In production this would be managed
# by a proper dependency injection container or application state.
_agent_instance = None


def _get_agent(settings: Settings = Depends(get_settings)):
    """Get or create the BioForge agent singleton.

    Lazily registers all available modules.
    """
    global _agent_instance
    if _agent_instance is not None:
        return _agent_instance

    from bioforge.agent.client import BioForgeAgent

    registry = ModuleRegistry()

    # Register all available modules
    try:
        from bioforge.modules.assembly.module import AssemblyModule
        registry.register(AssemblyModule())
    except ImportError:
        pass

    try:
        from bioforge.modules.alignment.module import AlignmentModule
        registry.register(AlignmentModule())
    except ImportError:
        pass

    try:
        from bioforge.modules.variants.module import VariantModule
        registry.register(VariantModule())
    except ImportError:
        pass

    try:
        from bioforge.modules.experiments.module import ExperimentModule
        registry.register(ExperimentModule())
    except ImportError:
        pass

    try:
        from bioforge.modules.sbol.module import SBOLModule
        registry.register(SBOLModule())
    except ImportError:
        pass

    try:
        from bioforge.modules.evo2.module import Evo2Module
        registry.register(Evo2Module())
    except ImportError:
        pass

    try:
        from bioforge.modules.structure.module import StructureModule
        registry.register(StructureModule())
    except ImportError:
        pass

    _agent_instance = BioForgeAgent(registry, settings)
    return _agent_instance


# ------------------------------------------------------------------
# Session endpoints
# ------------------------------------------------------------------


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    body: CreateSessionRequest,
    agent=Depends(_get_agent),
):
    """Create a new persistent conversation session."""
    session_id = await agent.start_session(body.workspace_id, body.project_id)
    session = agent.get_session(session_id)
    return CreateSessionResponse(
        session_id=session_id,
        workspace_id=body.workspace_id,
        project_id=body.project_id,
        created_at=session.created_at if session else datetime.now(UTC),
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=SendMessageResponse,
)
async def send_message(
    session_id: UUID,
    body: SendMessageRequest,
    agent=Depends(_get_agent),
):
    """Send a message in an existing session."""
    session = agent.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not agent.settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured. Set BIOFORGE_ANTHROPIC_API_KEY.",
        )

    resp = await agent.send_message(session_id, body.prompt)
    return SendMessageResponse(
        session_id=session_id,
        text=resp.text,
        turns_used=resp.turns_used,
        tool_calls=resp.tool_calls,
    )


@router.get(
    "/sessions/{session_id}/messages",
    response_model=ConversationHistoryResponse,
)
async def get_conversation_history(
    session_id: UUID,
    agent=Depends(_get_agent),
):
    """Get the full conversation history for a session."""
    session = agent.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    history = agent.get_session_history(session_id)
    messages = [
        ConversationMessage(
            role=msg["role"],
            content=msg["content"],
            timestamp=msg["timestamp"],
        )
        for msg in history
    ]
    return ConversationHistoryResponse(session_id=session_id, messages=messages)


@router.post(
    "/sessions/{session_id}/messages/stream",
)
async def send_message_stream(
    session_id: UUID,
    body: SendMessageRequest,
    agent=Depends(_get_agent),
):
    """Send a message and receive SSE-streamed response."""
    session = agent.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    if not agent.settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured. Set BIOFORGE_ANTHROPIC_API_KEY.",
        )

    from bioforge.agent.streaming import stream_agent_response

    return StreamingResponse(
        stream_agent_response(agent, session_id, body.prompt),
        media_type="text/event-stream",
    )


# ------------------------------------------------------------------
# Backward-compatible single-turn endpoint
# ------------------------------------------------------------------


@router.post("/query", response_model=AgentResponse)
async def agent_query(body: AgentQuery, agent=Depends(_get_agent)):
    """Send a natural language query to the BioForge AI agent.

    This is the backward-compatible single-turn endpoint. It creates a
    temporary session, processes one message, and returns the result.
    """
    if not agent.settings.anthropic_api_key:
        raise HTTPException(
            status_code=503,
            detail="Anthropic API key not configured. Set BIOFORGE_ANTHROPIC_API_KEY.",
        )
    result = await agent.query(
        prompt=body.prompt,
        workspace_id=str(body.workspace_id),
        project_id=str(body.project_id),
    )
    return AgentResponse(result=result)
