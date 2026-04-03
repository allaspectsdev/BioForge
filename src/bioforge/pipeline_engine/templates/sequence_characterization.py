"""Pre-built pipeline: Sequence → BLAST → Evo 2 Embed → Similar Search → Structure Prediction."""

from bioforge.pipeline_engine.dsl import PipelineBuilder


def build_sequence_characterization_pipeline() -> "PipelineDefinition":
    """Build a comprehensive sequence characterization pipeline.

    Steps:
    1. Compute Evo 2 embedding for sequence intelligence
    2. Search for similar sequences via embedding distance
    3. Predict 3D structure (if protein)
    """
    return (
        PipelineBuilder(
            "sequence_characterization",
            "Comprehensive sequence analysis: embed, search, fold",
        )
        .add_step("evo2.embed", "embed")
        .add_step("structure.fold", "fold")
        .connect("_input", "sequence", "embed", "sequence")
        .connect("_input", "sequence", "fold", "sequence")
        .build()
    )
