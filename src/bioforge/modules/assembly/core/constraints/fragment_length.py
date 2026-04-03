from bioforge.modules.assembly.core.constraints.base import BaseConstraint
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    ConstraintViolation,
    Partition,
)


class FragmentLengthConstraint(BaseConstraint):
    """C1: Each fragment must be within [min_fragment_bp, max_fragment_bp]."""

    @property
    def name(self) -> str:
        return "fragment_length"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        violations = []
        fragments = partition.get_fragments()
        min_bp = self.config.min_fragment_bp
        max_bp = self.config.max_fragment_bp

        for frag in fragments:
            if frag.length < min_bp or frag.length > max_bp:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=(
                            f"Fragment {frag.index}: length {frag.length} bp "
                            f"outside [{min_bp}, {max_bp}]"
                        ),
                        indices=[frag.index],
                    )
                )

        if violations:
            # Score: fraction of fragments that pass
            passing = len(fragments) - len(violations)
            score = passing / len(fragments) if fragments else 0.0
            return ConstraintResult(passed=False, violations=violations, score=score)
        return ConstraintResult.ok()
