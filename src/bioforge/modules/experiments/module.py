"""Experiment module: protocols, experiment records, and primer ordering."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, UTC
from typing import Any
from uuid import uuid4

from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
    ValidationResult,
)
from bioforge.modules.experiments.ordering import PrimerOrderGenerator
from bioforge.modules.experiments.protocols import ProtocolLibrary

logger = logging.getLogger(__name__)


class ExperimentModule(BioForgeModule):
    """Module for experiment management, protocol templates, primer ordering, and wet-lab feedback.

    Capabilities:
    - create_experiment: Create an experiment record with protocol steps
    - list_protocols: Return available protocol templates
    - generate_primer_order: Generate IDT-format primer order CSV from assembly results
    - record_outcome: Record whether a design actually worked in the wet lab
    - get_outcomes: Retrieve recorded outcomes (training data for future designs)
    """

    def __init__(self) -> None:
        self._protocol_library = ProtocolLibrary()
        self._primer_generator = PrimerOrderGenerator()
        # In-memory experiment store (would be database-backed in production)
        self._experiments: dict[str, dict] = {}
        # Wet-lab feedback store: every assembly that gets validated becomes training data
        self._outcomes: list[dict] = []

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
            ModuleCapability(
                name="record_outcome",
                description=(
                    "Record wet-lab outcome for a design. Did the assembly work? "
                    "This closes the feedback loop: every validated (or failed) design "
                    "becomes proprietary training data for improving future predictions."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "experiment_id": {
                            "type": "string",
                            "description": "ID of the experiment (from create_experiment)",
                        },
                        "design_type": {
                            "type": "string",
                            "description": (
                                "What was designed: gibson_assembly, golden_gate, "
                                "codon_optimization, variant_prediction, structure_prediction"
                            ),
                        },
                        "design_params": {
                            "type": "object",
                            "description": "The parameters/input that produced the design",
                        },
                        "design_result": {
                            "type": "object",
                            "description": "The computational result that was tested",
                        },
                        "success": {
                            "type": "boolean",
                            "description": "Did the design work in the wet lab?",
                        },
                        "colony_count": {
                            "type": "integer",
                            "description": "Number of positive colonies (for assembly)",
                        },
                        "sequence_verified": {
                            "type": "boolean",
                            "description": "Was the construct Sanger/NGS verified?",
                        },
                        "failure_mode": {
                            "type": "string",
                            "description": "If failed: no_colonies, wrong_size, mutations, etc.",
                        },
                        "notes": {
                            "type": "string",
                            "description": "Free-text lab notes or observations",
                        },
                    },
                    "required": ["design_type", "success"],
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "outcome_id": {"type": "string"},
                        "recorded_at": {"type": "string"},
                    },
                },
                handler=self._record_outcome,
            ),
            ModuleCapability(
                name="get_outcomes",
                description=(
                    "Retrieve recorded wet-lab outcomes. Use this to review what worked "
                    "and what didn't — the basis for learning from real experiments."
                ),
                input_schema={
                    "type": "object",
                    "properties": {
                        "design_type": {
                            "type": "string",
                            "description": "Filter by design type (optional)",
                        },
                        "success_only": {
                            "type": "boolean",
                            "description": "Only return successful outcomes",
                        },
                    },
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "outcomes": {"type": "array"},
                        "count": {"type": "integer"},
                        "success_rate": {"type": "number"},
                    },
                },
                handler=self._get_outcomes,
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
        return [
            self._create_experiment,
            self._list_protocols,
            self._generate_primer_order,
            self._record_outcome,
            self._get_outcomes,
        ]

    async def validate(self, capability_name: str, result: dict) -> ValidationResult:
        """Validate experiment outputs — check protocol steps and primer orders."""
        checks = []
        warnings = []
        errors = []

        if capability_name == "create_experiment":
            protocol = result.get("protocol", {})
            steps = protocol.get("steps", [])
            checks.append(f"protocol_steps={len(steps)}")
            if not steps:
                warnings.append("Experiment created with empty protocol (no steps)")
            if not result.get("experiment_id"):
                errors.append("No experiment_id in result")
            checks.append("experiment_id_present")

        elif capability_name == "generate_primer_order":
            primers = result.get("primers", [])
            csv = result.get("csv", "")
            checks.append(f"primer_count={len(primers)}")
            if not primers:
                errors.append("No primers generated")
            if not csv:
                errors.append("Empty CSV output")
            checks.append("csv_non_empty")

        return ValidationResult(
            valid=len(errors) == 0,
            checks_performed=checks,
            warnings=warnings,
            errors=errors,
        )

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
            "created_at": datetime.now(UTC).isoformat(),
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

    async def _record_outcome(self, request: dict) -> dict:
        """Record a wet-lab outcome — the feedback loop that builds training data.

        Every assembly/prediction that gets tested in the lab and reported
        back here becomes proprietary data for improving future designs.
        """
        outcome_id = str(uuid4())
        outcome = {
            "outcome_id": outcome_id,
            "experiment_id": request.get("experiment_id"),
            "design_type": request.get("design_type", "unknown"),
            "design_params": request.get("design_params", {}),
            "design_result": request.get("design_result", {}),
            "success": request.get("success", False),
            "colony_count": request.get("colony_count"),
            "sequence_verified": request.get("sequence_verified", False),
            "failure_mode": request.get("failure_mode"),
            "notes": request.get("notes", ""),
            "recorded_at": datetime.now(UTC).isoformat(),
        }

        self._outcomes.append(outcome)

        # Also update the experiment record if we have one
        experiment_id = request.get("experiment_id")
        if experiment_id and experiment_id in self._experiments:
            exp = self._experiments[experiment_id]
            exp.setdefault("outcomes", []).append(outcome_id)
            exp["status"] = "completed" if request.get("success") else "failed"

        logger.info(
            "Recorded outcome %s for %s: success=%s",
            outcome_id,
            request.get("design_type"),
            request.get("success"),
        )

        return {"outcome_id": outcome_id, "recorded_at": outcome["recorded_at"]}

    async def _get_outcomes(self, request: dict) -> dict:
        """Retrieve recorded outcomes, optionally filtered."""
        design_type = request.get("design_type")
        success_only = request.get("success_only", False)

        filtered = self._outcomes
        if design_type:
            filtered = [o for o in filtered if o.get("design_type") == design_type]
        if success_only:
            filtered = [o for o in filtered if o.get("success")]

        total = len(filtered)
        successes = sum(1 for o in filtered if o.get("success"))
        success_rate = round(successes / max(total, 1), 3)

        return {
            "outcomes": filtered,
            "count": total,
            "success_rate": success_rate,
        }

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
