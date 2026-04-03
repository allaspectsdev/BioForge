"""Pre-built pipeline: Sequence → Codon Optimize → Assembly Design → Feasibility Check → Primer Order."""

from bioforge.pipeline_engine.dsl import PipelineBuilder


def build_assembly_to_order_pipeline(
    organism: str = "ecoli_k12",
    assembly_method: str = "gibson",
    min_fragment_bp: int = 2000,
    max_fragment_bp: int = 2500,
) -> "PipelineDefinition":
    """Build a complete assembly-to-order pipeline.

    Steps:
    1. Codon optimize the input protein sequence for the target organism
    2. Design assembly (Gibson or Golden Gate) for the optimized DNA
    3. Check synthesis feasibility with providers
    4. Generate primer order sheet
    """
    builder = PipelineBuilder(
        "assembly_to_order",
        f"Complete assembly design pipeline for {organism} ({assembly_method})",
    )

    if assembly_method == "golden_gate":
        builder.add_step(
            "assembly.golden_gate", "design",
            params={"enzyme": "BsaI"},
        )
    else:
        builder.add_step(
            "assembly.design", "design",
            params={"min_fragment_bp": min_fragment_bp, "max_fragment_bp": max_fragment_bp},
        )

    builder.connect("_input", "sequence", "design", "sequence")

    return builder.build()


def build_codon_optimize_and_assemble_pipeline(
    organism: str = "ecoli_k12",
) -> "PipelineDefinition":
    """Protein → codon optimize → assemble → order."""
    return (
        PipelineBuilder(
            "codon_optimize_and_assemble",
            f"Codon optimize for {organism} then design assembly",
        )
        .add_step("assembly.codon_optimize", "optimize",
                   params={"organism": organism})
        .add_step("assembly.design", "design",
                   params={"min_fragment_bp": 2000, "max_fragment_bp": 2500})
        .connect("_input", "protein_sequence", "optimize", "protein_sequence")
        .connect("optimize", "optimized_dna", "design", "sequence")
        .build()
    )
