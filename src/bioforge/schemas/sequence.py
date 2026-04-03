import hashlib
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class SequenceCreate(BaseModel):
    project_id: UUID
    name: str = Field(max_length=255)
    description: str | None = None
    sequence_type: Literal["dna", "rna", "protein"]
    sequence_data: str
    annotations: list[dict] = Field(default_factory=list)
    source_format: str | None = None

    @field_validator("sequence_data")
    @classmethod
    def validate_sequence(cls, v: str, info) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("Sequence data cannot be empty")
        return v


class SequenceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    annotations: list[dict] | None = None


class SequenceRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    project_id: UUID
    name: str
    description: str | None
    sequence_type: str
    length: int
    gc_content: float | None
    annotations: list
    source_format: str | None
    checksum: str | None
    created_at: datetime
    updated_at: datetime


class SequenceImport(BaseModel):
    project_id: UUID
    format: Literal["fasta", "genbank"]
    content: str


class SequenceExport(BaseModel):
    format: Literal["fasta", "genbank"]


def compute_gc_content(sequence: str) -> float | None:
    seq = sequence.upper()
    gc = sum(1 for c in seq if c in ("G", "C"))
    total = sum(1 for c in seq if c in ("A", "T", "G", "C"))
    if total == 0:
        return None
    return gc / total


def compute_checksum(sequence: str) -> str:
    return hashlib.sha256(sequence.upper().encode()).hexdigest()
