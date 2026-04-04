"""Codon optimization engine with beam search and constraint awareness.

Optimizes a protein (amino acid) sequence for expression in a target
organism by selecting codons that maximize usage frequency while
respecting constraints on GC content, forbidden sequence patterns
(e.g., restriction enzyme sites), and mRNA secondary structure.

The beam search evaluates multiple candidate DNA sequences in parallel,
scoring each by a composite metric of codon adaptation, GC balance,
and pattern avoidance. A sliding window estimates local mRNA folding
energy to penalize sequences with strong secondary structure that
could impede translation.
"""

import logging
import math
import random
from dataclasses import dataclass, field

from bioforge.modules.assembly.core.codon.cai import compute_cai
from bioforge.modules.assembly.core.codon.tables import (
    AA_TO_CODONS,
    CODON_TABLES,
    GENETIC_CODE,
)
from bioforge.modules.assembly.core.models import gc_content

logger = logging.getLogger(__name__)

# Amino acid single-letter codes (excluding stop)
AMINO_ACIDS = set("ACDEFGHIKLMNPQRSTVWY")


@dataclass
class CodonOptimizationResult:
    """Result of codon optimization.

    Attributes:
        optimized_dna: The optimized DNA coding sequence.
        protein_sequence: The input protein sequence (for verification).
        organism: The target organism.
        cai_score: Codon Adaptation Index of the optimized sequence.
        gc_content: Overall GC content (fraction, 0.0-1.0).
        avoided_patterns_count: Number of forbidden patterns that were
            successfully avoided during optimization.
        codon_choices: Per-position codon selections with scores.
    """

    optimized_dna: str
    protein_sequence: str
    organism: str
    cai_score: float
    gc_content: float
    avoided_patterns_count: int
    codon_choices: list[dict[str, str | float]] = field(default_factory=list)


def _gc_penalty(
    seq: str,
    target_gc_min: float,
    target_gc_max: float,
) -> float:
    """Compute a GC content penalty for a sequence.

    Returns 1.0 if GC is within target range, <1.0 otherwise.
    Penalty increases with distance from target range.
    """
    gc = gc_content(seq)
    if target_gc_min <= gc <= target_gc_max:
        return 1.0
    if gc < target_gc_min:
        deviation = target_gc_min - gc
    else:
        deviation = gc - target_gc_max
    # Exponential penalty
    return math.exp(-10.0 * deviation)


def _contains_pattern(seq: str, patterns: list[str]) -> bool:
    """Check if sequence contains any of the forbidden patterns."""
    seq_upper = seq.upper()
    for pattern in patterns:
        if pattern.upper() in seq_upper:
            return True
    return False


def _count_patterns_avoided(
    seq: str,
    patterns: list[str],
) -> int:
    """Count how many patterns from the avoid list are NOT in the sequence."""
    seq_upper = seq.upper()
    count = 0
    for pattern in patterns:
        if pattern.upper() not in seq_upper:
            count += 1
    return count


def _simple_folding_penalty(window: str) -> float:
    """Estimate mRNA secondary structure penalty for a sliding window.

    Uses a simplified model based on GC content and self-complementarity
    within the window. High GC regions and palindromic stretches are
    penalized as they can form stable secondary structures that impede
    ribosome scanning.

    Returns a score from 0.0 (strong structure, bad) to 1.0 (no structure, good).
    """
    if len(window) < 6:
        return 1.0

    gc = gc_content(window)

    # High GC in mRNA windows correlates with secondary structure
    gc_penalty = 1.0
    if gc > 0.7:
        gc_penalty = 0.5
    elif gc > 0.6:
        gc_penalty = 0.8

    # Check for simple palindromic self-complementarity
    complement = {"A": "T", "T": "A", "G": "C", "C": "G"}
    window_upper = window.upper()
    max_stem = 0

    # Check if any 4+ bp stretch can form a stem-loop
    half = len(window_upper) // 2
    for stem_len in range(4, half + 1):
        for start in range(len(window_upper) - 2 * stem_len - 3):
            left = window_upper[start:start + stem_len]
            # Look for complement in the right half
            for right_start in range(start + stem_len + 3, len(window_upper) - stem_len + 1):
                right = window_upper[right_start:right_start + stem_len]
                # Check if right is reverse complement of left
                rc_left = "".join(complement.get(c, "N") for c in reversed(left))
                if right == rc_left:
                    max_stem = max(max_stem, stem_len)
                    break

    stem_penalty = 1.0
    if max_stem >= 8:
        stem_penalty = 0.3
    elif max_stem >= 6:
        stem_penalty = 0.6
    elif max_stem >= 4:
        stem_penalty = 0.85

    return gc_penalty * stem_penalty


@dataclass
class _BeamCandidate:
    """A candidate sequence in the beam search."""

    codons: list[str]
    score: float = 0.0


class CodonOptimizer:
    """Optimizes protein sequences to DNA for a target organism.

    Uses a beam search that evaluates multiple candidate codon selections
    in parallel, scoring by usage frequency, GC content, pattern avoidance,
    and mRNA secondary structure.

    Args:
        organism: Target organism (key into CODON_TABLES).
        avoid_patterns: List of DNA patterns to avoid (e.g., ["GGTCTC"]
            for BsaI sites).
        target_gc: Tuple of (min_gc, max_gc) as fractions (default 0.40-0.60).
        beam_width: Number of candidates to maintain during beam search.
        seed: Random seed for reproducibility.
    """

    def __init__(
        self,
        organism: str = "ecoli_k12",
        avoid_patterns: list[str] | None = None,
        target_gc: tuple[float, float] = (0.40, 0.60),
        beam_width: int = 5,
        seed: int | None = None,
    ):
        if organism not in CODON_TABLES:
            raise ValueError(
                f"Unknown organism '{organism}'. "
                f"Available: {', '.join(sorted(CODON_TABLES.keys()))}"
            )

        self.organism = organism
        self.codon_table = CODON_TABLES[organism]
        self.avoid_patterns = [p.upper() for p in (avoid_patterns or [])]
        self.target_gc_min, self.target_gc_max = target_gc
        self.beam_width = beam_width
        self.rng = random.Random(seed)

        # Precompute: for each amino acid, sort codons by frequency
        self._sorted_codons: dict[str, list[tuple[str, float]]] = {}
        for aa, codons in AA_TO_CODONS.items():
            if aa == "*":
                continue
            scored = [(c, self.codon_table.get(c, 0.0)) for c in codons]
            scored.sort(key=lambda x: x[1], reverse=True)
            self._sorted_codons[aa] = scored

    def optimize(self, protein_sequence: str) -> CodonOptimizationResult:
        """Optimize a protein sequence to DNA for the target organism.

        Args:
            protein_sequence: Amino acid sequence using single-letter codes.
                Must not contain stop codons.

        Returns:
            CodonOptimizationResult with the optimized DNA sequence and metrics.

        Raises:
            ValueError: If protein sequence contains invalid amino acids.
        """
        protein = protein_sequence.upper().replace(" ", "").replace("\n", "")
        protein = protein.rstrip("*")  # Strip trailing stop codon

        # Validate protein sequence
        invalid_chars = set(protein) - AMINO_ACIDS
        if invalid_chars:
            raise ValueError(
                f"Invalid amino acid characters: {invalid_chars}. "
                f"Use single-letter codes (ACDEFGHIKLMNPQRSTVWY)."
            )

        if len(protein) == 0:
            raise ValueError("Protein sequence is empty.")

        # Run beam search
        best_codons = self._beam_search(protein)

        # Build result
        optimized_dna = "".join(best_codons)
        cai = compute_cai(optimized_dna, self.organism)
        gc = gc_content(optimized_dna)
        avoided = _count_patterns_avoided(optimized_dna, self.avoid_patterns)

        # Build per-position codon info
        codon_choices = []
        for i, (aa, codon) in enumerate(zip(protein, best_codons)):
            freq = self.codon_table.get(codon, 0.0)
            codon_choices.append({
                "position": i,
                "amino_acid": aa,
                "codon": codon,
                "frequency": round(freq, 3),
            })

        return CodonOptimizationResult(
            optimized_dna=optimized_dna,
            protein_sequence=protein,
            organism=self.organism,
            cai_score=round(cai, 4),
            gc_content=round(gc, 4),
            avoided_patterns_count=avoided,
            codon_choices=codon_choices,
        )

    def _beam_search(self, protein: str) -> list[str]:
        """Beam search over codon choices for each amino acid position.

        Maintains `beam_width` candidate sequences, extending each by one
        codon at each step. Candidates are scored by a composite metric
        and only the top-scoring are kept.
        """
        # Initialize beam with empty candidates
        beam: list[_BeamCandidate] = [_BeamCandidate(codons=[], score=0.0)]

        folding_window_size = 30  # nucleotides for mRNA structure check

        for pos, aa in enumerate(protein):
            next_beam: list[_BeamCandidate] = []
            codon_options = self._sorted_codons.get(aa, [])

            if not codon_options:
                # Unknown amino acid — skip
                logger.warning("No codons found for amino acid '%s'", aa)
                for cand in beam:
                    cand.codons.append("NNN")
                continue

            for candidate in beam:
                for codon, freq in codon_options:
                    # Skip very rare codons (<10% relative frequency) unless
                    # it's the only option
                    if freq < 0.10 and len(codon_options) > 1:
                        # Still consider if it avoids a forbidden pattern
                        # that the preferred codon would introduce
                        test_seq = "".join(candidate.codons) + codon
                        if not _contains_pattern(test_seq[-20:], self.avoid_patterns):
                            # Only skip if the preferred codons also avoid patterns
                            preferred_avoids = False
                            for pref_codon, pref_freq in codon_options:
                                if pref_freq >= 0.10:
                                    pref_test = "".join(candidate.codons) + pref_codon
                                    if not _contains_pattern(
                                        pref_test[-20:], self.avoid_patterns
                                    ):
                                        preferred_avoids = True
                                        break
                            if preferred_avoids:
                                continue

                    new_codons = candidate.codons + [codon]
                    new_seq = "".join(new_codons)

                    # Score components
                    # 1. Codon frequency
                    freq_score = freq

                    # 2. GC penalty on recent window
                    gc_window = new_seq[-30:] if len(new_seq) >= 30 else new_seq
                    gc_score = _gc_penalty(
                        gc_window, self.target_gc_min, self.target_gc_max
                    )

                    # 3. Pattern avoidance: check last 20bp for new patterns
                    pattern_score = 1.0
                    if self.avoid_patterns:
                        check_region = new_seq[-20:] if len(new_seq) >= 20 else new_seq
                        if _contains_pattern(check_region, self.avoid_patterns):
                            pattern_score = 0.01  # Heavy penalty

                    # 4. mRNA structure penalty (sliding window)
                    structure_score = 1.0
                    if len(new_seq) >= folding_window_size:
                        window = new_seq[-folding_window_size:]
                        structure_score = _simple_folding_penalty(window)

                    # Composite score (additive for beam search)
                    step_score = (
                        0.40 * freq_score
                        + 0.25 * gc_score
                        + 0.20 * pattern_score
                        + 0.15 * structure_score
                    )

                    total_score = candidate.score + step_score

                    next_beam.append(
                        _BeamCandidate(codons=new_codons, score=total_score)
                    )

            # Prune to beam width
            next_beam.sort(key=lambda c: c.score, reverse=True)
            beam = next_beam[:self.beam_width]

        if not beam:
            # Fallback: use most frequent codons
            return [
                self._sorted_codons[aa][0][0]
                for aa in protein
                if aa in self._sorted_codons
            ]

        return beam[0].codons
