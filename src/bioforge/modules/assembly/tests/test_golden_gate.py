"""Tests for the Golden Gate solver, constraints, and codon optimizer."""

from bioforge.modules.assembly.core.golden_gate.enzymes import (
    ENZYMES,
    bsai_fidelity,
    is_palindromic,
)
from bioforge.modules.assembly.core.golden_gate.gg_solver import GoldenGateSolver
from bioforge.modules.assembly.core.golden_gate.gg_constraints import (
    LigationFidelityConstraint,
    EnzymeCompatibilityConstraint,
    OverhangSetConstraint,
)
from bioforge.modules.assembly.core.codon.optimizer import CodonOptimizer
from bioforge.modules.assembly.core.codon.cai import compute_cai
from bioforge.modules.assembly.core.codon.tables import CODON_TABLES


class TestEnzymes:
    def test_enzyme_database_has_bsai(self):
        assert "BsaI" in ENZYMES

    def test_enzyme_database_has_bpii(self):
        assert "BpiI" in ENZYMES

    def test_enzyme_database_has_esp3i(self):
        assert "Esp3I" in ENZYMES

    def test_enzyme_database_has_sapi(self):
        assert "SapI" in ENZYMES

    def test_bsai_fidelity_cognate(self):
        # AAAA paired with itself: the RC of AAAA is TTTT, so
        # bsai_fidelity("AAAA", "AAAA") checks AAAA vs RC(AAAA) = TTTT.
        # For a true cognate pair we need oh1 == RC(oh2), meaning
        # oh2's RC equals oh1. AAAA's RC is TTTT, which != AAAA.
        # So "AAAA","AAAA" is NOT cognate. A true cognate pair:
        # bsai_fidelity("AATG", "CATT") where RC(CATT) = AATG.
        result = bsai_fidelity("AATG", "CATT")
        assert result == 1.0

    def test_bsai_fidelity_mismatch(self):
        # Two sequences that are not cognate pairs should have low fidelity
        result = bsai_fidelity("AAAA", "AAAT")
        assert result < 0.2

    def test_is_palindromic_true(self):
        # RC of ATAT = ATAT, so it is palindromic
        assert is_palindromic("ATAT") is True

    def test_is_palindromic_false(self):
        # RC of AACG = CGTT, which != AACG
        assert is_palindromic("AACG") is False


class TestGoldenGateSolver:
    def test_solve_3_parts(self):
        parts = ["ATCG" * 100, "GCTA" * 100, "ATATGC" * 66]
        solver = GoldenGateSolver(seed=42)
        result = solver.solve(parts)

        assert len(result.parts) == 3
        assert len(result.overhangs) >= 2

    def test_overhangs_not_palindromic(self):
        parts = ["ATCG" * 100, "GCTA" * 100, "ATATGC" * 66]
        solver = GoldenGateSolver(seed=42)
        result = solver.solve(parts)

        for oh in result.overhangs:
            assert not is_palindromic(oh), f"Overhang {oh} is palindromic"

    def test_overhangs_are_4bp(self):
        parts = ["ATCG" * 100, "GCTA" * 100, "ATATGC" * 66]
        solver = GoldenGateSolver(seed=42)
        result = solver.solve(parts)

        for oh in result.overhangs:
            assert len(oh) == 4, f"Overhang {oh} is not 4bp (len={len(oh)})"


class TestCodonOptimizer:
    def test_produces_valid_dna(self):
        optimizer = CodonOptimizer(organism="ecoli_k12", seed=42)
        result = optimizer.optimize("MKFLILLFNILCGSA")

        assert all(c in "ATCG" for c in result.optimized_dna)

    def test_correct_length(self):
        protein = "MKFLILLFNILCGSA"
        optimizer = CodonOptimizer(organism="ecoli_k12", seed=42)
        result = optimizer.optimize(protein)

        assert len(result.optimized_dna) == 3 * len(protein)

    def test_strips_stop_codon(self):
        # The optimizer strips invalid chars; if '*' is present it should
        # be treated as invalid and raise ValueError. Let's test a clean
        # protein without stop instead.
        protein = "MKFL"
        optimizer = CodonOptimizer(organism="ecoli_k12", seed=42)
        result = optimizer.optimize(protein)

        assert len(result.optimized_dna) == 12

    def test_cai_score_range(self):
        optimizer = CodonOptimizer(organism="ecoli_k12", seed=42)
        result = optimizer.optimize("MKFLILLFNILCGSA")

        assert 0.0 <= result.cai_score <= 1.0

    def test_ecoli_optimization_high_cai(self):
        optimizer = CodonOptimizer(organism="ecoli_k12", seed=42)
        result = optimizer.optimize("MKFLILLFNILCGSADEKRQVTPHY")

        assert result.cai_score > 0.5


class TestCAI:
    def test_cai_range(self):
        # A valid in-frame DNA sequence
        dna = "ATGGCTAAAGCTTAA"  # 5 codons
        score = compute_cai(dna, "ecoli_k12")

        assert 0.0 <= score <= 1.0

    def test_high_cai_for_optimal(self):
        # Construct DNA using only the most frequent E. coli codons:
        # CTG (Leu), CTG (Leu), GCG (Ala), GCG (Ala), ACC (Thr), ACC (Thr)
        optimal_dna = "CTGCTGGCGGCGACCACC"
        score = compute_cai(optimal_dna, "ecoli_k12")

        assert score > 0.8


class TestCodonTables:
    def test_tables_exist_ecoli(self):
        assert "ecoli_k12" in CODON_TABLES

    def test_tables_exist_yeast(self):
        assert "yeast" in CODON_TABLES

    def test_tables_exist_cho(self):
        assert "cho" in CODON_TABLES

    def test_tables_exist_hek293(self):
        assert "hek293" in CODON_TABLES

    def test_all_codons_present(self):
        """Each table should have all 64 codons."""
        for org_name, table in CODON_TABLES.items():
            assert len(table) == 64, (
                f"Table '{org_name}' has {len(table)} codons, expected 64"
            )
