"""Schemas for the alignment module."""

from pydantic import BaseModel, Field


class BlastSearchRequest(BaseModel):
    """Request to perform a BLAST search."""

    query_sequence: str = Field(description="Nucleotide or protein query sequence")
    database: str = Field(
        default="nr",
        description="BLAST database name (nr, nt, swissprot, pdb, etc.)",
    )
    program: str = Field(
        default="blastn",
        description="BLAST program (blastn, blastp, blastx, tblastn, tblastx)",
    )
    evalue_threshold: float = Field(
        default=1e-5,
        description="E-value threshold for reporting hits",
    )
    max_hits: int = Field(
        default=10,
        ge=1,
        le=500,
        description="Maximum number of hits to return",
    )


class BlastHSP(BaseModel):
    """High-Scoring Segment Pair from a BLAST search."""

    query_start: int
    query_end: int
    subject_start: int
    subject_end: int
    identity_pct: float = Field(description="Percent identity (0-100)")
    e_value: float
    bit_score: float
    alignment_length: int
    gaps: int = 0
    query_aligned: str = ""
    subject_aligned: str = ""


class BlastHit(BaseModel):
    """A single BLAST hit with one or more HSPs."""

    subject_id: str
    subject_description: str = ""
    subject_length: int = 0
    hsps: list[BlastHSP] = Field(default_factory=list)
    best_evalue: float = 0.0
    best_identity_pct: float = 0.0


class BlastResult(BaseModel):
    """Complete result of a BLAST search."""

    program: str
    database: str
    query_length: int
    hits: list[BlastHit] = Field(default_factory=list)
    total_hits: int = 0
    search_time_s: float = 0.0


class AlignmentRequest(BaseModel):
    """Request to perform pairwise or multiple alignment."""

    sequences: list[str] = Field(
        description="List of sequences to align (2 for pairwise, 3+ for multiple)",
        min_length=2,
    )
    names: list[str] = Field(
        default_factory=list,
        description="Optional names for each sequence",
    )
    alignment_type: str = Field(
        default="global",
        description="Alignment type: global (Needleman-Wunsch) or local (Smith-Waterman)",
    )
    gap_open_penalty: float = Field(default=-10.0, description="Gap opening penalty")
    gap_extend_penalty: float = Field(default=-0.5, description="Gap extension penalty")
    match_score: float = Field(default=2.0, description="Score for matching bases")
    mismatch_penalty: float = Field(default=-1.0, description="Penalty for mismatches")


class AlignedSequence(BaseModel):
    """A single aligned sequence with gaps inserted."""

    name: str
    aligned_sequence: str
    original_length: int


class AlignmentResult(BaseModel):
    """Result of a pairwise or multiple alignment."""

    aligned_sequences: list[AlignedSequence]
    alignment_length: int
    identity_pct: float = Field(description="Percent identity across the alignment")
    gap_count: int
    score: float
    method: str = Field(description="Algorithm used (e.g., Needleman-Wunsch)")
