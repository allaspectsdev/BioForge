import io
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.core.exceptions import NotFoundError, ValidationError
from bioforge.models.sequence import Sequence
from bioforge.repositories.sequence import SequenceRepository
from bioforge.schemas.sequence import (
    SequenceCreate,
    SequenceImport,
    SequenceUpdate,
    compute_checksum,
    compute_gc_content,
)


class SequenceService:
    def __init__(self, session: AsyncSession):
        self.repo = SequenceRepository(session)

    async def get(self, id: UUID) -> Sequence:
        seq = await self.repo.get(id)
        if seq is None:
            raise NotFoundError("Sequence", str(id))
        return seq

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        sequence_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Sequence]:
        return await self.repo.list_by_project(
            project_id, sequence_type=sequence_type, offset=offset, limit=limit
        )

    async def create(self, data: SequenceCreate) -> Sequence:
        seq_data = data.sequence_data.upper().strip()
        gc = compute_gc_content(seq_data) if data.sequence_type in ("dna", "rna") else None

        return await self.repo.create(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            sequence_type=data.sequence_type,
            sequence_data=seq_data,
            length=len(seq_data),
            gc_content=gc,
            annotations=data.annotations,
            source_format=data.source_format,
            checksum=compute_checksum(seq_data),
        )

    async def update(self, id: UUID, data: SequenceUpdate) -> Sequence:
        updates = data.model_dump(exclude_unset=True)
        seq = await self.repo.update(id, **updates)
        if seq is None:
            raise NotFoundError("Sequence", str(id))
        return seq

    async def delete(self, id: UUID) -> None:
        if not await self.repo.delete(id):
            raise NotFoundError("Sequence", str(id))

    async def import_fasta(self, project_id: UUID, content: str) -> list[Sequence]:
        from Bio import SeqIO

        sequences = []
        for record in SeqIO.parse(io.StringIO(content), "fasta"):
            seq_data = str(record.seq).upper()
            seq_type = self._detect_sequence_type(seq_data)
            gc = compute_gc_content(seq_data) if seq_type in ("dna", "rna") else None

            seq = await self.repo.create(
                project_id=project_id,
                name=record.id,
                description=record.description,
                sequence_type=seq_type,
                sequence_data=seq_data,
                length=len(seq_data),
                gc_content=gc,
                annotations=[],
                source_format="fasta",
                checksum=compute_checksum(seq_data),
            )
            sequences.append(seq)
        return sequences

    async def import_genbank(self, project_id: UUID, content: str) -> list[Sequence]:
        from Bio import SeqIO

        sequences = []
        for record in SeqIO.parse(io.StringIO(content), "genbank"):
            seq_data = str(record.seq).upper()
            seq_type = self._detect_sequence_type(seq_data)
            gc = compute_gc_content(seq_data) if seq_type in ("dna", "rna") else None

            annotations = []
            for feature in record.features:
                annotations.append({
                    "type": feature.type,
                    "start": int(feature.location.start),
                    "end": int(feature.location.end),
                    "strand": feature.location.strand,
                    "qualifiers": {k: v for k, v in feature.qualifiers.items()},
                })

            seq = await self.repo.create(
                project_id=project_id,
                name=record.name,
                description=record.description,
                sequence_type=seq_type,
                sequence_data=seq_data,
                length=len(seq_data),
                gc_content=gc,
                annotations=annotations,
                source_format="genbank",
                checksum=compute_checksum(seq_data),
            )
            sequences.append(seq)
        return sequences

    async def import_sequences(self, data: SequenceImport) -> list[Sequence]:
        if data.format == "fasta":
            return await self.import_fasta(data.project_id, data.content)
        elif data.format == "genbank":
            return await self.import_genbank(data.project_id, data.content)
        raise ValidationError(f"Unsupported format: {data.format}")

    @staticmethod
    def _detect_sequence_type(seq: str) -> str:
        bases = set(seq.upper())
        if bases <= {"A", "T", "G", "C", "N"}:
            return "dna"
        elif bases <= {"A", "U", "G", "C", "N"}:
            return "rna"
        return "protein"
