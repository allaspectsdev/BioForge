"""Pydantic request / response schemas for the Evo 2 module."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Embedding
# ---------------------------------------------------------------------------


class EmbedRequest(BaseModel):
    """Request to embed a nucleotide sequence via Evo 2."""

    sequence: str = Field(..., description="Nucleotide sequence (ATCGN)")
    sequence_id: UUID | None = Field(
        default=None,
        description="Optional sequence UUID; when provided the embedding is stored in the database.",
    )


class EmbedResult(BaseModel):
    """Result of an embedding operation."""

    sequence_id: UUID | None = None
    embedding: list[float] = Field(..., description="1536-dimensional embedding vector")
    dimension: int = Field(default=1536, description="Dimensionality of the embedding")


# ---------------------------------------------------------------------------
# Variant scoring
# ---------------------------------------------------------------------------


class MutationSpec(BaseModel):
    """A single nucleotide mutation."""

    position: int = Field(..., ge=0, description="0-based position in the sequence")
    ref_base: str = Field(..., min_length=1, max_length=1, description="Reference base at position")
    alt_base: str = Field(..., min_length=1, max_length=1, description="Alternate (mutant) base")


class VariantScanRequest(BaseModel):
    """Request to scan variant effects over a region of a sequence."""

    sequence: str = Field(..., description="Reference nucleotide sequence")
    region_start: int = Field(default=0, ge=0, description="Start of region to scan (inclusive)")
    region_end: int | None = Field(
        default=None,
        description="End of region to scan (exclusive). Defaults to full sequence length.",
    )


class VariantScore(BaseModel):
    """Score for a single variant."""

    position: int
    ref_base: str
    alt_base: str
    score: float = Field(..., description="Delta log-likelihood score")
    interpretation: str = Field(
        ...,
        description="One of: deleterious, neutral, beneficial",
    )


class VariantScanResult(BaseModel):
    """Results of a variant scan sorted by predicted effect."""

    sequence_length: int
    region_start: int
    region_end: int
    num_variants_scored: int
    variants: list[VariantScore] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Similarity search
# ---------------------------------------------------------------------------


class SimilaritySearchRequest(BaseModel):
    """Request to find sequences similar to a query."""

    query_sequence: str = Field(..., description="Nucleotide query sequence")
    project_id: UUID = Field(..., description="Scope search to this project")
    top_k: int = Field(default=10, ge=1, le=100, description="Number of results to return")


class SimilaritySearchResult(BaseModel):
    """A single similarity search hit."""

    sequence_id: UUID
    name: str
    distance: float = Field(..., description="Cosine distance (lower = more similar)")
    score: float = Field(..., description="Similarity score in [0, 1]")


# ---------------------------------------------------------------------------
# Sequence generation
# ---------------------------------------------------------------------------


class SequenceGenerateRequest(BaseModel):
    """Request to generate a nucleotide continuation."""

    prompt_sequence: str = Field(..., description="Seed / prompt nucleotide sequence")
    max_length: int = Field(default=100, ge=1, le=10000, description="Maximum bases to generate")


class SequenceGenerateResult(BaseModel):
    """Result of sequence generation."""

    prompt_length: int
    generated_sequence: str
    generated_length: int
    full_sequence: str = Field(..., description="Prompt + generated concatenation")
