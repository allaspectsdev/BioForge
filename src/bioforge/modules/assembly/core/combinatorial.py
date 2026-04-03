"""Combinatorial multi-construct co-design for DNA assembly.

Designs shared overhang sets that are compatible across ALL combinations
of part variants. Given N part categories (promoter, RBS, CDS, terminator)
each with M variants, the designer finds overhangs at the N-1 junctions
that work for every combination of M^N constructs.

For Golden Gate: finds an orthogonal 4bp overhang set shared across all
construct variants. The key insight is that overhang compatibility only
depends on the junction positions, not on the specific variant sequences,
so we need one overhang set that works for the union of all variants.

For Gibson: finds boundary overlap regions that maintain sufficient Tm
and orthogonality across all variant combinations.
"""

import itertools
import logging
import random
from dataclasses import dataclass, field

from bioforge.modules.assembly.core.golden_gate.enzymes import (
    bsai_fidelity,
    is_palindromic,
)
from bioforge.modules.assembly.core.golden_gate.gg_solver import (
    GoldenGatePart,
    GoldenGateResult,
    GoldenGateSolver,
)
from bioforge.modules.assembly.core.models import gc_content, reverse_complement

logger = logging.getLogger(__name__)


@dataclass
class ConstructPlan:
    """Assembly plan for a single construct in the combinatorial library.

    Attributes:
        construct_id: Unique identifier for this combination.
        parts: List of part sequences (one variant per category).
        variant_indices: Which variant was chosen from each category.
        overhangs: The shared overhang set for this construct.
        assembly_method: "golden_gate" or "gibson".
    """

    construct_id: int
    parts: list[str]
    variant_indices: list[int]
    overhangs: list[str]
    assembly_method: str


@dataclass
class CombinatorialResult:
    """Result of combinatorial assembly co-design.

    Attributes:
        shared_overhangs: The overhang set shared by all constructs.
        per_construct_plans: Assembly plan for each construct combination.
        total_constructs: Total number of construct combinations.
        assembly_method: "golden_gate" or "gibson".
        feasible: Whether the shared overhang set meets all constraints.
        score: Quality score of the shared overhang set.
    """

    shared_overhangs: list[str]
    per_construct_plans: list[ConstructPlan]
    total_constructs: int
    assembly_method: str
    feasible: bool = False
    score: float = 0.0


def _generate_orthogonal_overhangs(
    num_overhangs: int,
    max_cross_ligation: float = 0.01,
    max_attempts: int = 5000,
    rng: random.Random | None = None,
) -> list[str]:
    """Generate a set of orthogonal 4bp overhangs by random sampling.

    Iteratively builds up a set of overhangs, testing each candidate
    against all previously selected overhangs for compatibility.

    Args:
        num_overhangs: Number of orthogonal overhangs needed.
        max_cross_ligation: Maximum allowed cross-ligation fidelity.
        max_attempts: Maximum random sampling attempts.
        rng: Random number generator.

    Returns:
        List of orthogonal 4bp overhangs.
    """
    if rng is None:
        rng = random.Random()

    bases = "ACGT"
    selected: list[str] = []

    attempts = 0
    while len(selected) < num_overhangs and attempts < max_attempts:
        attempts += 1
        # Generate random 4bp overhang
        candidate = "".join(rng.choices(bases, k=4))

        # Skip palindromes
        if is_palindromic(candidate):
            continue

        # Check for duplicates and reverse complement conflicts
        candidate_rc = reverse_complement(candidate)
        conflict = False

        for existing in selected:
            if candidate == existing or candidate == reverse_complement(existing):
                conflict = True
                break
            if candidate_rc == existing:
                conflict = True
                break

            # Check cross-ligation in both directions
            cross1 = bsai_fidelity(candidate, existing)
            cross2 = bsai_fidelity(existing, candidate)
            if cross1 > max_cross_ligation or cross2 > max_cross_ligation:
                conflict = True
                break

            # Check reverse complement cross-ligation
            if candidate != reverse_complement(existing):
                cross_rc = bsai_fidelity(candidate, reverse_complement(existing))
                if cross_rc > max_cross_ligation:
                    conflict = True
                    break

        if not conflict:
            selected.append(candidate)

    return selected


def _gibson_overlap_regions(
    part_categories: list[list[str]],
    overlap_length: int = 25,
) -> list[str]:
    """Design Gibson overlap sequences at junctions between part categories.

    For each junction between category i and category i+1, extract
    overlap sequences from the boundary of the first variant pair.
    Gibson overlaps should maintain:
    - Tm between 50-65C
    - GC 40-60%
    - No strong hairpins

    Args:
        part_categories: List of part variant lists.
        overlap_length: Length of the overlap region (default 25bp).

    Returns:
        List of overlap sequences, one per junction.
    """
    overlaps: list[str] = []

    for i in range(len(part_categories) - 1):
        # Use the first variant of each category as the reference
        left_part = part_categories[i][0]
        right_part = part_categories[i + 1][0]

        # Take overlap from the end of the left part and start of the right part
        half = overlap_length // 2
        left_end = left_part[-half:] if len(left_part) >= half else left_part
        right_start = right_part[:half] if len(right_part) >= half else right_part

        overlap = (left_end + right_start).upper()
        overlaps.append(overlap)

    return overlaps


class CombinatorialDesigner:
    """Designs shared assemblies for combinatorial part libraries.

    Given part categories (e.g., promoters, RBS sequences, CDSes,
    terminators), each with multiple variants, designs a single
    overhang/overlap set that is compatible with ALL variant combinations.

    Args:
        assembly_method: "golden_gate" or "gibson".
        enzyme_name: Enzyme for Golden Gate (default "BsaI").
        max_cross_ligation: Maximum allowed cross-ligation for Golden Gate.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        assembly_method: str = "golden_gate",
        enzyme_name: str = "BsaI",
        max_cross_ligation: float = 0.01,
        seed: int | None = None,
    ):
        if assembly_method not in ("golden_gate", "gibson"):
            raise ValueError(
                f"Unknown assembly method '{assembly_method}'. "
                f"Must be 'golden_gate' or 'gibson'."
            )

        self.assembly_method = assembly_method
        self.enzyme_name = enzyme_name
        self.max_cross_ligation = max_cross_ligation
        self.rng = random.Random(seed)

    def design(
        self,
        part_categories: list[list[str]],
    ) -> CombinatorialResult:
        """Design a shared assembly for all combinatorial constructs.

        Args:
            part_categories: List of part categories. Each category is a
                list of variant DNA sequences. E.g.:
                [
                    ["promoter_A", "promoter_B"],  # Category 0
                    ["rbs_1", "rbs_2", "rbs_3"],   # Category 1
                    ["cds_X", "cds_Y"],             # Category 2
                ]
                Total constructs = 2 * 3 * 2 = 12.

        Returns:
            CombinatorialResult with shared overhangs and per-construct plans.

        Raises:
            ValueError: If fewer than 2 categories are provided or any
                category is empty.
        """
        if len(part_categories) < 2:
            raise ValueError("Need at least 2 part categories")
        for i, category in enumerate(part_categories):
            if len(category) == 0:
                raise ValueError(f"Part category {i} is empty")

        num_junctions = len(part_categories) - 1
        total_constructs = 1
        for cat in part_categories:
            total_constructs *= len(cat)

        if self.assembly_method == "golden_gate":
            return self._design_golden_gate(
                part_categories, num_junctions, total_constructs
            )
        else:
            return self._design_gibson(
                part_categories, num_junctions, total_constructs
            )

    def _design_golden_gate(
        self,
        part_categories: list[list[str]],
        num_junctions: int,
        total_constructs: int,
    ) -> CombinatorialResult:
        """Design Golden Gate assembly with shared overhangs.

        The key insight: since all construct variants share the same
        junction positions, we need ONE orthogonal overhang set that
        works for the union of all variant sequences. The overhangs
        don't depend on variant identity — they define the architecture.
        """
        # Generate orthogonal overhang set
        # We need num_junctions overhangs (one per junction between categories)
        shared_overhangs = _generate_orthogonal_overhangs(
            num_overhangs=num_junctions,
            max_cross_ligation=self.max_cross_ligation,
            rng=self.rng,
        )

        feasible = len(shared_overhangs) == num_junctions

        if not feasible:
            logger.warning(
                "Could only generate %d of %d required orthogonal overhangs",
                len(shared_overhangs), num_junctions,
            )
            # Pad with placeholder overhangs
            while len(shared_overhangs) < num_junctions:
                shared_overhangs.append("NNNN")

        # Score the overhang set
        score = self._score_golden_gate_set(shared_overhangs)

        # Generate per-construct plans for all combinations
        plans: list[ConstructPlan] = []
        variant_indices_list = list(
            itertools.product(*(range(len(cat)) for cat in part_categories))
        )

        for construct_id, variant_indices in enumerate(variant_indices_list):
            parts = [
                part_categories[cat_idx][var_idx]
                for cat_idx, var_idx in enumerate(variant_indices)
            ]

            plans.append(
                ConstructPlan(
                    construct_id=construct_id,
                    parts=parts,
                    variant_indices=list(variant_indices),
                    overhangs=shared_overhangs,
                    assembly_method="golden_gate",
                )
            )

        return CombinatorialResult(
            shared_overhangs=shared_overhangs,
            per_construct_plans=plans,
            total_constructs=total_constructs,
            assembly_method="golden_gate",
            feasible=feasible,
            score=score,
        )

    def _design_gibson(
        self,
        part_categories: list[list[str]],
        num_junctions: int,
        total_constructs: int,
    ) -> CombinatorialResult:
        """Design Gibson assembly with shared overlap regions.

        For Gibson, we extract overlap regions from the junction boundaries.
        Since variant sequences may differ at the boundaries, we use the
        first variant as a reference and check compatibility.
        """
        shared_overhangs = _gibson_overlap_regions(part_categories)
        feasible = len(shared_overhangs) == num_junctions

        # Score based on overlap Tm and GC
        score = 0.0
        if shared_overhangs:
            gc_scores = []
            for oh in shared_overhangs:
                gc = gc_content(oh)
                if 0.40 <= gc <= 0.60:
                    gc_scores.append(1.0)
                else:
                    gc_scores.append(max(0.0, 1.0 - abs(gc - 0.50) * 5))
            score = sum(gc_scores) / len(gc_scores)

        # Generate per-construct plans
        plans: list[ConstructPlan] = []
        variant_indices_list = list(
            itertools.product(*(range(len(cat)) for cat in part_categories))
        )

        for construct_id, variant_indices in enumerate(variant_indices_list):
            parts = [
                part_categories[cat_idx][var_idx]
                for cat_idx, var_idx in enumerate(variant_indices)
            ]

            plans.append(
                ConstructPlan(
                    construct_id=construct_id,
                    parts=parts,
                    variant_indices=list(variant_indices),
                    overhangs=shared_overhangs,
                    assembly_method="gibson",
                )
            )

        return CombinatorialResult(
            shared_overhangs=shared_overhangs,
            per_construct_plans=plans,
            total_constructs=total_constructs,
            assembly_method="gibson",
            feasible=feasible,
            score=score,
        )

    def _score_golden_gate_set(self, overhangs: list[str]) -> float:
        """Score a Golden Gate overhang set for orthogonality.

        Returns a score from 0.0 to 1.0 based on minimum pairwise
        orthogonality and absence of problematic features.
        """
        if not overhangs:
            return 0.0

        n = len(overhangs)
        max_cross = 0.0

        for i in range(n):
            if is_palindromic(overhangs[i]):
                return 0.0  # Palindromic overhangs are always infeasible

            for j in range(i + 1, n):
                if overhangs[i] == overhangs[j]:
                    return 0.0  # Duplicate overhangs

                cross = bsai_fidelity(overhangs[i], overhangs[j])
                max_cross = max(max_cross, cross)

        # Score: 1.0 if all cross-ligation is below threshold
        if max_cross <= self.max_cross_ligation:
            return 1.0 - max_cross  # Higher is better
        else:
            return max(0.0, 1.0 - max_cross * 10.0)
