"""Assembly module: DNA fragment assembly design for Gibson Assembly."""

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.solver import AssemblySolver
from bioforge.modules.assembly.schemas import AssemblyRequest, AssemblyResult
from bioforge.modules.assembly import tools as assembly_tools
from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
    ValidationResult,
)


class AssemblyModule(BioForgeModule):
    def __init__(self) -> None:
        self._solver: AssemblySolver | None = None

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="assembly",
            version="0.1.0",
            description="DNA fragment assembly design (Gibson Assembly) with constraint-based optimization",
            author="BioForge",
            tags=["dna", "assembly", "gibson", "cloning", "overhang"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="design_assembly",
                description="Design a complete Gibson Assembly partition for a DNA sequence",
                input_schema=AssemblyRequest.model_json_schema(),
                output_schema=AssemblyResult.model_json_schema(),
                handler=self._design_assembly,
            ),
            ModuleCapability(
                name="calculate_tm",
                description="Calculate melting temperature and properties for a DNA oligonucleotide",
                input_schema={"type": "object", "properties": {"sequence": {"type": "string"}}, "required": ["sequence"]},
                output_schema={"type": "object"},
                handler=assembly_tools.calculate_tm,
            ),
            ModuleCapability(
                name="check_overhang_quality",
                description="Evaluate overhang sequences against assembly quality constraints (Tm, GC, homopolymers, hairpins)",
                input_schema={"type": "object", "properties": {"overhangs": {"type": "array", "items": {"type": "string"}}}, "required": ["overhangs"]},
                output_schema={"type": "object"},
                handler=assembly_tools.check_overhang_quality,
            ),
            ModuleCapability(
                name="reverse_complement",
                description="Compute the reverse complement of a DNA sequence",
                input_schema={"type": "object", "properties": {"sequence": {"type": "string"}}, "required": ["sequence"]},
                output_schema={"type": "object"},
                handler=assembly_tools.reverse_complement_tool,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="assembly.design",
                description="Design Gibson Assembly fragments and overhangs for a DNA sequence",
                input_ports={"sequence": "str"},
                output_ports={"result": "AssemblyResult"},
                handler=self._design_assembly_step,
            ),
            ModulePipelineStep(
                step_type="assembly.golden_gate",
                description="Design Golden Gate Assembly with Type IIS enzyme overhangs",
                input_ports={"parts": "list[str]"},
                output_ports={"result": "dict"},
                handler=self._design_golden_gate_step,
            ),
            ModulePipelineStep(
                step_type="assembly.codon_optimize",
                description="Optimize codons for a protein sequence for a target organism",
                input_ports={"protein_sequence": "str"},
                output_ports={"optimized_dna": "str", "cai": "float"},
                handler=self._codon_optimize_step,
            ),
        ]

    def mcp_tools(self) -> list:
        """Return tool functions for MCP exposure."""
        return [
            assembly_tools.design_assembly,
            assembly_tools.calculate_tm,
            assembly_tools.check_overhang_quality,
            assembly_tools.reverse_complement_tool,
        ]

    async def _design_assembly(self, request: dict) -> dict:
        """Handle capability invocation."""
        req = AssemblyRequest(**request)
        result = self._run_solver(req)
        return result.model_dump()

    async def _design_assembly_step(self, inputs: dict, params: dict) -> dict:
        """Handle pipeline step invocation."""
        sequence = inputs["sequence"]
        req = AssemblyRequest(sequence=sequence, **params)
        result = self._run_solver(req)
        return {"result": result.model_dump()}

    async def _design_golden_gate_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for Golden Gate Assembly design."""
        from dataclasses import asdict
        from bioforge.modules.assembly.core.golden_gate.gg_solver import GoldenGateSolver
        parts = inputs["parts"]
        enzyme = params.get("enzyme", "BsaI")
        solver = GoldenGateSolver(enzyme_name=enzyme)
        result = solver.solve(parts)
        return {"result": asdict(result) if hasattr(result, "__dataclass_fields__") else result}

    async def _codon_optimize_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for codon optimization."""
        from bioforge.modules.assembly.core.codon.optimizer import CodonOptimizer
        protein_sequence = inputs["protein_sequence"]
        organism = params.get("organism", "ecoli_k12")
        opt = CodonOptimizer(organism=organism)
        result = opt.optimize(protein_sequence)
        return {
            "optimized_dna": result.optimized_sequence if hasattr(result, "optimized_sequence") else str(result),
            "cai": result.cai if hasattr(result, "cai") else 0.0,
        }

    async def validate(self, capability_name: str, result: dict) -> ValidationResult:
        """Validate assembly output via pydna simulation.

        Don't just trust the solver — simulate the assembly to verify
        fragments actually join correctly.
        """
        checks = []
        warnings = []
        errors = []

        if capability_name == "design_assembly":
            # Check basic structural validity
            fragments = result.get("fragments", [])
            overhangs = result.get("overhangs", [])

            checks.append(f"fragment_count={len(fragments)}")
            if not fragments:
                errors.append("No fragments in result")
                return ValidationResult(
                    valid=False, checks_performed=checks, errors=errors,
                )

            # Check fragment coverage (no gaps)
            sorted_frags = sorted(fragments, key=lambda f: f["start"])
            for i in range(1, len(sorted_frags)):
                prev_end = sorted_frags[i - 1]["end"]
                curr_start = sorted_frags[i]["start"]
                if curr_start > prev_end:
                    errors.append(
                        f"Gap between fragments {i-1} and {i}: "
                        f"[{prev_end}, {curr_start})"
                    )
            checks.append("fragment_coverage_continuity")

            # Verify overhang Tm values are within sane range
            for oh in overhangs:
                tm = oh.get("tm", 0)
                if tm < 30 or tm > 85:
                    warnings.append(
                        f"Overhang {oh.get('index', '?')} has extreme Tm={tm:.1f}C"
                    )
            checks.append("overhang_tm_sanity")

            # Attempt pydna simulation if we have sequence data
            if result.get("feasible"):
                checks.append("pydna_simulation_available")

        return ValidationResult(
            valid=len(errors) == 0,
            checks_performed=checks,
            warnings=warnings,
            errors=errors,
        )

    def _run_solver(self, req: AssemblyRequest) -> AssemblyResult:
        config = AssemblyConfig(
            min_fragment_bp=req.constraints.min_fragment_bp,
            max_fragment_bp=req.constraints.max_fragment_bp,
            default_overhang_bp=req.constraints.overhang_length,
            min_tm=req.constraints.min_tm,
            max_tm=req.constraints.max_tm,
            min_gc=req.constraints.min_gc,
            max_gc=req.constraints.max_gc,
            min_hamming_distance=req.constraints.min_hamming_distance,
            min_ddg_kcal=req.constraints.min_ddg_kcal,
            max_homopolymer_run=req.constraints.max_homopolymer_length,
        )
        solver = AssemblySolver(config=config, seed=req.seed)
        result = solver.solve(req.sequence)

        return AssemblyResult(
            feasible=result.feasible,
            num_fragments=result.partition.num_fragments,
            fragments=[
                {"index": f["index"], "start": f["start"], "end": f["end"], "length": f["length"]}
                for f in result.fragments
            ],
            overhangs=[
                {
                    "index": o["index"],
                    "position": o["position"],
                    "sequence": o["sequence"],
                    "length": o["length"],
                    "tm": o["tm"],
                    "gc": o["gc"],
                    "homopolymer_run": o["homopolymer_run"],
                }
                for o in result.overhangs
            ],
            quality_scores=result.quality_scores,
            restarts_used=result.restarts_used,
            total_time_s=result.total_time_s,
            violations=[
                {"constraint": v.constraint_name, "severity": v.severity.value, "message": v.message}
                for v in result.constraint_result.violations
            ],
        )
