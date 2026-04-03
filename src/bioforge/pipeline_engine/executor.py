"""Pipeline execution engine: async parallel step execution."""

import asyncio
import logging
import time
from typing import Any
from uuid import UUID

from bioforge.core.exceptions import PipelineError
from bioforge.modules.base import ModulePipelineStep
from bioforge.pipeline_engine.dsl import PipelineDefinition
from bioforge.pipeline_engine.graph import PipelineGraph

logger = logging.getLogger(__name__)


class PipelineExecutor:
    """Execute a pipeline DAG with parallel step scheduling."""

    def __init__(self, step_registry: dict[str, ModulePipelineStep]):
        self.step_registry = step_registry

    async def execute(
        self,
        definition: PipelineDefinition,
        initial_inputs: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute a pipeline, returning outputs keyed by step name."""
        graph = PipelineGraph(definition.steps)
        results: dict[str, dict[str, Any]] = {}

        # Inject initial inputs as a virtual "input" step
        results["_input"] = initial_inputs

        for group in graph.parallel_groups():
            tasks = []
            for step_name in group:
                step_config = graph.steps[step_name]
                step_impl = self.step_registry.get(step_config.step_type)
                if step_impl is None:
                    raise PipelineError(f"No implementation for step type: {step_config.step_type}")

                # Resolve inputs
                step_inputs = self._resolve_inputs(step_config.inputs, results)
                tasks.append(
                    self._run_step(step_name, step_impl, step_inputs, step_config.params)
                )

            group_results = await asyncio.gather(*tasks, return_exceptions=True)

            for step_name, result in zip(group, group_results):
                if isinstance(result, Exception):
                    raise PipelineError(
                        f"Step '{step_name}' failed: {result}"
                    ) from result
                results[step_name] = result

        return results

    async def _run_step(
        self,
        step_name: str,
        step_impl: ModulePipelineStep,
        inputs: dict,
        params: dict,
    ) -> dict[str, Any]:
        """Execute a single pipeline step."""
        logger.info("Executing step: %s (%s)", step_name, step_impl.step_type)
        start = time.monotonic()

        result = await step_impl.handler(inputs=inputs, params=params)

        elapsed = time.monotonic() - start
        logger.info("Step %s completed in %.2fs", step_name, elapsed)
        return result

    @staticmethod
    def _resolve_inputs(
        input_refs: dict[str, str],
        results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        resolved = {}
        for port, ref in input_refs.items():
            parts = ref.split(".", 1)
            src_step = parts[0]
            src_port = parts[1] if len(parts) > 1 else port

            if src_step not in results:
                raise PipelineError(f"Input step '{src_step}' has not completed yet")

            step_output = results[src_step]
            if src_port in step_output:
                resolved[port] = step_output[src_port]
            else:
                resolved[port] = step_output
        return resolved
