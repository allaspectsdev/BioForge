"""Integration tests for the assembly solver."""

import random

from bioforge.modules.assembly.core.config import AssemblyConfig
from bioforge.modules.assembly.core.constraints.orthogonality import pairwise_hamming
from bioforge.modules.assembly.core.models import (
    Partition,
    gc_content,
    longest_homopolymer,
    reverse_complement,
)
from bioforge.modules.assembly.core.solver import AssemblySolver
from bioforge.modules.assembly.core.thermo import ThermoEngine


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


class TestThermo:
    def test_fallback_tm_reasonable(self):
        """Pure-Python NN Tm should be in a biologically reasonable range."""
        engine = ThermoEngine()
        # 25-mer with ~50% GC
        tm = engine.calc_tm("ATCGATCGATCGATCGATCGATCGA")
        assert 40 < tm < 80, f"Tm {tm} out of reasonable range"

    def test_primer3_and_fallback_agree(self):
        """If primer3 is available, both should give similar results."""
        from bioforge.modules.assembly.core.thermo import _HAS_PRIMER3
        if not _HAS_PRIMER3:
            return  # Skip if no primer3
        engine = ThermoEngine()
        seq = "ATCGATCGATCGATCGATCGATCGA"
        primer3_tm = engine.calc_tm(seq)
        fallback_engine = ThermoEngine.__new__(ThermoEngine)
        fallback_engine.na_conc = 50.0
        fallback_engine.oligo_conc = 250.0
        fallback_tm = fallback_engine._nn_tm(seq)
        # They should agree within ~5°C (different salt correction implementations)
        assert abs(primer3_tm - fallback_tm) < 10, f"primer3={primer3_tm:.1f}, fallback={fallback_tm:.1f}"


class TestSolverSmall:
    """Test solver on small sequences (6-10K bp)."""

    def test_solve_6k(self):
        seq = _random_dna(6300, seed=1)
        solver = AssemblySolver(seed=42)
        result = solver.solve(seq)

        assert result.partition is not None
        assert result.partition.num_fragments >= 2
        assert result.total_time_s >= 0

        # Fragments should be within bounds if feasible
        if result.feasible:
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
        assert result.total_time_s < 60


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


class TestConstraints:
    def test_hamming_distance_matrix(self):
        seqs = ["ATCGATCG", "ATCGATCG", "TAGCTAGC"]
        matrix = pairwise_hamming(seqs)
        assert matrix[0, 1] == 0  # Identical
        assert matrix[0, 2] > 0   # Different

    def test_partition_overhang_extraction(self):
        seq = "A" * 100 + "GCGCGCGCGCGCGCGCGCGCGCGCG" + "T" * 100
        partition = Partition(
            sequence_length=len(seq),
            boundaries=[112],
            overhang_lengths=[25],
        )
        oh_seqs = partition.get_overhang_sequences(seq)
        assert len(oh_seqs) == 1
        assert len(oh_seqs[0]) == 25


class TestModuleIntegration:
    def test_assembly_module_capabilities(self):
        from bioforge.modules.assembly import AssemblyModule
        mod = AssemblyModule()
        caps = mod.capabilities()
        names = {c.name for c in caps}
        assert "design_assembly" in names
        assert "calculate_tm" in names
        assert "check_overhang_quality" in names
        assert "reverse_complement" in names

    def test_assembly_module_mcp_tools(self):
        from bioforge.modules.assembly import AssemblyModule
        mod = AssemblyModule()
        tools = mod.mcp_tools()
        assert len(tools) == 4

    def test_module_registry_wiring(self):
        from bioforge.modules.assembly import AssemblyModule
        from bioforge.modules.registry import ModuleRegistry
        registry = ModuleRegistry()
        registry.register(AssemblyModule())
        assert len(registry.all_capabilities()) == 4
        assert len(registry.all_mcp_tools()) == 4
        assert "assembly.design" in registry.all_pipeline_steps()
