"""Agent session persistence."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.agent_session import AgentSession, AgentToolCall


class AgentSessionManager:
    """Manages agent session lifecycle and tool call logging."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    async def create_session(
        self, workspace_id: UUID, project_id: UUID
    ) -> AgentSession:
        session = AgentSession(
            workspace_id=workspace_id,
            project_id=project_id,
            status="active",
        )
        self.db.add(session)
        await self.db.flush()
        await self.db.refresh(session)
        return session

    async def log_tool_call(
        self,
        session_id: UUID,
        tool_name: str,
        tool_input: dict,
        tool_output: dict,
        duration_ms: int = 0,
        is_error: bool = False,
    ) -> AgentToolCall:
        call = AgentToolCall(
            session_id=session_id,
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output,
            duration_ms=duration_ms,
            is_error=is_error,
        )
        self.db.add(call)
        await self.db.flush()
        return call

    async def close_session(self, session_id: UUID) -> None:
        session = await self.db.get(AgentSession, session_id)
        if session:
            session.status = "closed"
            await self.db.flush()
