"""Golden Gate Assembly solver: overhang set design for Type IIS cloning.

Selects optimal 4bp overhangs at part junctions to maximize assembly
fidelity. Uses greedy selection with fidelity-based scoring against the
NEB ligation fidelity model.

The algorithm:
1. Extract junction sequences (boundaries between input parts)
2. For each junction, enumerate candidate overhangs from local context
3. Greedy selection: pick the overhang at each junction that maximizes
   minimum pairwise orthogonality with all previously selected overhangs
4. Score the full set and return the best result
"""

import logging
import random
from dataclasses import dataclass, field

from bioforge.modules.assembly.core.golden_gate.enzymes import (
    ENZYMES,
    TypeIISEnzyme,
    bsai_fidelity,
    is_palindromic,
    overhang_fidelity_matrix,
)
from bioforge.modules.assembly.core.models import reverse_complement

logger = logging.getLogger(__name__)

# Candidate overhang window: how many bases on each side of a junction
# to consider for overhang extraction.
_CONTEXT_WINDOW = 10


@dataclass(frozen=True, slots=True)
class GoldenGatePart:
    """A single part prepared for Golden Gate assembly.

    Attributes:
        index: Part index in the assembly order.
        original_sequence: The original input sequence of this part.
        flanked_sequence: The part sequence with flanking enzyme sites and overhangs.
        left_overhang: The 4bp overhang on the 5' end.
        right_overhang: The 4bp overhang on the 3' end.
        enzyme: The Type IIS enzyme used.
    """

    index: int
    original_sequence: str
    flanked_sequence: str
    left_overhang: str
    right_overhang: str
    enzyme: str


@dataclass
class GoldenGateResult:
    """Result of Golden Gate assembly design.

    Attributes:
        parts: List of parts with flanking sequences.
        overhangs: The selected overhang set (one per junction + terminal pair).
        fidelity_matrix: Pairwise fidelity scores between all overhangs.
        min_cognate_fidelity: Minimum fidelity among cognate (intended) pairs.
        max_cross_ligation: Maximum fidelity among non-cognate pairs.
        enzyme: The enzyme used for the assembly.
        feasible: Whether the design meets all fidelity thresholds.
    """

    parts: list[GoldenGatePart]
    overhangs: list[str]
    fidelity_matrix: list[list[float]]
    min_cognate_fidelity: float
    max_cross_ligation: float
    enzyme: str
    feasible: bool
    score: float = 0.0


def _extract_junction_candidates(
    parts: list[str],
    overhang_length: int = 4,
    context_window: int = _CONTEXT_WINDOW,
) -> list[list[str]]:
    """Extract candidate overhangs at each junction between consecutive parts.

    For each junction between part[i] and part[i+1], we look at the last
    `context_window` bases of part[i] and the first `context_window` bases
    of part[i+1], then enumerate all possible overhang_length-mers from
    this combined context.

    Args:
        parts: List of part DNA sequences.
        overhang_length: Length of overhangs to extract (typically 4).
        context_window: Number of bases on each side of junction to consider.

    Returns:
        List of lists, one per junction, each containing candidate overhangs.
    """
    candidates_per_junction: list[list[str]] = []

    for i in range(len(parts) - 1):
        left_context = parts[i][-context_window:] if len(parts[i]) >= context_window else parts[i]
        right_context = parts[i + 1][:context_window] if len(parts[i + 1]) >= context_window else parts[i + 1]
        junction_seq = (left_context + right_context).upper()

        candidates = set()
        for pos in range(len(junction_seq) - overhang_length + 1):
            oh = junction_seq[pos:pos + overhang_length]
            if all(c in "ACGT" for c in oh):
                # Skip palindromic overhangs — they self-ligate
                if not is_palindromic(oh):
                    candidates.add(oh)

        if not candidates:
            # Fallback: use the exact junction sequence
            exact = (parts[i][-overhang_length // 2:] + parts[i + 1][:overhang_length // 2]).upper()
            if len(exact) == overhang_length and all(c in "ACGT" for c in exact):
                candidates.add(exact)

        candidates_per_junction.append(sorted(candidates))

    return candidates_per_junction


def _score_overhang_set(overhangs: list[str]) -> tuple[float, float, float]:
    """Score an overhang set by its pairwise ligation fidelity profile.

    Returns:
        Tuple of (overall_score, min_cognate_fidelity, max_cross_ligation).
        Overall score combines cognate fidelity and cross-ligation penalty.
    """
    if not overhangs:
        return 0.0, 0.0, 0.0

    n = len(overhangs)
    min_cognate = 1.0
    max_cross = 0.0

    for i in range(n):
        # Cognate fidelity: overhang with its own reverse complement
        cognate = bsai_fidelity(overhangs[i], reverse_complement(overhangs[i]))
        min_cognate = min(min_cognate, cognate)

        for j in range(i + 1, n):
            # Cross-ligation: overhang i with overhang j (non-cognate)
            cross_fwd = bsai_fidelity(overhangs[i], overhangs[j])
            cross_rev = bsai_fidelity(overhangs[j], overhangs[i])
            max_cross = max(max_cross, cross_fwd, cross_rev)

            # Also check reverse complement cross-ligation
            rc_cross = bsai_fidelity(overhangs[i], reverse_complement(overhangs[j]))
            if overhangs[i] != reverse_complement(overhangs[j]):
                max_cross = max(max_cross, rc_cross)

    # Score: high cognate fidelity and low cross-ligation
    # Penalize heavily if max_cross > 0.01
    cross_penalty = max(0.0, 1.0 - max_cross * 100.0) if max_cross < 0.01 else 0.0
    cognate_bonus = min_cognate

    score = 0.5 * cognate_bonus + 0.5 * cross_penalty
    return score, min_cognate, max_cross


def _is_compatible(candidate: str, selected: list[str], max_cross: float = 0.01) -> bool:
    """Check if a candidate overhang is compatible with already-selected overhangs.

    Compatible means:
    - Not a duplicate of any selected overhang
    - Not the reverse complement of any selected overhang
    - Cross-ligation fidelity with all selected overhangs is below threshold
    """
    candidate_rc = reverse_complement(candidate)

    for existing in selected:
        if candidate == existing or candidate == reverse_complement(existing):
            return False
        if candidate_rc == existing:
            return False

        # Check cross-ligation in both directions
        cross1 = bsai_fidelity(candidate, existing)
        cross2 = bsai_fidelity(existing, candidate)
        if cross1 > max_cross or cross2 > max_cross:
            return False

        # Check reverse complement cross-ligation
        cross_rc = bsai_fidelity(candidate, reverse_complement(existing))
        if candidate != reverse_complement(existing) and cross_rc > max_cross:
            return False

    return True


class GoldenGateSolver:
    """Designs optimal overhang sets for Golden Gate assembly.

    Given a list of part sequences and a Type IIS enzyme, finds a set of
    4bp overhangs (one per junction) that maximizes assembly fidelity:
    cognate pairs should ligate efficiently (>0.95) while non-cognate
    pairs should have minimal cross-ligation (<0.01).

    Args:
        enzyme_name: Name of the Type IIS enzyme (default "BsaI").
        num_trials: Number of random overhang set trials to evaluate.
        max_cross_ligation: Maximum allowed cross-ligation fidelity.
        min_cognate_fidelity: Minimum required cognate ligation fidelity.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        enzyme_name: str = "BsaI",
        num_trials: int = 100,
        max_cross_ligation: float = 0.01,
        min_cognate_fidelity: float = 0.95,
        seed: int | None = None,
    ):
        if enzyme_name not in ENZYMES:
            raise ValueError(
                f"Unknown enzyme '{enzyme_name}'. "
                f"Available: {', '.join(ENZYMES.keys())}"
            )
        self.enzyme = ENZYMES[enzyme_name]
        self.num_trials = num_trials
        self.max_cross_ligation = max_cross_ligation
        self.min_cognate_fidelity = min_cognate_fidelity
        self.rng = random.Random(seed)

    def solve(self, parts: list[str]) -> GoldenGateResult:
        """Design Golden Gate assembly for the given parts.

        Args:
            parts: List of DNA sequences to assemble in order.

        Returns:
            GoldenGateResult with the optimal overhang set and flanked parts.

        Raises:
            ValueError: If fewer than 2 parts are provided.
        """
        if len(parts) < 2:
            raise ValueError("Golden Gate assembly requires at least 2 parts")

        num_junctions = len(parts) - 1
        overhang_len = self.enzyme.overhang_length

        # Step 1: Extract candidate overhangs at each junction
        junction_candidates = _extract_junction_candidates(
            parts, overhang_length=overhang_len
        )

        # Ensure every junction has at least one candidate
        for i, candidates in enumerate(junction_candidates):
            if not candidates:
                # Generate a fallback overhang from the junction boundary
                left = parts[i][-2:] if len(parts[i]) >= 2 else "AT"
                right = parts[i + 1][:2] if len(parts[i + 1]) >= 2 else "GC"
                fallback = (left + right).upper()[:overhang_len]
                while len(fallback) < overhang_len:
                    fallback += "A"
                junction_candidates[i] = [fallback]

        # Step 2: Greedy selection with multiple random restarts
        best_overhangs: list[str] | None = None
        best_score = -1.0
        best_min_cognate = 0.0
        best_max_cross = 1.0

        for trial in range(self.num_trials):
            selected = self._greedy_select(junction_candidates, num_junctions)
            if selected is None:
                continue

            score, min_cog, max_crs = _score_overhang_set(selected)
            if score > best_score:
                best_score = score
                best_overhangs = selected
                best_min_cognate = min_cog
                best_max_cross = max_crs

            # Early exit if we found a perfect set
            if min_cog >= self.min_cognate_fidelity and max_crs <= self.max_cross_ligation:
                break

        if best_overhangs is None:
            # Last resort: take the first candidate from each junction
            best_overhangs = [
                candidates[0] if candidates else "AAAA"
                for candidates in junction_candidates
            ]
            best_score, best_min_cognate, best_max_cross = _score_overhang_set(
                best_overhangs
            )

        # Step 3: Build flanked parts
        flanked_parts = self._build_flanked_parts(parts, best_overhangs)

        # Step 4: Compute full fidelity matrix
        fidelity_mat = overhang_fidelity_matrix(best_overhangs)

        feasible = (
            best_min_cognate >= self.min_cognate_fidelity
            and best_max_cross <= self.max_cross_ligation
        )

        return GoldenGateResult(
            parts=flanked_parts,
            overhangs=best_overhangs,
            fidelity_matrix=fidelity_mat,
            min_cognate_fidelity=best_min_cognate,
            max_cross_ligation=best_max_cross,
            enzyme=self.enzyme.name,
            feasible=feasible,
            score=best_score,
        )

    def _greedy_select(
        self,
        junction_candidates: list[list[str]],
        num_junctions: int,
    ) -> list[str] | None:
        """Greedy overhang selection with randomized candidate ordering.

        For each junction in order, pick the candidate overhang that is
        compatible with all previously selected overhangs and has the
        best fidelity profile.
        """
        selected: list[str] = []

        # Randomize junction processing order for diversity across trials
        junction_order = list(range(num_junctions))
        self.rng.shuffle(junction_order)

        # Map from junction order position back to result index
        result = [None] * num_junctions

        for junction_idx in junction_order:
            candidates = list(junction_candidates[junction_idx])
            self.rng.shuffle(candidates)

            best_candidate = None
            best_cand_score = -1.0

            for candidate in candidates:
                if not _is_compatible(
                    candidate, selected, self.max_cross_ligation
                ):
                    continue

                # Score: how well does this candidate work with existing set?
                test_set = selected + [candidate]
                score, _, _ = _score_overhang_set(test_set)
                if score > best_cand_score:
                    best_cand_score = score
                    best_candidate = candidate

            if best_candidate is None:
                # Could not find compatible overhang for this junction
                return None

            selected.append(best_candidate)
            result[junction_idx] = best_candidate

        return result  # type: ignore[return-value]

    def _build_flanked_parts(
        self,
        parts: list[str],
        overhangs: list[str],
    ) -> list[GoldenGatePart]:
        """Build part sequences flanked with enzyme recognition sites and overhangs.

        Each part gets:
        - 5' flank: enzyme_site + overhang (from left junction)
        - 3' flank: overhang_rc + enzyme_site_rc (from right junction)

        The first part uses a fixed start overhang, the last part uses a
        fixed end overhang, and interior junctions use the designed overhangs.
        """
        enzyme_site = self.enzyme.recognition_site
        enzyme_site_rc = reverse_complement(enzyme_site)
        flanked = []

        for i, part_seq in enumerate(parts):
            # Left overhang
            if i == 0:
                left_oh = overhangs[0] if overhangs else "AAAA"
            else:
                left_oh = overhangs[i - 1]

            # Right overhang
            if i == len(parts) - 1:
                right_oh = overhangs[-1] if overhangs else "TTTT"
            else:
                right_oh = overhangs[i]

            # Build flanked sequence:
            # 5': [enzyme_site][spacer_to_cut][left_overhang][part_sequence]
            # 3': [part_sequence][right_overhang_rc][spacer_to_cut_rc][enzyme_site_rc]
            # Simplified: enzyme_site + left_oh + part + right_oh_rc + enzyme_site_rc
            right_oh_rc = reverse_complement(right_oh)

            flanked_seq = (
                enzyme_site
                + left_oh
                + part_seq
                + right_oh_rc
                + enzyme_site_rc
            )

            flanked.append(
                GoldenGatePart(
                    index=i,
                    original_sequence=part_seq,
                    flanked_sequence=flanked_seq,
                    left_overhang=left_oh,
                    right_overhang=right_oh,
                    enzyme=self.enzyme.name,
                )
            )

        return flanked
