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


def _interpret_score(score: float) -> str:
    """Map a delta log-likelihood score to a human-readable interpretation."""
    if score <= _DELETERIOUS_THRESHOLD:
        return "deleterious"
    if score >= _BENEFICIAL_THRESHOLD:
        return "beneficial"
    return "neutral"


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
            }

        scores = await self._client.score_variants(
            sequence,
            [(position, ref_base, alt_base)],
        )
        score = scores[0]

        return {
            "position": position,
            "ref_base": ref_base,
            "alt_base": alt_base,
            "score": round(score, 6),
            "interpretation": _interpret_score(score),
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
            results.append(
                {
                    "position": pos,
                    "ref_base": ref,
                    "alt_base": alt,
                    "score": round(score, 6),
                    "interpretation": _interpret_score(score),
                }
            )

        # Sort by score ascending (most deleterious first)
        results.sort(key=lambda r: r["score"])
        return results
