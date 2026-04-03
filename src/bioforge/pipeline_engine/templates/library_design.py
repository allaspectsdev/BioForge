"""Pre-built pipeline: Combinatorial Parts → Co-Design → Per-Construct Plans → Batch Order."""

from bioforge.pipeline_engine.dsl import PipelineBuilder


def build_library_design_pipeline(
    assembly_method: str = "golden_gate",
) -> "PipelineDefinition":
    """Build a combinatorial library design pipeline.

    Steps:
    1. Take part categories with variants
    2. Co-design shared overhangs across all combinations
    3. Generate per-construct assembly plans
    """
    return (
        PipelineBuilder(
            "library_design",
            f"Combinatorial library design via {assembly_method}",
        )
        .add_step("assembly.combinatorial_design", "codesign",
                   params={"assembly_method": assembly_method})
        .connect("_input", "part_categories", "codesign", "part_categories")
        .build()
    )
