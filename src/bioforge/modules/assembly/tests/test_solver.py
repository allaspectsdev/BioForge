"""Integration tests for the assembly solver."""

import random
import string

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.models import (
    gc_content,
    longest_homopolymer,
    reverse_complement,
)
from bioforge.modules.assembly.core.solver import AssemblySolver


def _random_dna(length: int, seed: int = 42) -> str:
    rng = random.Random(seed)
    return "".join(rng.choices("ATCG", k=length))


class TestHelpers:
    def test_reverse_complement(self):
        assert reverse_complement("ATCG") == "CGAT"
        assert reverse_complement("AAAA") == "TTTT"
        assert reverse_complement("GCGC") == "GCGC"

    def test_gc_content(self):
        assert gc_content("GGCC") == 1.0
        assert gc_content("AATT") == 0.0
        assert gc_content("ATGC") == 0.5

    def test_longest_homopolymer(self):
        assert longest_homopolymer("AATTCC") == 2
        assert longest_homopolymer("AAAATCG") == 4
        assert longest_homopolymer("ATCG") == 1
        assert longest_homopolymer("") == 0


class TestSolverSmall:
    """Test solver on small sequences (6-10K bp)."""

    def test_solve_6k(self):
        seq = _random_dna(6300, seed=1)
        solver = AssemblySolver(seed=42)
        result = solver.solve(seq)

        assert result.partition is not None
        assert result.partition.num_fragments >= 2
        assert result.total_time_s >= 0

        # All fragments should be within bounds
        for frag in result.fragments:
            assert 2000 <= frag["length"] <= 2500, f"Fragment {frag['index']}: {frag['length']} bp"

    def test_solve_10k(self):
        seq = _random_dna(10000, seed=2)
        solver = AssemblySolver(seed=42)
        result = solver.solve(seq)

        assert result.partition.num_fragments >= 4
        assert len(result.overhangs) == result.partition.num_fragments - 1

    def test_fragments_cover_sequence(self):
        seq = _random_dna(6300, seed=3)
        solver = AssemblySolver(seed=42)
        result = solver.solve(seq)

        # First fragment starts at 0
        assert result.fragments[0]["start"] == 0
        # Last fragment ends at sequence length
        assert result.fragments[-1]["end"] == 6300
        # Fragments are contiguous
        for i in range(1, len(result.fragments)):
            assert result.fragments[i]["start"] == result.fragments[i - 1]["end"]


class TestSolverMedium:
    """Test solver on medium sequences (50-100K bp)."""

    def test_solve_50k(self):
        seq = _random_dna(50000, seed=4)
        config = AssemblyConfig(max_restarts=10, max_iterations_per_restart=200)
        solver = AssemblySolver(config=config, seed=42)
        result = solver.solve(seq)

        assert result.partition.num_fragments >= 20
        assert result.total_time_s < 60  # Should finish in under a minute


class TestQualityScores:
    def test_scores_present(self):
        seq = _random_dna(6300, seed=5)
        solver = AssemblySolver(seed=42)
        result = solver.solve(seq)

        assert "total" in result.quality_scores
        assert "orthogonality" in result.quality_scores
        assert "tm_uniformity" in result.quality_scores
        assert "gc_balance" in result.quality_scores
        assert 0.0 <= result.quality_scores["total"] <= 1.0
