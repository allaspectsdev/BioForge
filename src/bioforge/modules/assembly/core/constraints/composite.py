from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.constraints.base import BaseConstraint
from bioforge.modules.assembly.core.constraints.fragment_length import FragmentLengthConstraint
from bioforge.modules.assembly.core.constraints.hairpin import HairpinConstraint
from bioforge.modules.assembly.core.constraints.orthogonality import OrthogonalityConstraint
from bioforge.modules.assembly.core.constraints.overhang_quality import OverhangQualityConstraint
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    Partition,
)
from bioforge.modules.assembly.core.thermo import ThermoEngine


class CompositeConstraint(BaseConstraint):
    """Runs all constraints in order with early termination and weighted scoring."""

    def __init__(self, config: AssemblyConfig, thermo: ThermoEngine):
        super().__init__(config)
        self.constraints: list[tuple[BaseConstraint, float]] = [
            (FragmentLengthConstraint(config), 1.0),
            (OverhangQualityConstraint(config, thermo), 1.0),
            (HairpinConstraint(config, thermo), 1.0),
            (OrthogonalityConstraint(config, thermo), 5.0),  # Hardest, weighted highest
        ]

    @property
    def name(self) -> str:
        return "composite"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        all_violations = []
        weighted_score = 0.0
        total_weight = sum(w for _, w in self.constraints)
        all_passed = True

        for constraint, weight in self.constraints:
            result = constraint.check(partition, sequence)
            all_violations.extend(result.violations)
            weighted_score += result.score * weight

            if not result.passed:
                all_passed = False
                # Early termination on hard failures for C1 (fragment length)
                # Skipped constraints contribute 0 to weighted_score but are
                # still counted in total_weight, correctly penalizing the score.
                if constraint.name == "fragment_length":
                    fail_count = sum(
                        1
                        for v in result.violations
                        if v.severity == ConstraintSeverity.FAIL
                    )
                    if fail_count > 0:
                        break

        composite_score = weighted_score / total_weight if total_weight > 0 else 0.0
        return ConstraintResult(
            passed=all_passed,
            violations=all_violations,
            score=composite_score,
        )
