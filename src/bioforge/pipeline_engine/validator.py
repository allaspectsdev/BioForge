"""Pipeline validation: check step types and port compatibility."""

from bioforge.core.exceptions import PipelineError
from bioforge.modules.base import ModulePipelineStep
from bioforge.pipeline_engine.dsl import PipelineDefinition


def validate_pipeline(
    definition: PipelineDefinition,
    available_steps: dict[str, ModulePipelineStep],
) -> list[str]:
    """Validate that all step types exist and ports are compatible.

    Returns a list of warnings (empty if everything is OK).
    Raises PipelineError on hard failures.
    """
    warnings = []

    for step in definition.steps:
        if step.step_type not in available_steps:
            raise PipelineError(
                f"Unknown step type '{step.step_type}' in step '{step.name}'. "
                f"Available: {list(available_steps.keys())}"
            )

        step_def = available_steps[step.step_type]

        # Check that all connected input ports exist
        for port, ref in step.inputs.items():
            if port not in step_def.input_ports:
                warnings.append(
                    f"Step '{step.name}': input port '{port}' not defined "
                    f"in step type '{step.step_type}'"
                )

    return warnings
