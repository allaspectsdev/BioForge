"""Pydantic request / response schemas for the structure prediction module."""

from __future__ import annotations

from pydantic import BaseModel, Field


class StructurePredictionRequest(BaseModel):
    """Request to predict the 3-D structure of a single protein chain."""

    sequence: str = Field(
        ...,
        description="Amino-acid sequence in one-letter code",
    )


class PDBResultSchema(BaseModel):
    """Serialisable representation of a structure prediction result."""

    pdb_string: str = Field(..., description="PDB-format coordinate string")
    plddt_scores: list[float] = Field(
        default_factory=list,
        description="Per-residue pLDDT confidence scores (0-100)",
    )
    mean_plddt: float = Field(..., description="Mean pLDDT across all residues")
    num_residues: int = Field(..., description="Total number of residues in the prediction")


class ComplexPredictionRequest(BaseModel):
    """Request to predict the structure of a multi-chain protein complex."""

    sequences: list[str] = Field(
        ...,
        min_length=1,
        description="One amino-acid sequence per chain",
    )
