"""BioForge AI Agent client wrapping the Anthropic API with multi-turn sessions."""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

import anthropic

from bioforge.agent.system_prompts import BIOFORGE_SYSTEM_PROMPT
from bioforge.agent.tools_registry import collect_capabilities
from bioforge.core.config import Settings
from bioforge.modules.registry import ModuleRegistry


def _serialize_content_blocks(content: Any) -> list[dict]:
    """Serialize Anthropic SDK content blocks to plain dicts for persistence.

    The API returns ToolUseBlock/TextBlock objects that can't be passed back
    directly on subsequent calls. Convert them to dict form.
    """
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    result = []
    for block in content:
        if isinstance(block, dict):
            result.append(block)
        elif hasattr(block, "type") and block.type == "tool_use":
            result.append({
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })
        elif hasattr(block, "type") and block.type == "text":
            result.append({"type": "text", "text": block.text})
        else:
            result.append({"type": "text", "text": str(block)})
    return result

logger = logging.getLogger(__name__)


@dataclass
class SessionMessage:
    """A single message in a conversation session."""

    role: str  # "user" | "assistant"
    content: Any  # str or list of content blocks
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Session:
    """In-memory representation of a conversation session."""

    id: UUID
    workspace_id: UUID
    project_id: UUID
    messages: list[SessionMessage] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    total_turns: int = 0
    status: str = "active"
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


@dataclass
class AgentResponse:
    """Response from the agent after processing a message."""

    text: str
    session_id: UUID
    turns_used: int
    tool_calls: list[dict] = field(default_factory=list)


class BioForgeAgent:
    """AI agent that can invoke bioinformatics tools via the Anthropic API.

    Supports both multi-turn persistent conversations and backward-compatible
    single-turn queries.
    """

    def __init__(self, registry: ModuleRegistry, settings: Settings):
        self.registry = registry
        self.settings = settings
        self._capabilities = collect_capabilities(registry)
        self._sessions: dict[UUID, Session] = {}

        if settings.anthropic_api_key:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self._client = None

        # Domain router for intent-based tool filtering
        from bioforge.agent.router import RouterAgent
        self._router = RouterAgent(registry)

        # Agent memory for cross-session knowledge
        from bioforge.agent.memory import AgentMemory
        self._memory = AgentMemory()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def start_session(self, workspace_id: UUID, project_id: UUID) -> UUID:
        """Create a new persistent conversation session."""
        session_id = uuid4()
        session = Session(
            id=session_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        self._sessions[session_id] = session
        logger.info(
            "Started agent session %s for workspace=%s project=%s",
            session_id,
            workspace_id,
            project_id,
        )
        return session_id

    def get_session(self, session_id: UUID) -> Session | None:
        """Retrieve a session by ID."""
        return self._sessions.get(session_id)

    def get_session_history(self, session_id: UUID) -> list[dict]:
        """Return the conversation history for a session as serializable dicts."""
        session = self._sessions.get(session_id)
        if session is None:
            return []
        history: list[dict] = []
        for msg in session.messages:
            content = msg.content
            # Flatten assistant content blocks to text for history endpoint
            if msg.role == "assistant" and isinstance(content, list):
                text_parts = []
                for block in content:
                    if hasattr(block, "text"):
                        text_parts.append(block.text)
                    elif isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block["text"])
                content = "".join(text_parts) if text_parts else str(content)
            history.append(
                {
                    "role": msg.role,
                    "content": content,
                    "timestamp": msg.timestamp.isoformat(),
                }
            )
        return history

    # ------------------------------------------------------------------
    # Multi-turn messaging
    # ------------------------------------------------------------------

    async def send_message(self, session_id: UUID, prompt: str) -> AgentResponse:
        """Send a message in an existing session.

        Loads full history, runs the agentic tool-use loop, persists
        messages, and returns the final response.
        """
        if self._client is None:
            return AgentResponse(
                text="Error: Anthropic API key not configured",
                session_id=session_id,
                turns_used=0,
            )

        session = self._sessions.get(session_id)
        if session is None:
            return AgentResponse(
                text=f"Error: session {session_id} not found",
                session_id=session_id,
                turns_used=0,
            )

        # Acquire session lock to prevent concurrent corruption
        async with session.lock:
            return await self._run_agentic_loop(session, prompt)

    async def _run_agentic_loop(self, session: Session, prompt: str) -> AgentResponse:
        """Run the agentic tool-use loop within a locked session."""
        session_id = session.id

        # 1. Build API-compatible message list from history
        api_messages = self._build_api_messages(session)

        # 2. Append user message
        session.messages.append(SessionMessage(role="user", content=prompt))
        api_messages.append({"role": "user", "content": prompt})

        # 3. Build system prompt with memory context
        memories = self._memory.recall(prompt, top_k=5)
        memory_context = ""
        if memories:
            memory_context = "\n\nRelevant context from prior sessions:\n" + "\n".join(
                f"- {m}" for m in memories
            )
        system = BIOFORGE_SYSTEM_PROMPT.format(
            workspace_id=str(session.workspace_id),
            project_id=str(session.project_id),
        ) + memory_context

        # 4. Route intent and select domain-specific tools
        domain = self._router.classify_intent(prompt)
        tools = self._router.get_tools_for_domain(domain)
        if not tools:
            tools = self._build_tools()  # Fall back to all tools
        tool_calls_log: list[dict] = []

        # 4. Agentic loop
        for turn in range(self.settings.agent_max_turns):
            response = await self._client.messages.create(
                model=self.settings.default_model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=api_messages,
            )

            if response.stop_reason == "tool_use":
                # Append assistant content (contains tool_use blocks)
                api_messages.append(
                    {"role": "assistant", "content": response.content}
                )
                # Persist intermediate assistant message so future calls
                # can reconstruct the full Anthropic message history.
                session.messages.append(
                    SessionMessage(role="assistant", content=_serialize_content_blocks(response.content))
                )

                # Execute each tool call
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._execute_tool(block.name, block.input)
                        result_str = (
                            json.dumps(result)
                            if isinstance(result, (dict, list))
                            else str(result)
                        )
                        tool_results.append(
                            {
                                "type": "tool_result",
                                "tool_use_id": block.id,
                                "content": result_str,
                            }
                        )
                        tool_calls_log.append(
                            {
                                "tool": block.name,
                                "input": block.input,
                                "output": result,
                            }
                        )

                api_messages.append({"role": "user", "content": tool_results})
                # Persist the tool results as a user message
                session.messages.append(
                    SessionMessage(role="user", content=tool_results)
                )
            else:
                # Final response -- extract text
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text

                # 5. Persist the assistant response
                session.messages.append(
                    SessionMessage(role="assistant", content=_serialize_content_blocks(response.content))
                )
                session.total_turns += turn + 1

                return AgentResponse(
                    text=text,
                    session_id=session_id,
                    turns_used=turn + 1,
                    tool_calls=tool_calls_log,
                )

        # Max turns exceeded
        session.messages.append(
            SessionMessage(
                role="assistant",
                content="I reached the maximum number of tool-use turns. "
                "Please try breaking your request into smaller steps.",
            )
        )
        return AgentResponse(
            text="Max turns exceeded",
            session_id=session_id,
            turns_used=self.settings.agent_max_turns,
            tool_calls=tool_calls_log,
        )

    # ------------------------------------------------------------------
    # Backward-compatible single-turn query
    # ------------------------------------------------------------------

    async def query(
        self,
        prompt: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Single-turn agent query with tool use loop.

        Creates a temporary session, sends one message, and returns the result.
        Maintains full backward compatibility with the original API.
        """
        if self._client is None:
            return {"error": "Anthropic API key not configured"}

        # Create ephemeral session
        session_id = await self.start_session(
            workspace_id=UUID(workspace_id),
            project_id=UUID(project_id),
        )

        resp = await self.send_message(session_id, prompt)

        # Clean up ephemeral session
        self._sessions.pop(session_id, None)

        if resp.text.startswith("Error:"):
            return {"error": resp.text, "turns": resp.turns_used}
        return {
            "response": resp.text,
            "turns": resp.turns_used,
            "tool_calls": resp.tool_calls,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_tools(self) -> list[dict]:
        """Build tool definitions for the Anthropic API."""
        tools = []
        for name, cap in self._capabilities.items():
            tools.append(
                {
                    "name": name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                }
            )
        return tools

    def _build_api_messages(self, session: Session) -> list[dict]:
        """Convert session history to Anthropic API message format."""
        api_messages: list[dict] = []
        for msg in session.messages:
            if msg.role == "user":
                api_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                # Content may be raw API content blocks or plain text
                api_messages.append({"role": "assistant", "content": msg.content})
        return api_messages

    async def _execute_tool(self, name: str, input_data: dict) -> Any:
        """Execute a tool by name."""
        cap = self._capabilities.get(name)
        if cap is None:
            return {"error": f"Unknown tool: {name}"}

        try:
            result = await cap.handler(input_data)
            return result
        except Exception as e:
            logger.exception("Tool execution failed: %s", name)
            return {"error": str(e)}
