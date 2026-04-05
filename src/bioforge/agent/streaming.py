"""SSE (Server-Sent Events) streaming adapter for the BioForge agent."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

logger = logging.getLogger(__name__)


def _sse_event(event_type: str, data: Any) -> str:
    """Format a single SSE event string."""
    payload = json.dumps(data) if not isinstance(data, str) else data
    return f"event: {event_type}\ndata: {payload}\n\n"


async def stream_agent_response(
    agent: Any,
    session_id: Any,
    prompt: str,
) -> AsyncGenerator[str, None]:
    """Async generator that yields SSE-formatted events during agent execution.

    Event types:
        - "token": text chunk from the assistant
        - "tool_start": a tool call is beginning (includes tool name and input)
        - "tool_result": a tool call has completed (includes output)
        - "error": an error occurred
        - "done": the agent has finished responding

    This adapter wraps the standard send_message flow. For true
    token-level streaming, the Anthropic streaming API would be used
    directly; this implementation emits the final text as a single
    token event, with granular tool events along the way.
    """
    from bioforge.agent.client import BioForgeAgent

    if not isinstance(agent, BioForgeAgent):
        yield _sse_event("error", {"message": "Invalid agent instance"})
        yield _sse_event("done", {})
        return

    if agent._client is None:
        yield _sse_event("error", {"message": "Anthropic API key not configured"})
        yield _sse_event("done", {})
        return

    session = agent.get_session(session_id)
    if session is None:
        yield _sse_event("error", {"message": f"Session {session_id} not found"})
        yield _sse_event("done", {})
        return

    try:
        # Use the Anthropic streaming API if available
        import anthropic

        from bioforge.agent.system_prompts import BIOFORGE_SYSTEM_PROMPT

        system = BIOFORGE_SYSTEM_PROMPT.format(
            workspace_id=str(session.workspace_id),
            project_id=str(session.project_id),
        )
        tools = agent._build_tools()

        # Build messages from history + new prompt
        api_messages = agent._build_api_messages(session)
        from bioforge.agent.client import SessionMessage

        session.messages.append(SessionMessage(role="user", content=prompt))
        api_messages.append({"role": "user", "content": prompt})

        for turn in range(agent.settings.agent_max_turns):
            # Use streaming for the API call
            collected_content: list[Any] = []
            stop_reason = None

            async with agent._client.messages.stream(
                model=agent.settings.default_model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=api_messages,
            ) as stream:
                async for event in stream:
                    if hasattr(event, "type"):
                        if event.type == "content_block_start":
                            block = event.content_block
                            if hasattr(block, "type") and block.type == "tool_use":
                                yield _sse_event(
                                    "tool_start",
                                    {"tool": block.name, "id": block.id},
                                )
                        elif event.type == "content_block_delta":
                            delta = event.delta
                            if hasattr(delta, "text"):
                                yield _sse_event("token", {"text": delta.text})
                            elif hasattr(delta, "partial_json"):
                                pass  # Tool input accumulating
                        elif event.type == "message_delta":
                            if hasattr(event, "delta") and hasattr(event.delta, "stop_reason"):
                                stop_reason = event.delta.stop_reason

                response = await stream.get_final_message()

            if stop_reason == "tool_use" or (response and response.stop_reason == "tool_use"):
                api_messages.append(
                    {"role": "assistant", "content": response.content}
                )

                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await agent._execute_tool(block.name, block.input)
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
                        yield _sse_event(
                            "tool_result",
                            {
                                "tool": block.name,
                                "id": block.id,
                                "result": result,
                            },
                        )

                api_messages.append({"role": "user", "content": tool_results})
            else:
                # Final response
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text

                from bioforge.agent.client import _serialize_content_blocks
                session.messages.append(
                    SessionMessage(role="assistant", content=_serialize_content_blocks(response.content))
                )
                session.total_turns += turn + 1

                yield _sse_event("done", {"turns": turn + 1, "text_length": len(text)})
                return

        yield _sse_event(
            "error", {"message": "Max turns exceeded"}
        )
        yield _sse_event("done", {})

    except anthropic.APIError as exc:
        logger.exception("Anthropic API error during streaming")
        yield _sse_event("error", {"message": str(exc)})
        yield _sse_event("done", {})
    except Exception as exc:
        logger.exception("Unexpected error during streaming")
        yield _sse_event("error", {"message": str(exc)})
        yield _sse_event("done", {})


async def stream_simple(text: str) -> AsyncGenerator[str, None]:
    """Utility: stream a pre-computed text as a series of token events.

    Useful for returning non-streaming results through an SSE endpoint.
    """
    # Split into ~100 char chunks to simulate streaming
    chunk_size = 100
    for i in range(0, len(text), chunk_size):
        yield _sse_event("token", {"text": text[i : i + chunk_size]})
    yield _sse_event("done", {})
