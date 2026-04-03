"""Top-level assembly solver: generate-optimize loop with restarts."""

import logging
import random
import time
from dataclasses import dataclass, field

from bioforge.core.exceptions import NoFeasiblePartitionError
from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.evaluator import Evaluator
from bioforge.modules.assembly.core.generator import generate_partition
from bioforge.modules.assembly.core.models import ConstraintResult, Partition
from bioforge.modules.assembly.core.optimizer import Optimizer
from bioforge.modules.assembly.core.scorer import AssemblyScorer
from bioforge.modules.assembly.core.thermo import ThermoEngine

logger = logging.getLogger(__name__)


@dataclass
class SolverResult:
    """Result of the assembly solver."""

    partition: Partition
    constraint_result: ConstraintResult
    quality_scores: dict
    feasible: bool
    restarts_used: int
    total_time_s: float
    fragments: list[dict] = field(default_factory=list)
    overhangs: list[dict] = field(default_factory=list)


class AssemblySolver:
    """Multi-restart generate-optimize solver for DNA fragment assembly."""

    def __init__(self, config: AssemblyConfig | None = None, seed: int | None = None):
        self.config = config or AssemblyConfig()
        self.rng = random.Random(seed)
        self.thermo = ThermoEngine(
            na_conc=self.config.na_conc_mm,
            mg_conc=self.config.mg_conc_mm,
            oligo_conc=self.config.oligo_conc_nm,
        )
        self.evaluator = Evaluator(self.config, self.thermo)
        self.optimizer = Optimizer(self.config, self.evaluator, self.rng)
        self.scorer = AssemblyScorer(self.config, self.thermo)

    def solve(self, sequence: str) -> SolverResult:
        """Find a feasible partition for the given DNA sequence.

        Returns the best partition found, whether feasible or not.
        """
        start_time = time.monotonic()
        seq_len = len(sequence)

        best_partition: Partition | None = None
        best_result: ConstraintResult | None = None
        best_score = -1.0
        restarts_used = 0

        for restart in range(max(1, self.config.max_restarts)):
            restarts_used = restart + 1
            # Generate initial candidate
            candidate = generate_partition(seq_len, self.config, self.rng)

            # Optimize
            optimized, result = self.optimizer.optimize(candidate, sequence)

            if result.score > best_score:
                best_partition = optimized
                best_result = result
                best_score = result.score

            if result.passed:
                logger.info("Feasible partition found at restart %d", restart)
                break

            # Clear thermo cache periodically to manage memory
            if restart % 10 == 9:
                self.thermo.clear_cache()

        elapsed = time.monotonic() - start_time
        if best_partition is None or best_result is None:
            raise NoFeasiblePartitionError("Solver produced no partitions")

        # Compute quality scores
        quality = self.scorer.score(best_partition, sequence)

        # Build fragment and overhang summaries
        fragments = []
        for frag in best_partition.get_fragments():
            fragments.append({
                "index": frag.index,
                "start": frag.start,
                "end": frag.end,
                "length": frag.length,
            })

        overhangs = []
        for oh in best_partition.get_overhangs(sequence):
            tm = self.thermo.calc_tm(oh.sequence)
            overhangs.append({
                "index": len(overhangs),
                "position": oh.position,
                "sequence": oh.sequence,
                "length": oh.length,
                "tm": round(tm, 1),
                "gc": round(oh.gc, 3),
                "homopolymer_run": oh.homopolymer_run,
            })

        return SolverResult(
            partition=best_partition,
            constraint_result=best_result,
            quality_scores=quality,
            feasible=best_result.passed,
            restarts_used=restarts_used,
            total_time_s=round(elapsed, 3),
            fragments=fragments,
            overhangs=overhangs,
        )
