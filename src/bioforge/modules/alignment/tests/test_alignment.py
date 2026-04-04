"""Tests for the alignment module: Needleman-Wunsch and AlignmentModule."""

import asyncio

from bioforge.modules.alignment import AlignmentModule
from bioforge.modules.alignment.module import _needleman_wunsch


class TestNeedlemanWunsch:
    def test_identical_sequences(self):
        aligned1, aligned2, score = _needleman_wunsch("ATCG", "ATCG")

        # Identical sequences should align perfectly
        assert aligned1 == "ATCG"
        assert aligned2 == "ATCG"
        assert score > 0

    def test_one_mismatch(self):
        aligned1, aligned2, score = _needleman_wunsch("ATCG", "ATCC")

        # Should have 3 matches and 1 mismatch out of 4 positions
        alignment_len = len(aligned1)
        matches = sum(
            1 for a, b in zip(aligned1, aligned2) if a == b and a != "-"
        )
        identity = matches / max(alignment_len, 1)

        assert identity < 1.0

    def test_with_gap(self):
        aligned1, aligned2, score = _needleman_wunsch("ATCGATCG", "ATCATCG")

        # One sequence is shorter by 1 base, so alignment should contain a gap
        all_chars = aligned1 + aligned2
        assert "-" in all_chars

    def test_empty_sequences(self):
        aligned1, aligned2, score = _needleman_wunsch("", "")

        assert aligned1 == ""
        assert aligned2 == ""


class TestAlignmentModule:
    def test_module_info(self):
        mod = AlignmentModule()
        info = mod.info()

        assert info.name == "alignment"

    def test_has_3_capabilities(self):
        mod = AlignmentModule()
        caps = mod.capabilities()

        assert len(caps) == 3

    def test_has_2_pipeline_steps(self):
        mod = AlignmentModule()
        steps = mod.pipeline_steps()

        assert len(steps) == 2

    def test_pairwise_handler(self):
        mod = AlignmentModule()
        result = asyncio.run(
            mod._pairwise_align({"sequences": ["ATCG", "ATCC"]})
        )

        assert "identity_pct" in result
        assert "aligned_sequences" in result
        assert result["identity_pct"] < 100.0
