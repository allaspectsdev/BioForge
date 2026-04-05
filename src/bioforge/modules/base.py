from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class DataProvenance:
    """Track where data or results came from and how much to trust them.

    Attach to any module output to make the "big approximation" visible:
    what model/library produced the result, what reference data was used,
    and how confident we are.
    """

    source: str  # e.g. "primer3-py 0.6.1", "Evo2-7B", "Boltz-2"
    method: str  # e.g. "delta-log-likelihood", "NW global alignment"
    confidence: float = 1.0  # 0.0–1.0, where 1.0 = fully validated
    confidence_notes: str = ""  # human-readable explanation of confidence level
    reference: str = ""  # paper DOI or URL
    reference_data: str = ""  # e.g. "NCBI nr 2026-03", "E. coli K-12 MG1655"
    warnings: list[str] = field(default_factory=list)  # low-confidence regime flags


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


@dataclass
class ValidationResult:
    """Result of a module's self-validation of its output."""

    valid: bool
    checks_performed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


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

    async def validate(self, capability_name: str, result: dict[str, Any]) -> ValidationResult:
        """Validate the output of a capability — don't just trust the library.

        Each module should verify its own outputs make biological/logical sense.
        Extends the pattern from assembly's pydna simulation to all modules.

        Parameters
        ----------
        capability_name : str
            Which capability produced the result (e.g. "design_assembly").
        result : dict
            The raw output dict from the capability handler.

        Returns
        -------
        ValidationResult
            Whether the output is valid, with details on what was checked.
        """
        return ValidationResult(valid=True, checks_performed=["none (base default)"])

    async def on_load(self) -> None:
        """Called when the module is loaded by the platform."""

    async def on_unload(self) -> None:
        """Called when the module is unloaded."""
