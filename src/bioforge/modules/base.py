from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ModuleInfo:
    name: str
    version: str
    description: str
    author: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ModuleCapability:
    """A single operation this module can perform."""

    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]]


@dataclass
class ModulePipelineStep:
    """A step type this module contributes to the pipeline engine."""

    step_type: str
    description: str
    input_ports: dict[str, str]
    output_ports: dict[str, str]
    handler: Callable[..., Awaitable[Any]]


class BioForgeModule(ABC):
    @abstractmethod
    def info(self) -> ModuleInfo:
        ...

    @abstractmethod
    def capabilities(self) -> list[ModuleCapability]:
        ...

    @abstractmethod
    def pipeline_steps(self) -> list[ModulePipelineStep]:
        ...

    def mcp_tools(self) -> list:
        """Return tool-decorated functions for MCP exposure."""
        return []

    def agent_definitions(self) -> dict[str, Any]:
        """Return AgentDefinition dicts for specialized sub-agents."""
        return {}

    async def on_load(self) -> None:
        """Called when the module is loaded by the platform."""

    async def on_unload(self) -> None:
        """Called when the module is unloaded."""
