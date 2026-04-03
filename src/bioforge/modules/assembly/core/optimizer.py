"""Local search optimizer with simulated annealing."""

import math
import random

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.evaluator import Evaluator
from bioforge.modules.assembly.core.models import (
    ConstraintResult,
    ConstraintSeverity,
    Partition,
)


class Optimizer:
    """Greedy boundary perturbation with simulated annealing acceptance."""

    def __init__(
        self,
        config: AssemblyConfig,
        evaluator: Evaluator,
        rng: random.Random | None = None,
    ):
        self.config = config
        self.evaluator = evaluator
        self.rng = rng or random.Random()

    def optimize(
        self, partition: Partition, sequence: str
    ) -> tuple[Partition, ConstraintResult]:
        """Run SA optimization on a partition. Returns (best_partition, best_result)."""
        best = partition
        best_result = self.evaluator.evaluate(best, sequence)
        best_score = best_result.score

        if best_result.passed:
            return best, best_result

        current = best
        current_score = best_score
        temp = self.config.sa_initial_temp

        for iteration in range(self.config.max_iterations_per_restart):
            if best_result.passed:
                break

            # Select which boundary to perturb based on violations
            candidate = self._perturb(current, sequence, best_result)

            # Always cool, even if perturbation failed
            temp *= self.config.sa_cooling_rate

            if candidate is None:
                continue

            result = self.evaluator.evaluate(candidate, sequence)
            candidate_score = result.score

            # Accept or reject
            delta = candidate_score - current_score
            if delta > 0 or self._accept(delta, temp):
                current = candidate
                current_score = candidate_score

                if candidate_score > best_score:
                    best = candidate
                    best_score = candidate_score
                    best_result = result

        return best, best_result

    def _perturb(
        self, partition: Partition, sequence: str, result: ConstraintResult
    ) -> Partition | None:
        """Create a neighbor by perturbing one boundary."""
        if not partition.boundaries:
            return None

        num_boundaries = len(partition.boundaries)

        # Pick a boundary to modify — prefer ones adjacent to violated fragments/overhangs
        violated_indices = set()
        for v in result.violations:
            if v.severity == ConstraintSeverity.FAIL:
                violated_indices.update(v.indices)

        if violated_indices:
            # Map fragment/overhang indices to adjacent boundary indices.
            # Fragment i is bounded by boundary (i-1) on the left and boundary i on the right.
            # Overhang i corresponds to boundary i.
            candidate_boundaries = set()
            for idx in violated_indices:
                if 0 <= idx < num_boundaries:
                    candidate_boundaries.add(idx)       # boundary on right of fragment idx
                if 0 <= idx - 1 < num_boundaries:
                    candidate_boundaries.add(idx - 1)   # boundary on left of fragment idx

            boundary_idx = self.rng.choice(
                list(candidate_boundaries) or list(range(num_boundaries))
            )
        else:
            boundary_idx = self.rng.randint(0, num_boundaries - 1)

        # Try boundary position perturbation or overhang length adjustment
        if self.rng.random() < 0.7:
            # Perturb boundary position
            delta = self.rng.choice(self.config.boundary_deltas)
            new_boundaries = list(partition.boundaries)
            new_boundaries[boundary_idx] = partition.boundaries[boundary_idx] + delta

            # Clamp to valid range
            new_boundaries[boundary_idx] = max(
                self.config.min_fragment_bp,
                min(
                    partition.sequence_length - self.config.min_fragment_bp,
                    new_boundaries[boundary_idx],
                ),
            )

            # Check ordering
            if boundary_idx > 0 and new_boundaries[boundary_idx] <= new_boundaries[boundary_idx - 1]:
                return None
            if (
                boundary_idx < len(new_boundaries) - 1
                and new_boundaries[boundary_idx] >= new_boundaries[boundary_idx + 1]
            ):
                return None

            return Partition(
                sequence_length=partition.sequence_length,
                boundaries=new_boundaries,
                overhang_lengths=list(partition.overhang_lengths),
            )
        else:
            # Adjust overhang length
            delta = self.rng.choice(self.config.overhang_deltas)
            new_oh = list(partition.overhang_lengths)
            new_oh[boundary_idx] = max(
                self.config.min_overhang_bp,
                min(self.config.max_overhang_bp, new_oh[boundary_idx] + delta),
            )

            return Partition(
                sequence_length=partition.sequence_length,
                boundaries=list(partition.boundaries),
                overhang_lengths=new_oh,
            )

    def _accept(self, delta: float, temp: float) -> bool:
        """Simulated annealing acceptance probability."""
        if temp <= 0:
            return False
        prob = math.exp(delta / temp)
        return self.rng.random() < prob
