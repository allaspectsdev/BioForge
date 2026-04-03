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
