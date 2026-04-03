"""Assembly sub-agent specializing in DNA assembly design."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import anthropic

from bioforge.agent.system_prompts import ASSEMBLY_SUB_AGENT_PROMPT
from bioforge.agent.tools_registry import collect_capabilities
from bioforge.core.config import Settings
from bioforge.modules.base import ModuleCapability
from bioforge.modules.registry import ModuleRegistry

logger = logging.getLogger(__name__)

# Capabilities relevant to assembly design
ASSEMBLY_TOOL_NAMES = [
    "design_assembly",
    "calculate_tm",
    "check_overhang_quality",
    "reverse_complement",
]


class AssemblySubAgent:
    """Specialized sub-agent for DNA assembly design tasks.

    Knows about Gibson Assembly vs Golden Gate Assembly selection criteria
    and has a system prompt encoding deep domain knowledge about:
    - Fragment boundary optimization
    - Overhang quality constraints (Tm, GC, orthogonality)
    - Type IIS restriction enzyme considerations
    - Protocol selection heuristics
    """

    def __init__(self, registry: ModuleRegistry, settings: Settings) -> None:
        self.registry = registry
        self.settings = settings
        all_caps = collect_capabilities(registry)
        self._capabilities: dict[str, ModuleCapability] = {
            name: cap for name, cap in all_caps.items() if name in ASSEMBLY_TOOL_NAMES
        }
        if settings.anthropic_api_key:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self._client = None

    def _build_tools(self) -> list[dict]:
        """Build assembly-specific tool definitions."""
        return [
            {
                "name": cap.name,
                "description": cap.description,
                "input_schema": cap.input_schema,
            }
            for cap in self._capabilities.values()
        ]

    async def handle(
        self,
        prompt: str,
        workspace_id: UUID,
        project_id: UUID,
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Handle an assembly-related query.

        Args:
            prompt: The user's natural language request.
            workspace_id: Active workspace UUID.
            project_id: Active project UUID.
            history: Optional prior conversation messages.

        Returns:
            Dict with 'response' text, 'turns' count, and 'tool_calls' list.
        """
        if self._client is None:
            return {"error": "Anthropic API key not configured"}

        system = ASSEMBLY_SUB_AGENT_PROMPT.format(
            workspace_id=str(workspace_id),
            project_id=str(project_id),
        )
        tools = self._build_tools()
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": prompt})
        tool_calls_log: list[dict] = []

        for turn in range(self.settings.agent_max_turns):
            response = await self._client.messages.create(
                model=self.settings.default_model,
                max_tokens=4096,
                system=system,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": response.content})

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

                messages.append({"role": "user", "content": tool_results})
            else:
                text = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text += block.text
                return {
                    "response": text,
                    "turns": turn + 1,
                    "tool_calls": tool_calls_log,
                }

        return {
            "error": "Max turns exceeded",
            "turns": self.settings.agent_max_turns,
            "tool_calls": tool_calls_log,
        }

    async def _execute_tool(self, name: str, input_data: dict) -> Any:
        """Execute an assembly tool by name."""
        cap = self._capabilities.get(name)
        if cap is None:
            return {"error": f"Unknown assembly tool: {name}"}
        try:
            return await cap.handler(input_data)
        except Exception as e:
            logger.exception("Assembly tool execution failed: %s", name)
            return {"error": str(e)}
