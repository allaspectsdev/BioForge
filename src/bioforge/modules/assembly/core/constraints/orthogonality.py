"""C3: Pairwise overhang orthogonality via Hamming distance + ΔΔG.

Two-phase approach:
1. Numpy-vectorized pairwise Hamming distance (fast, O(k² × L))
2. Primer3 heterodimer ΔG on borderline pairs (slow, targeted)
"""

import numpy as np

from bioforge.modules.assembly.core.constraints.base import BaseConstraint
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    ConstraintViolation,
    Partition,
    reverse_complement,
)
from bioforge.modules.assembly.core.thermo import ThermoEngine


def _encode_sequences(seqs: list[str], target_len: int) -> np.ndarray:
    """Encode DNA sequences as uint8 array. Pad/truncate to target_len."""
    mapping = {"A": 0, "T": 1, "C": 2, "G": 3, "N": 4}
    result = np.zeros((len(seqs), target_len), dtype=np.uint8)
    for i, seq in enumerate(seqs):
        for j, c in enumerate(seq[:target_len]):
            result[i, j] = mapping.get(c.upper(), 4)
    return result


def pairwise_hamming(seqs: list[str]) -> np.ndarray:
    """Compute pairwise Hamming distance matrix for equal-length sequences.

    For variable-length overhangs, we pad to the max length and only compare
    valid positions.
    """
    if not seqs:
        return np.array([])

    max_len = max(len(s) for s in seqs)
    encoded = _encode_sequences(seqs, max_len)
    k = len(seqs)

    # Broadcast pairwise comparison: (k, 1, L) != (1, k, L) -> (k, k, L)
    diffs = encoded[:, np.newaxis, :] != encoded[np.newaxis, :, :]
    distances = diffs.sum(axis=2)

    return distances


class OrthogonalityConstraint(BaseConstraint):
    """C3: Overhangs must not cross-anneal. Hamming distance + ΔΔG check."""

    def __init__(self, config, thermo: ThermoEngine):
        super().__init__(config)
        self.thermo = thermo

    @property
    def name(self) -> str:
        return "orthogonality"

    def check(self, partition: Partition, sequence: str) -> ConstraintResult:
        oh_seqs = partition.get_overhang_sequences(sequence)
        if len(oh_seqs) < 2:
            return ConstraintResult.ok()

        violations = []

        # Also check against reverse complements
        rc_seqs = [reverse_complement(s) for s in oh_seqs]
        all_seqs = oh_seqs + rc_seqs

        # Phase 1: Hamming distance matrix
        hamming_matrix = pairwise_hamming(all_seqs)
        k = len(oh_seqs)
        min_hamming = self.config.min_hamming_distance

        # Check all pairs of original overhangs
        for i in range(k):
            for j in range(i + 1, k):
                dist = hamming_matrix[i, j]
                if dist < min_hamming:
                    violations.append(
                        ConstraintViolation(
                            constraint_name=self.name,
                            severity=ConstraintSeverity.FAIL,
                            message=f"Overhangs {i} and {j}: Hamming distance {dist} < {min_hamming}",
                            indices=[i, j],
                        )
                    )

            # Check each overhang against reverse complements of other overhangs
            for j in range(k):
                if i == j:
                    continue
                dist = hamming_matrix[i, k + j]  # i vs RC(j)
                if dist < min_hamming:
                    violations.append(
                        ConstraintViolation(
                            constraint_name=self.name,
                            severity=ConstraintSeverity.FAIL,
                            message=f"Overhang {i} vs RC({j}): Hamming distance {dist} < {min_hamming}",
                            indices=[i, j],
                        )
                    )

        # Phase 2: ΔΔG check on borderline pairs (Hamming distance near threshold)
        borderline_threshold = min_hamming + 3
        for i in range(k):
            for j in range(i + 1, k):
                dist = hamming_matrix[i, j]
                if min_hamming <= dist <= borderline_threshold:
                    dg = self.thermo.calc_heterodimer_dg(oh_seqs[i], oh_seqs[j])
                    if dg < -self.config.min_ddg_kcal:
                        violations.append(
                            ConstraintViolation(
                                constraint_name=self.name,
                                severity=ConstraintSeverity.WARNING,
                                message=(
                                    f"Overhangs {i} and {j}: ΔG {dg:.1f} kcal/mol "
                                    f"(borderline cross-anneal risk)"
                                ),
                                indices=[i, j],
                            )
                        )

        if violations:
            fail_count = sum(1 for v in violations if v.severity == ConstraintSeverity.FAIL)
            total_pairs = k * (k - 1) // 2
            score = max(0.0, 1.0 - fail_count / max(total_pairs, 1))
            return ConstraintResult(passed=(fail_count == 0), violations=violations, score=score)
        return ConstraintResult.ok()
