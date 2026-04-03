"""Pre-built pipeline: VCF → Annotate → Evo 2 Effect Prediction → Summary."""

from bioforge.pipeline_engine.dsl import PipelineBuilder


def build_variant_analysis_pipeline() -> "PipelineDefinition":
    """Build a variant analysis pipeline.

    Steps:
    1. Load and parse VCF data
    2. Annotate variants with gene/feature context
    3. Predict variant effects using Evo 2
    4. Generate summary report
    """
    return (
        PipelineBuilder(
            "variant_analysis",
            "Annotate and predict effects of genomic variants",
        )
        .add_step("variants.annotate", "annotate")
        .add_step("evo2.variant_scan", "predict_effects")
        .connect("_input", "variants", "annotate", "variants")
        .connect("_input", "reference_sequence", "annotate", "reference")
        .connect("annotate", "annotated_variants", "predict_effects", "variants")
        .connect("_input", "reference_sequence", "predict_effects", "sequence")
        .build()
    )
