"""Evaluate partitions against the composite constraint."""

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.constraints.composite import CompositeConstraint
from bioforge.modules.assembly.core.models import ConstraintResult, Partition
from bioforge.modules.assembly.core.thermo import ThermoEngine


class Evaluator:
    """Evaluates partition quality against all assembly constraints."""

    def __init__(self, config: AssemblyConfig, thermo: ThermoEngine):
        self.config = config
        self.thermo = thermo
        self.composite = CompositeConstraint(config, thermo)

    def evaluate(self, partition: Partition, sequence: str) -> ConstraintResult:
        """Full evaluation of a partition against all constraints."""
        return self.composite.check(partition, sequence)

    def quick_score(self, partition: Partition, sequence: str) -> float:
        """Get just the composite score for optimization."""
        result = self.evaluate(partition, sequence)
        return result.score
