"""Variant effect prediction powered by Evo 2 delta log-likelihoods."""

from __future__ import annotations

import logging
from typing import Any

from bioforge.modules.evo2.client import BaseEvo2Client

logger = logging.getLogger(__name__)

BASES = ["A", "T", "C", "G"]

# Interpretation thresholds (delta log-likelihood)
_DELETERIOUS_THRESHOLD = -0.5
_BENEFICIAL_THRESHOLD = 0.5

# Confidence regime thresholds
_NEAR_THRESHOLD_MARGIN = 0.15  # score within this of a threshold boundary
_SHORT_CONTEXT_BP = 50  # sequences shorter than this lose model context
_EXTREME_GC_LOW = 0.25
_EXTREME_GC_HIGH = 0.75


def _interpret_score(score: float) -> str:
    """Map a delta log-likelihood score to a human-readable interpretation."""
    if score <= _DELETERIOUS_THRESHOLD:
        return "deleterious"
    if score >= _BENEFICIAL_THRESHOLD:
        return "beneficial"
    return "neutral"


def _compute_gc_content(sequence: str) -> float:
    """Compute GC content of a sequence."""
    if not sequence:
        return 0.0
    upper = sequence.upper()
    gc = sum(1 for b in upper if b in ("G", "C"))
    return gc / len(upper)


def _assess_confidence(
    score: float,
    sequence: str,
    position: int,
) -> tuple[float, list[str]]:
    """Assess confidence of a variant prediction.

    Returns (confidence, list_of_flags) where confidence is in [0, 1].
    Flags explain why confidence was reduced.
    """
    confidence = 1.0
    flags: list[str] = []

    # Near-threshold: score is close to deleterious/beneficial boundary
    dist_to_del = abs(score - _DELETERIOUS_THRESHOLD)
    dist_to_ben = abs(score - _BENEFICIAL_THRESHOLD)
    if dist_to_del < _NEAR_THRESHOLD_MARGIN or dist_to_ben < _NEAR_THRESHOLD_MARGIN:
        confidence -= 0.3
        flags.append("near_threshold")

    # Short context: less sequence for the model to work with
    if len(sequence) < _SHORT_CONTEXT_BP:
        confidence -= 0.3
        flags.append("short_context")

    # Position near edge: model has less context on one side
    edge_dist = min(position, len(sequence) - 1 - position)
    if edge_dist < 10:
        confidence -= 0.15
        flags.append("near_sequence_edge")

    # Extreme GC content in local window
    window_start = max(0, position - 25)
    window_end = min(len(sequence), position + 25)
    local_gc = _compute_gc_content(sequence[window_start:window_end])
    if local_gc < _EXTREME_GC_LOW or local_gc > _EXTREME_GC_HIGH:
        confidence -= 0.15
        flags.append("extreme_gc")

    return max(0.05, round(confidence, 2)), flags


class VariantEffectPredictor:
    """Score the functional impact of single-nucleotide variants using Evo 2.

    Parameters
    ----------
    client : BaseEvo2Client
        An Evo 2 client instance.
    """

    def __init__(self, client: BaseEvo2Client) -> None:
        self._client = client

    async def score_mutation(
        self,
        sequence: str,
        position: int,
        alt_base: str,
    ) -> dict[str, Any]:
        """Score a single mutation and return a result dict.

        Parameters
        ----------
        sequence : str
            The reference nucleotide sequence.
        position : int
            0-based position of the mutation.
        alt_base : str
            The alternate base to introduce.

        Returns
        -------
        dict
            Keys: ``position``, ``ref_base``, ``alt_base``, ``score``,
            ``interpretation``.
        """
        if position < 0 or position >= len(sequence):
            raise ValueError(
                f"Position {position} is out of range for sequence of length {len(sequence)}"
            )

        ref_base = sequence[position].upper()
        alt_base = alt_base.upper()

        if ref_base == alt_base:
            return {
                "position": position,
                "ref_base": ref_base,
                "alt_base": alt_base,
                "score": 0.0,
                "interpretation": "neutral",
                "confidence": 1.0,
                "confidence_flags": [],
            }

        scores = await self._client.score_variants(
            sequence,
            [(position, ref_base, alt_base)],
        )
        score = scores[0]
        confidence, flags = _assess_confidence(score, sequence, position)

        return {
            "position": position,
            "ref_base": ref_base,
            "alt_base": alt_base,
            "score": round(score, 6),
            "interpretation": _interpret_score(score),
            "confidence": confidence,
            "confidence_flags": flags,
        }

    async def scan_variants(
        self,
        sequence: str,
        region_start: int,
        region_end: int,
    ) -> list[dict[str, Any]]:
        """Scan all single-nucleotide variants in *[region_start, region_end)*.

        For every position in the region and every possible alternate base,
        a delta log-likelihood score is computed.  Results are sorted from
        most deleterious (most negative) to most beneficial.

        Parameters
        ----------
        sequence : str
            Reference nucleotide sequence.
        region_start : int
            Start of the scan region (inclusive, 0-based).
        region_end : int
            End of the scan region (exclusive).

        Returns
        -------
        list[dict]
            Sorted list of variant score dicts.
        """
        if region_start < 0:
            region_start = 0
        if region_end > len(sequence):
            region_end = len(sequence)
        if region_start >= region_end:
            raise ValueError(
                f"Invalid region [{region_start}, {region_end}): "
                "start must be less than end and within sequence bounds."
            )

        # Build all mutations for the region
        mutations: list[tuple[int, str, str]] = []
        for pos in range(region_start, region_end):
            ref = sequence[pos].upper()
            for alt in BASES:
                if alt != ref:
                    mutations.append((pos, ref, alt))

        if not mutations:
            return []

        # Score them in a single batch call
        scores = await self._client.score_variants(sequence, mutations)

        results: list[dict[str, Any]] = []
        for (pos, ref, alt), score in zip(mutations, scores):
            confidence, flags = _assess_confidence(score, sequence, pos)
            results.append(
                {
                    "position": pos,
                    "ref_base": ref,
                    "alt_base": alt,
                    "score": round(score, 6),
                    "interpretation": _interpret_score(score),
                    "confidence": confidence,
                    "confidence_flags": flags,
                }
            )

        # Sort by score ascending (most deleterious first)
        results.sort(key=lambda r: r["score"])
        return results
