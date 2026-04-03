"""Golden Gate-specific assembly constraints.

These constraints validate overhang sets for Type IIS restriction enzyme
assemblies, checking ligation fidelity, internal enzyme site conflicts,
and overhang set properties (no palindromes, no duplicates).
"""

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.golden_gate.enzymes import (
    ENZYMES,
    TypeIISEnzyme,
    bsai_fidelity,
    is_palindromic,
    overhang_fidelity_matrix,
)
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    ConstraintViolation,
    Partition,
    reverse_complement,
)
from bioforge.modules.assembly.core.constraints.base import BaseConstraint


class LigationFidelityConstraint(BaseConstraint):
    """Validates pairwise ligation fidelity for a Golden Gate overhang set.

    Checks that:
    - All cognate pairs (overhang with its intended complement) have
      fidelity >= min_cognate_fidelity (default 0.95).
    - All non-cognate pairs have cross-ligation fidelity <= max_cross_ligation
      (default 0.01).

    This is the primary quality constraint for Golden Gate assembly: poor
    fidelity leads to mis-assembled or incomplete constructs.
    """

    def __init__(
        self,
        config: AssemblyConfig,
        overhangs: list[str],
        max_cross_ligation: float = 0.01,
        min_cognate_fidelity: float = 0.95,
    ):
        super().__init__(config)
        self.overhangs = overhangs
        self.max_cross_ligation = max_cross_ligation
        self.min_cognate_fidelity = min_cognate_fidelity

    @property
    def name(self) -> str:
        return "ligation_fidelity"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        """Check all-pairs fidelity matrix for the overhang set.

        Note: For Golden Gate constraints, the partition/sequence arguments
        are accepted for interface compatibility but the overhangs are
        provided at construction time.
        """
        if len(self.overhangs) < 2:
            return ConstraintResult.ok()

        violations: list[ConstraintViolation] = []
        n = len(self.overhangs)
        matrix = overhang_fidelity_matrix(self.overhangs)

        # Check cognate fidelity (diagonal — each overhang with its own RC)
        for i in range(n):
            oh = self.overhangs[i]
            oh_rc = reverse_complement(oh)
            cognate_fid = bsai_fidelity(oh, oh_rc)
            if cognate_fid < self.min_cognate_fidelity:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=(
                            f"Overhang {i} ({oh}): cognate fidelity "
                            f"{cognate_fid:.3f} < {self.min_cognate_fidelity}"
                        ),
                        indices=[i],
                    )
                )

        # Check non-cognate cross-ligation (off-diagonal pairs)
        for i in range(n):
            for j in range(i + 1, n):
                cross_fid = matrix[i][j]
                if cross_fid > self.max_cross_ligation:
                    violations.append(
                        ConstraintViolation(
                            constraint_name=self.name,
                            severity=ConstraintSeverity.FAIL,
                            message=(
                                f"Overhangs {i} ({self.overhangs[i]}) and "
                                f"{j} ({self.overhangs[j]}): cross-ligation "
                                f"fidelity {cross_fid:.4f} > {self.max_cross_ligation}"
                            ),
                            indices=[i, j],
                        )
                    )

                # Also check i against RC(j) if they're not cognate pairs
                rc_j = reverse_complement(self.overhangs[j])
                if self.overhangs[i] != rc_j:
                    cross_rc = bsai_fidelity(self.overhangs[i], rc_j)
                    if cross_rc > self.max_cross_ligation:
                        violations.append(
                            ConstraintViolation(
                                constraint_name=self.name,
                                severity=ConstraintSeverity.WARNING,
                                message=(
                                    f"Overhang {i} ({self.overhangs[i]}) vs "
                                    f"RC({j}) ({rc_j}): cross-ligation "
                                    f"fidelity {cross_rc:.4f} > {self.max_cross_ligation}"
                                ),
                                indices=[i, j],
                            )
                        )

        if violations:
            fail_count = sum(
                1 for v in violations if v.severity == ConstraintSeverity.FAIL
            )
            total_checks = n + n * (n - 1) // 2
            score = max(0.0, 1.0 - fail_count / max(total_checks, 1))
            return ConstraintResult(
                passed=(fail_count == 0), violations=violations, score=score
            )
        return ConstraintResult.ok()


class EnzymeCompatibilityConstraint(BaseConstraint):
    """Checks that part sequences do not contain internal enzyme recognition sites.

    Internal recognition sites would cause the Type IIS enzyme to cut the
    part during the Golden Gate reaction, destroying the intended assembly.
    Parts with internal sites must be domesticated (silent mutations) before
    use.
    """

    def __init__(
        self,
        config: AssemblyConfig,
        enzyme_name: str = "BsaI",
    ):
        super().__init__(config)
        if enzyme_name not in ENZYMES:
            raise ValueError(f"Unknown enzyme: {enzyme_name}")
        self.enzyme = ENZYMES[enzyme_name]

    @property
    def name(self) -> str:
        return "enzyme_compatibility"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        """Check for internal enzyme recognition sites in each fragment.

        Scans each fragment for the enzyme recognition site on both strands.
        """
        violations: list[ConstraintViolation] = []
        site_fwd = self.enzyme.recognition_site.upper()
        site_rev = reverse_complement(site_fwd)

        fragments = partition.get_fragments()
        for frag in fragments:
            frag_seq = sequence[frag.start:frag.end].upper()

            # Check forward strand
            pos = 0
            while True:
                idx = frag_seq.find(site_fwd, pos)
                if idx == -1:
                    break
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=(
                            f"Fragment {frag.index}: internal {self.enzyme.name} "
                            f"site ({site_fwd}) at position {frag.start + idx} "
                            f"(forward strand)"
                        ),
                        indices=[frag.index],
                    )
                )
                pos = idx + 1

            # Check reverse strand
            pos = 0
            while True:
                idx = frag_seq.find(site_rev, pos)
                if idx == -1:
                    break
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=(
                            f"Fragment {frag.index}: internal {self.enzyme.name} "
                            f"site ({site_rev}) at position {frag.start + idx} "
                            f"(reverse strand)"
                        ),
                        indices=[frag.index],
                    )
                )
                pos = idx + 1

        if violations:
            return ConstraintResult(
                passed=False,
                violations=violations,
                score=0.0,
            )
        return ConstraintResult.ok()

    def check_parts(self, parts: list[str]) -> ConstraintResult:
        """Convenience method to check a list of part sequences directly.

        This avoids the need to construct a Partition object for simple
        part-level checks.
        """
        violations: list[ConstraintViolation] = []
        site_fwd = self.enzyme.recognition_site.upper()
        site_rev = reverse_complement(site_fwd)

        for i, part_seq in enumerate(parts):
            seq = part_seq.upper()
            for site_label, site in [("fwd", site_fwd), ("rev", site_rev)]:
                pos = 0
                while True:
                    idx = seq.find(site, pos)
                    if idx == -1:
                        break
                    violations.append(
                        ConstraintViolation(
                            constraint_name=self.name,
                            severity=ConstraintSeverity.FAIL,
                            message=(
                                f"Part {i}: internal {self.enzyme.name} site "
                                f"({site}) at position {idx} ({site_label} strand)"
                            ),
                            indices=[i],
                        )
                    )
                    pos = idx + 1

        if violations:
            return ConstraintResult(passed=False, violations=violations, score=0.0)
        return ConstraintResult.ok()


class OverhangSetConstraint(BaseConstraint):
    """Validates structural properties of the overhang set.

    Checks:
    - No palindromic overhangs (self-ligation risk).
    - No duplicate overhangs (would create ambiguous ligation).
    - No overhang is the reverse complement of another (cross-pairing).
    """

    def __init__(self, config: AssemblyConfig, overhangs: list[str]):
        super().__init__(config)
        self.overhangs = [oh.upper() for oh in overhangs]

    @property
    def name(self) -> str:
        return "overhang_set"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        """Validate the overhang set for palindromes and duplicates."""
        violations: list[ConstraintViolation] = []

        # Check for palindromic overhangs
        for i, oh in enumerate(self.overhangs):
            if is_palindromic(oh):
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=(
                            f"Overhang {i} ({oh}) is palindromic — "
                            f"will self-ligate"
                        ),
                        indices=[i],
                    )
                )

        # Check for duplicate overhangs
        seen: dict[str, int] = {}
        for i, oh in enumerate(self.overhangs):
            if oh in seen:
                violations.append(
                    ConstraintViolation(
                        constraint_name=self.name,
                        severity=ConstraintSeverity.FAIL,
                        message=(
                            f"Overhang {i} ({oh}) is a duplicate of "
                            f"overhang {seen[oh]}"
                        ),
                        indices=[seen[oh], i],
                    )
                )
            else:
                seen[oh] = i

        # Check for reverse complement conflicts
        for i in range(len(self.overhangs)):
            rc_i = reverse_complement(self.overhangs[i])
            for j in range(i + 1, len(self.overhangs)):
                if self.overhangs[j] == rc_i:
                    violations.append(
                        ConstraintViolation(
                            constraint_name=self.name,
                            severity=ConstraintSeverity.FAIL,
                            message=(
                                f"Overhang {j} ({self.overhangs[j]}) is the "
                                f"reverse complement of overhang {i} "
                                f"({self.overhangs[i]}) — will cross-pair"
                            ),
                            indices=[i, j],
                        )
                    )

        if violations:
            fail_count = sum(
                1 for v in violations if v.severity == ConstraintSeverity.FAIL
            )
            score = max(0.0, 1.0 - fail_count / max(len(self.overhangs), 1))
            return ConstraintResult(
                passed=False, violations=violations, score=score
            )
        return ConstraintResult.ok()
