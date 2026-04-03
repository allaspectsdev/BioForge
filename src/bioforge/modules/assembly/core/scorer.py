"""Multi-objective scoring for assembly quality."""

import statistics

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import Overhang, Partition
from bioforge.modules.assembly.core.thermo import ThermoEngine


class AssemblyScorer:
    """Compute composite quality score for a validated partition."""

    def __init__(self, config: AssemblyConfig, thermo: ThermoEngine):
        self.config = config
        self.thermo = thermo

    def score(self, partition: Partition, sequence: str) -> dict:
        """Score a partition. Returns dict with component scores and total."""
        overhangs = partition.get_overhangs(sequence)
        oh_seqs = partition.get_overhang_sequences(sequence)

        if not overhangs:
            return {"total": 1.0, "orthogonality": 1.0, "tm_uniformity": 1.0, "gc_balance": 1.0, "structure": 1.0}

        # Compute Tm for each overhang
        tms = [self.thermo.calc_tm(s) for s in oh_seqs]

        # Component scores
        ortho = self._orthogonality_score(oh_seqs)
        tm_uni = self._tm_uniformity_score(tms)
        gc_bal = self._gc_balance_score(overhangs)
        struct = self._structure_score(oh_seqs)

        total = (
            self.config.weight_orthogonality * ortho
            + self.config.weight_tm_uniformity * tm_uni
            + self.config.weight_gc_balance * gc_bal
            + self.config.weight_structure_avoidance * struct
        )

        return {
            "total": total,
            "orthogonality": ortho,
            "tm_uniformity": tm_uni,
            "gc_balance": gc_bal,
            "structure": struct,
            "tm_mean": statistics.mean(tms) if tms else 0.0,
            "tm_stdev": statistics.stdev(tms) if len(tms) > 1 else 0.0,
        }

    def _orthogonality_score(self, oh_seqs: list[str]) -> float:
        """Score based on minimum pairwise Hamming distance."""
        from bioforge.modules.assembly.core.constraints.orthogonality import pairwise_hamming

        if len(oh_seqs) < 2:
            return 1.0
        distances = pairwise_hamming(oh_seqs)
        k = len(oh_seqs)
        min_dist = float("inf")
        for i in range(k):
            for j in range(i + 1, k):
                min_dist = min(min_dist, distances[i, j])

        target = self.config.min_hamming_distance
        return min(1.0, min_dist / (target * 2)) if target > 0 else 1.0

    def _tm_uniformity_score(self, tms: list[float]) -> float:
        """Score based on how uniform the Tm values are."""
        if len(tms) < 2:
            return 1.0
        stdev = statistics.stdev(tms)
        # Perfect at 0 stdev, degrades with higher stdev
        return max(0.0, 1.0 - stdev / 10.0)

    def _gc_balance_score(self, overhangs: list[Overhang]) -> float:
        """Score based on how close GC content is to 50%."""
        if not overhangs:
            return 1.0
        deviations = [abs(oh.gc - 0.5) for oh in overhangs]
        avg_dev = statistics.mean(deviations)
        return max(0.0, 1.0 - avg_dev * 4.0)

    def _structure_score(self, oh_seqs: list[str]) -> float:
        """Score based on absence of secondary structure."""
        if not oh_seqs:
            return 1.0
        dgs = [self.thermo.calc_hairpin_dg(s) for s in oh_seqs]
        # More negative = worse. Threshold at -2 kcal/mol
        worst = min(dgs)
        if worst >= 0:
            return 1.0
        return max(0.0, 1.0 + worst / 5.0)
