"""BioForge AI Agent client wrapping the Anthropic API."""

import logging
from typing import Any

import anthropic

from bioforge.agent.system_prompts import BIOFORGE_SYSTEM_PROMPT
from bioforge.agent.tools_registry import collect_capabilities
from bioforge.core.config import Settings
from bioforge.modules.registry import ModuleRegistry

logger = logging.getLogger(__name__)


class BioForgeAgent:
    """AI agent that can invoke bioinformatics tools via the Anthropic API."""

    def __init__(self, registry: ModuleRegistry, settings: Settings):
        self.registry = registry
        self.settings = settings
        self._capabilities = collect_capabilities(registry)

        if settings.anthropic_api_key:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self._client = None

    def _build_tools(self) -> list[dict]:
        """Build tool definitions for the Anthropic API."""
        tools = []
        for name, cap in self._capabilities.items():
            tools.append({
                "name": name,
                "description": cap.description,
                "input_schema": cap.input_schema,
            })
        return tools

    async def query(
        self,
        prompt: str,
        workspace_id: str,
        project_id: str,
    ) -> dict[str, Any]:
        """Single-turn agent query with tool use loop."""
        if self._client is None:
            return {"error": "Anthropic API key not configured"}

        system = BIOFORGE_SYSTEM_PROMPT.format(
            workspace_id=workspace_id,
            project_id=project_id,
        )
        tools = self._build_tools()
        messages: list[dict] = [{"role": "user", "content": prompt}]

        for turn in range(self.settings.agent_max_turns):
            response = await self._client.messages.create(
                model=self.settings.default_model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=messages,
            )

            # Check if we need to handle tool calls
            if response.stop_reason == "tool_use":
                # Append assistant message
                messages.append({"role": "assistant", "content": response.content})

                # Process tool calls
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = await self._execute_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": str(result),
                        })

                messages.append({"role": "user", "content": tool_results})
            else:
                # Final response
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                return {"response": text, "turns": turn + 1}

        return {"error": "Max turns exceeded", "turns": self.settings.agent_max_turns}

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
