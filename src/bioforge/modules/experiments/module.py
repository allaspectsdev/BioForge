"""Experiment module: protocols, experiment records, and primer ordering."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
)
from bioforge.modules.experiments.ordering import PrimerOrderGenerator
from bioforge.modules.experiments.protocols import ProtocolLibrary

logger = logging.getLogger(__name__)


class ExperimentModule(BioForgeModule):
    """Module for experiment management, protocol templates, and primer ordering.

    Capabilities:
    - create_experiment: Create an experiment record with protocol steps
    - list_protocols: Return available protocol templates
    - generate_primer_order: Generate IDT-format primer order CSV from assembly results
    """

    def __init__(self) -> None:
        self._protocol_library = ProtocolLibrary()
        self._primer_generator = PrimerOrderGenerator()
        # In-memory experiment store (would be database-backed in production)
        self._experiments: dict[str, dict] = {}

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="experiments",
            version="0.1.0",
            description="Experiment tracking: protocol templates, experiment records, primer ordering",
            author="BioForge",
            tags=["experiments", "protocols", "ordering", "plates", "lab"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="create_experiment",
                description=(
                    "Create a new experiment record from a protocol template. "
                    "Returns the experiment with all protocol steps pre-populated. "
                    "Optionally override specific parameters."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for this experiment",
                        },
                        "protocol_id": {
                            "type": "string",
                            "description": (
                                "Protocol template ID (e.g., gibson_assembly_neb_hifi, "
                                "golden_gate_bsai, colony_pcr)"
                            ),
                        },
                        "description": {
                            "type": "string",
                            "description": "Optional description or notes",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Optional parameter overrides for the protocol",
                        },
                    },
                    "required": ["name", "protocol_id"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "experiment_id": {"type": "string"},
                        "name": {"type": "string"},
                        "protocol": {"type": "object"},
                        "created_at": {"type": "string"},
                    },
                },
                handler=self._create_experiment,
            ),
            ModuleCapability(
                name="list_protocols",
                description=(
                    "List all available experiment protocol templates. "
                    "Returns protocol IDs, names, descriptions, and step counts."
                ),
                input_schema={
                    "type": "object",
                    "properties": {},
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "protocols": {"type": "array"},
                    },
                },
                handler=self._list_protocols,
            ),
            ModuleCapability(
                name="generate_primer_order",
                description=(
                    "Generate an IDT-format 96-well plate CSV for primer ordering. "
                    "Takes an assembly result with fragments and overhangs, and "
                    "produces a primer plate layout with calculated Tm values."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "assembly_result": {
                            "type": "object",
                            "description": (
                                "Assembly result dict with 'fragments' and 'overhangs' lists. "
                                "Each fragment has 'index', 'start', 'end'. "
                                "Each overhang has 'index', 'sequence'."
                            ),
                        },
                        "plate_name": {
                            "type": "string",
                            "description": "Name for the primer plate",
                        },
                        "primer_prefix": {
                            "type": "string",
                            "description": "Prefix for primer names (default: BF)",
                        },
                    },
                    "required": ["assembly_result"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "csv": {"type": "string"},
                        "num_primers": {"type": "integer"},
                        "primers": {"type": "array"},
                    },
                },
                handler=self._generate_primer_order,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="experiments.primer_order",
                description="Generate primer order CSV from assembly results",
                input_ports={"assembly_result": "dict"},
                output_ports={"order": "dict"},
                handler=self._primer_order_step,
            ),
        ]

    def mcp_tools(self) -> list:
        return [self._create_experiment, self._list_protocols, self._generate_primer_order]

    # ------------------------------------------------------------------
    # Capability handlers
    # ------------------------------------------------------------------

    async def _create_experiment(self, request: dict) -> dict:
        """Create a new experiment record from a protocol template."""
        name = request.get("name", "Untitled Experiment")
        protocol_id = request.get("protocol_id", "")
        description = request.get("description", "")
        parameters = request.get("parameters", {})

        # Look up protocol
        protocol = self._protocol_library.get_protocol_dict(protocol_id)
        if protocol is None:
            return {
                "error": f"Unknown protocol: {protocol_id}",
                "available_protocols": self._protocol_library.available_ids(),
            }

        # Create experiment record
        experiment_id = str(uuid4())
        experiment = {
            "experiment_id": experiment_id,
            "name": name,
            "description": description,
            "protocol_id": protocol_id,
            "protocol": protocol,
            "parameters": parameters,
            "status": "planned",
            "created_at": datetime.utcnow().isoformat(),
            "steps_completed": [],
        }

        self._experiments[experiment_id] = experiment
        logger.info("Created experiment %s: %s (protocol: %s)", experiment_id, name, protocol_id)

        return experiment

    async def _list_protocols(self, request: dict) -> dict:
        """List all available protocol templates."""
        protocols = self._protocol_library.list_protocols()
        return {"protocols": protocols, "count": len(protocols)}

    async def _generate_primer_order(self, request: dict) -> dict:
        """Generate IDT-format primer order from assembly results."""
        assembly_result = request.get("assembly_result", {})
        plate_name = request.get("plate_name", "BioForge_Primers")
        primer_prefix = request.get("primer_prefix", "BF")

        order = self._primer_generator.generate(
            assembly_result=assembly_result,
            plate_name=plate_name,
            primer_prefix=primer_prefix,
        )

        return order.to_dict()

    # ------------------------------------------------------------------
    # Pipeline step handlers
    # ------------------------------------------------------------------

    async def _primer_order_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for primer order generation."""
        request = {
            "assembly_result": inputs["assembly_result"],
            **params,
        }
        result = await self._generate_primer_order(request)
        return {"order": result}
