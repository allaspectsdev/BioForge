"""Pipeline definition DSL — fluent builder for constructing pipeline DAGs."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StepConfig:
    step_type: str
    name: str
    params: dict[str, Any] = field(default_factory=dict)
    inputs: dict[str, str] = field(default_factory=dict)  # port -> "step_name.port"
    container: str | None = None


@dataclass(frozen=True)
class PipelineDefinition:
    name: str
    description: str
    steps: list[StepConfig]


class PipelineBuilder:
    """Fluent API for constructing pipelines."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self._steps: list[StepConfig] = []

    def add_step(
        self,
        step_type: str,
        name: str,
        params: dict[str, Any] | None = None,
        container: str | None = None,
    ) -> "PipelineBuilder":
        self._steps.append(
            StepConfig(
                step_type=step_type,
                name=name,
                params=params or {},
                container=container,
            )
        )
        return self

    def connect(
        self,
        from_step: str,
        from_port: str,
        to_step: str,
        to_port: str,
    ) -> "PipelineBuilder":
        for s in self._steps:
            if s.name == to_step:
                s.inputs[to_port] = f"{from_step}.{from_port}"
                break
        return self

    def build(self) -> PipelineDefinition:
        """Validate and return immutable pipeline definition."""
        from bioforge.pipeline_engine.graph import PipelineGraph

        graph = PipelineGraph(self._steps)
        graph.validate()
        return PipelineDefinition(
            name=self.name,
            description=self.description,
            steps=list(self._steps),
        )
