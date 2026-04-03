"""Alignment module: BLAST search, pairwise alignment, and multiple alignment."""

from __future__ import annotations

import logging
from typing import Any

from bioforge.modules.alignment.blast_runner import MockBlastRunner
from bioforge.modules.alignment.schemas import (
    AlignedSequence,
    AlignmentRequest,
    AlignmentResult,
    BlastResult,
    BlastSearchRequest,
)
from bioforge.modules.base import (
    BioForgeModule,
    ModuleCapability,
    ModuleInfo,
    ModulePipelineStep,
)

logger = logging.getLogger(__name__)


def _needleman_wunsch(
    seq1: str,
    seq2: str,
    match: float = 2.0,
    mismatch: float = -1.0,
    gap_open: float = -10.0,
    gap_extend: float = -0.5,
) -> tuple[str, str, float]:
    """Simple Needleman-Wunsch global alignment for short sequences.

    Uses affine gap penalties. For sequences longer than ~5000 bp,
    an external aligner should be used instead.
    """
    n, m = len(seq1), len(seq2)
    # Score matrices: M (match/mismatch), X (gap in seq2), Y (gap in seq1)
    NEG_INF = float("-inf")

    M = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    X = [[NEG_INF] * (m + 1) for _ in range(n + 1)]
    Y = [[NEG_INF] * (m + 1) for _ in range(n + 1)]

    M[0][0] = 0.0
    for i in range(1, n + 1):
        X[i][0] = gap_open + gap_extend * (i - 1)
    for j in range(1, m + 1):
        Y[0][j] = gap_open + gap_extend * (j - 1)

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = match if seq1[i - 1].upper() == seq2[j - 1].upper() else mismatch

            M[i][j] = s + max(
                M[i - 1][j - 1],
                X[i - 1][j - 1],
                Y[i - 1][j - 1],
            )
            X[i][j] = max(
                M[i - 1][j] + gap_open,
                X[i - 1][j] + gap_extend,
            )
            Y[i][j] = max(
                M[i][j - 1] + gap_open,
                Y[i][j - 1] + gap_extend,
            )

    # Traceback
    best_score = max(M[n][m], X[n][m], Y[n][m])
    aligned1: list[str] = []
    aligned2: list[str] = []
    i, j = n, m

    # Determine which matrix we end in
    if M[n][m] >= X[n][m] and M[n][m] >= Y[n][m]:
        state = "M"
    elif X[n][m] >= Y[n][m]:
        state = "X"
    else:
        state = "Y"

    while i > 0 or j > 0:
        if state == "M" and i > 0 and j > 0:
            aligned1.append(seq1[i - 1])
            aligned2.append(seq2[j - 1])
            s = match if seq1[i - 1].upper() == seq2[j - 1].upper() else mismatch
            prev_score = M[i][j] - s
            if i > 0 and j > 0 and abs(M[i - 1][j - 1] - prev_score) < 1e-6:
                state = "M"
            elif i > 0 and j > 0 and abs(X[i - 1][j - 1] - prev_score) < 1e-6:
                state = "X"
            else:
                state = "Y"
            i -= 1
            j -= 1
        elif state == "X" and i > 0:
            aligned1.append(seq1[i - 1])
            aligned2.append("-")
            if abs(X[i - 1][j] + gap_extend - X[i][j]) < 1e-6:
                state = "X"
            else:
                state = "M"
            i -= 1
        elif j > 0:
            aligned1.append("-")
            aligned2.append(seq2[j - 1])
            if abs(Y[i][j - 1] + gap_extend - Y[i][j]) < 1e-6:
                state = "Y"
            else:
                state = "M"
            j -= 1
        else:
            break

    return "".join(reversed(aligned1)), "".join(reversed(aligned2)), best_score


class AlignmentModule(BioForgeModule):
    """Alignment module providing BLAST search, pairwise, and multiple alignment.

    Uses a MockBlastRunner by default. Set use_real_blast=True and ensure
    BLAST+ is installed for production searches.
    """

    def __init__(self, use_real_blast: bool = False) -> None:
        self._use_real_blast = use_real_blast
        if use_real_blast:
            from bioforge.modules.alignment.blast_runner import BlastRunner
            self._blast_runner = BlastRunner()
        else:
            self._blast_runner = MockBlastRunner()

    def info(self) -> ModuleInfo:
        return ModuleInfo(
            name="alignment",
            version="0.1.0",
            description="Sequence alignment and BLAST search (pairwise, multiple alignment, BLAST+)",
            author="BioForge",
            tags=["alignment", "blast", "needleman-wunsch", "sequence", "search"],
        )

    def capabilities(self) -> list[ModuleCapability]:
        return [
            ModuleCapability(
                name="blast_search",
                description=(
                    "Run a BLAST search against a database. Returns hits with HSP details "
                    "including identity percentage, e-value, bit score, and alignment coordinates."
                ),
                input_schema=BlastSearchRequest.model_json_schema(),
                output_schema=BlastResult.model_json_schema(),
                handler=self._blast_search,
            ),
            ModuleCapability(
                name="pairwise_align",
                description=(
                    "Perform pairwise sequence alignment (Needleman-Wunsch global alignment). "
                    "For short sequences (<5000 bp) uses a built-in implementation; for longer "
                    "sequences, an external aligner is recommended."
                ),
                input_schema=AlignmentRequest.model_json_schema(),
                output_schema=AlignmentResult.model_json_schema(),
                handler=self._pairwise_align,
            ),
            ModuleCapability(
                name="multiple_align",
                description=(
                    "Perform multiple sequence alignment. Currently returns input sequences "
                    "as-is (stub). Full MUSCLE/MAFFT integration planned."
                ),
                input_schema=AlignmentRequest.model_json_schema(),
                output_schema=AlignmentResult.model_json_schema(),
                handler=self._multiple_align,
            ),
        ]

    def pipeline_steps(self) -> list[ModulePipelineStep]:
        return [
            ModulePipelineStep(
                step_type="alignment.blast",
                description="Run BLAST search on a query sequence",
                input_ports={"query_sequence": "str", "database": "str"},
                output_ports={"result": "BlastResult"},
                handler=self._blast_search_step,
            ),
            ModulePipelineStep(
                step_type="alignment.pairwise",
                description="Align two sequences using Needleman-Wunsch",
                input_ports={"sequences": "list[str]"},
                output_ports={"result": "AlignmentResult"},
                handler=self._pairwise_align_step,
            ),
        ]

    def mcp_tools(self) -> list:
        return [self._blast_search, self._pairwise_align, self._multiple_align]

    # ------------------------------------------------------------------
    # Capability handlers
    # ------------------------------------------------------------------

    async def _blast_search(self, request: dict) -> dict:
        """Handle BLAST search capability invocation."""
        req = BlastSearchRequest(**request)
        result = await self._blast_runner.search(req)
        return result.model_dump()

    async def _pairwise_align(self, request: dict) -> dict:
        """Handle pairwise alignment capability invocation."""
        req = AlignmentRequest(**request)
        sequences = req.sequences
        if len(sequences) < 2:
            return {"error": "At least 2 sequences required for pairwise alignment"}

        seq1, seq2 = sequences[0], sequences[1]
        names = req.names if req.names and len(req.names) >= 2 else ["seq1", "seq2"]

        # For very long sequences, warn but still try
        max_builtin_len = 5000
        if len(seq1) > max_builtin_len or len(seq2) > max_builtin_len:
            logger.warning(
                "Sequences are long (%d, %d bp). Built-in NW may be slow. "
                "Consider using an external aligner.",
                len(seq1),
                len(seq2),
            )

        aligned1, aligned2, score = _needleman_wunsch(
            seq1,
            seq2,
            match=req.match_score,
            mismatch=req.mismatch_penalty,
            gap_open=req.gap_open_penalty,
            gap_extend=req.gap_extend_penalty,
        )

        # Calculate statistics
        alignment_length = len(aligned1)
        matches = sum(
            1
            for a, b in zip(aligned1, aligned2)
            if a == b and a != "-"
        )
        gap_count = aligned1.count("-") + aligned2.count("-")
        identity_pct = round(matches / max(alignment_length, 1) * 100, 1)

        result = AlignmentResult(
            aligned_sequences=[
                AlignedSequence(
                    name=names[0],
                    aligned_sequence=aligned1,
                    original_length=len(seq1),
                ),
                AlignedSequence(
                    name=names[1],
                    aligned_sequence=aligned2,
                    original_length=len(seq2),
                ),
            ],
            alignment_length=alignment_length,
            identity_pct=identity_pct,
            gap_count=gap_count,
            score=score,
            method="Needleman-Wunsch (global, affine gaps)",
        )
        return result.model_dump()

    async def _multiple_align(self, request: dict) -> dict:
        """Handle multiple sequence alignment (stub).

        TODO: Integrate MUSCLE or MAFFT for true MSA.
        Currently returns input sequences as-is with identity metrics.
        """
        req = AlignmentRequest(**request)
        sequences = req.sequences
        names = req.names if req.names and len(req.names) == len(sequences) else [
            f"seq{i+1}" for i in range(len(sequences))
        ]

        # Stub: pad sequences to equal length with trailing gaps
        max_len = max(len(s) for s in sequences)
        aligned = [
            AlignedSequence(
                name=names[i],
                aligned_sequence=seq + "-" * (max_len - len(seq)),
                original_length=len(seq),
            )
            for i, seq in enumerate(sequences)
        ]

        result = AlignmentResult(
            aligned_sequences=aligned,
            alignment_length=max_len,
            identity_pct=0.0,  # Not computed for stub
            gap_count=sum(max_len - len(s) for s in sequences),
            score=0.0,
            method="stub (sequences padded to equal length, no true alignment)",
        )
        return result.model_dump()

    # ------------------------------------------------------------------
    # Pipeline step handlers
    # ------------------------------------------------------------------

    async def _blast_search_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for BLAST search."""
        request = {
            "query_sequence": inputs["query_sequence"],
            "database": inputs.get("database", "nr"),
            **params,
        }
        result = await self._blast_search(request)
        return {"result": result}

    async def _pairwise_align_step(self, inputs: dict, params: dict) -> dict:
        """Pipeline step handler for pairwise alignment."""
        request = {"sequences": inputs["sequences"], **params}
        result = await self._pairwise_align(request)
        return {"result": result}
