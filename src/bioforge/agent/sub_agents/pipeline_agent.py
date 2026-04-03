"""Pipeline sub-agent that can construct pipeline DAGs from natural language."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import UUID

import anthropic

from bioforge.agent.system_prompts import PIPELINE_SUB_AGENT_PROMPT
from bioforge.agent.tools_registry import collect_capabilities
from bioforge.core.config import Settings
from bioforge.modules.base import ModuleCapability
from bioforge.modules.registry import ModuleRegistry

logger = logging.getLogger(__name__)


class PipelineSubAgent:
    """Specialized sub-agent for bioinformatics pipeline construction.

    Can parse natural language descriptions of workflows and translate them
    into executable pipeline DAGs. Understands common bioinformatics
    patterns like scatter-gather, fan-out/fan-in, and linear processing chains.
    """

    def __init__(self, registry: ModuleRegistry, settings: Settings) -> None:
        self.registry = registry
        self.settings = settings
        all_caps = collect_capabilities(registry)
        # Pipeline agent has access to all capabilities since any
        # module capability can be a pipeline step
        self._capabilities: dict[str, ModuleCapability] = all_caps
        self._pipeline_steps = registry.all_pipeline_steps()

        if settings.anthropic_api_key:
            self._client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        else:
            self._client = None

    def _build_tools(self) -> list[dict]:
        """Build pipeline-oriented tool definitions.

        Includes a meta-tool for constructing DAGs plus any registered
        pipeline steps from modules.
        """
        tools: list[dict] = [
            {
                "name": "construct_pipeline_dag",
                "description": (
                    "Construct a pipeline DAG from a list of steps. Each step has a "
                    "name, step_type, params dict, and depends_on list of step names. "
                    "Returns the validated DAG structure."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for this pipeline",
                        },
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "step_type": {"type": "string"},
                                    "params": {"type": "object"},
                                    "depends_on": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    },
                                },
                                "required": ["name", "step_type"],
                            },
                        },
                    },
                    "required": ["name", "steps"],
                },
            },
            {
                "name": "list_available_step_types",
                "description": "List all available pipeline step types from loaded modules.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
        # Also include regular module tools that could be part of pipelines
        for cap in self._capabilities.values():
            tools.append(
                {
                    "name": cap.name,
                    "description": cap.description,
                    "input_schema": cap.input_schema,
                }
            )
        return tools

    async def handle(
        self,
        prompt: str,
        workspace_id: UUID,
        project_id: UUID,
        history: list[dict] | None = None,
    ) -> dict[str, Any]:
        """Handle a pipeline-related query.

        Args:
            prompt: The user's natural language request.
            workspace_id: Active workspace UUID.
            project_id: Active project UUID.
            history: Optional prior conversation messages.

        Returns:
            Dict with 'response' text, 'turns' count, and optionally 'pipeline' DAG.
        """
        if self._client is None:
            return {"error": "Anthropic API key not configured"}

        system = PIPELINE_SUB_AGENT_PROMPT.format(
            workspace_id=str(workspace_id),
            project_id=str(project_id),
        )
        tools = self._build_tools()
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": prompt})
        tool_calls_log: list[dict] = []
        pipeline_dag: dict | None = None

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
                        if block.name == "construct_pipeline_dag":
                            pipeline_dag = result
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
                result = {
                    "response": text,
                    "turns": turn + 1,
                    "tool_calls": tool_calls_log,
                }
                if pipeline_dag is not None:
                    result["pipeline"] = pipeline_dag
                return result

        return {
            "error": "Max turns exceeded",
            "turns": self.settings.agent_max_turns,
            "tool_calls": tool_calls_log,
        }

    async def _execute_tool(self, name: str, input_data: dict) -> Any:
        """Execute a pipeline-related tool by name."""
        if name == "construct_pipeline_dag":
            return self._construct_dag(input_data)
        if name == "list_available_step_types":
            return self._list_step_types()

        cap = self._capabilities.get(name)
        if cap is None:
            return {"error": f"Unknown tool: {name}"}
        try:
            return await cap.handler(input_data)
        except Exception as e:
            logger.exception("Pipeline tool execution failed: %s", name)
            return {"error": str(e)}

    def _construct_dag(self, input_data: dict) -> dict:
        """Construct and validate a pipeline DAG from step definitions."""
        pipeline_name = input_data.get("name", "unnamed_pipeline")
        steps_raw = input_data.get("steps", [])

        # Build step lookup
        steps: list[dict] = []
        step_names: set[str] = set()
        for s in steps_raw:
            step_name = s.get("name", "")
            step_type = s.get("step_type", "")
            params = s.get("params", {})
            depends_on = s.get("depends_on", [])

            if step_name in step_names:
                return {"error": f"Duplicate step name: {step_name}"}
            step_names.add(step_name)

            steps.append(
                {
                    "name": step_name,
                    "step_type": step_type,
                    "params": params,
                    "depends_on": depends_on,
                }
            )

        # Validate dependencies
        for step in steps:
            for dep in step["depends_on"]:
                if dep not in step_names:
                    return {"error": f"Step '{step['name']}' depends on unknown step '{dep}'"}

        # Check for cycles (simple DFS)
        visited: set[str] = set()
        in_stack: set[str] = set()
        step_map = {s["name"]: s for s in steps}

        def has_cycle(node: str) -> bool:
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in step_map[node]["depends_on"]:
                if has_cycle(dep):
                    return True
            in_stack.discard(node)
            return False

        for step in steps:
            if has_cycle(step["name"]):
                return {"error": "Pipeline DAG contains a cycle"}

        return {
            "name": pipeline_name,
            "steps": steps,
            "step_count": len(steps),
            "valid": True,
        }

    def _list_step_types(self) -> dict:
        """List all available pipeline step types."""
        step_types = []
        for step_type, step in self._pipeline_steps.items():
            step_types.append(
                {
                    "step_type": step_type,
                    "description": step.description,
                    "input_ports": step.input_ports,
                    "output_ports": step.output_ports,
                }
            )
        return {"step_types": step_types, "count": len(step_types)}
