"""Search router: similarity search (pgvector) and BLAST search endpoints."""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.api.deps import get_session
from bioforge.modules.evo2.client import create_evo2_client
from bioforge.modules.evo2.embeddings import EmbeddingService
from bioforge.modules.evo2.schemas import SimilaritySearchRequest, SimilaritySearchResult

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# BLAST schemas (stub)
# ---------------------------------------------------------------------------


class BlastSearchRequest(BaseModel):
    """Request to run a BLAST search."""

    query: str = Field(..., description="Nucleotide or protein query sequence")
    db_name: str = Field(
        default="nt",
        description="BLAST database name (e.g. 'nt', 'nr', or a custom project DB)",
    )
    e_value: float = Field(
        default=1e-5,
        ge=0,
        description="E-value threshold",
    )
    max_hits: int = Field(default=50, ge=1, le=500, description="Maximum hits to return")


class BlastHit(BaseModel):
    """A single BLAST alignment hit."""

    subject_id: str
    subject_name: str
    identity: float = Field(..., description="Percent identity (0-100)")
    alignment_length: int
    e_value: float
    bit_score: float
    query_start: int
    query_end: int
    subject_start: int
    subject_end: int


class BlastResult(BaseModel):
    """Result of a BLAST search."""

    query_length: int
    db_name: str
    num_hits: int
    hits: list[BlastHit] = Field(default_factory=list)
    message: str | None = None


# ---------------------------------------------------------------------------
# Similarity search endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/similar",
    response_model=list[SimilaritySearchResult],
    summary="Find similar sequences via Evo 2 embeddings + pgvector",
)
async def search_similar(
    body: SimilaritySearchRequest,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    """Compute the Evo 2 embedding for the query sequence and find the top-K
    most similar sequences in the specified project using pgvector cosine
    distance.

    Returns a ranked list of matches with similarity scores.
    """
    client = create_evo2_client(mode="auto")
    embedding_service = EmbeddingService(client)

    query_embedding = await client.embed(body.query_sequence)
    hits = await embedding_service.similarity_search(
        query_embedding,
        body.project_id,
        body.top_k,
        session,
    )
    return hits


# ---------------------------------------------------------------------------
# BLAST search endpoint (stub)
# ---------------------------------------------------------------------------


@router.post(
    "/blast",
    response_model=BlastResult,
    summary="Run a BLAST search (stub)",
)
async def search_blast(body: BlastSearchRequest) -> BlastResult:
    """Run a BLAST search against the specified database.

    .. note::

       This is a **stub implementation** that returns empty results.
       Full BLAST+ integration is planned for a future release.

    TODO:
        - Install BLAST+ command-line tools in the container image.
        - Build project-specific BLAST databases from stored sequences via
          ``makeblastdb``.
        - Shell out to ``blastn`` / ``blastp`` / ``blastx`` and parse the XML
          or tabular output.
        - Stream results for large queries.
    """
    logger.info(
        "BLAST search stub called: query_len=%d db=%s e_value=%s",
        len(body.query),
        body.db_name,
        body.e_value,
    )

    return BlastResult(
        query_length=len(body.query),
        db_name=body.db_name,
        num_hits=0,
        hits=[],
        message=(
            "BLAST+ integration is not yet implemented. "
            "This endpoint will be functional once BLAST+ is installed and configured."
        ),
    )
