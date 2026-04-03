from uuid import UUID

from fastapi import APIRouter, Depends, Query

from bioforge.api.deps import get_sequence_service
from bioforge.schemas.sequence import (
    SequenceCreate,
    SequenceImport,
    SequenceRead,
    SequenceUpdate,
)
from bioforge.services.sequence import SequenceService

router = APIRouter()


@router.get("/", response_model=list[SequenceRead])
async def list_sequences(
    project_id: UUID,
    sequence_type: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: SequenceService = Depends(get_sequence_service),
):
    return await service.list_by_project(
        project_id, sequence_type=sequence_type, offset=offset, limit=limit
    )


@router.post("/", response_model=SequenceRead, status_code=201)
async def create_sequence(
    body: SequenceCreate,
    service: SequenceService = Depends(get_sequence_service),
):
    return await service.create(body)


@router.post("/import", response_model=list[SequenceRead], status_code=201)
async def import_sequences(
    body: SequenceImport,
    service: SequenceService = Depends(get_sequence_service),
):
    return await service.import_sequences(body)


@router.get("/{sequence_id}", response_model=SequenceRead)
async def get_sequence(
    sequence_id: UUID,
    service: SequenceService = Depends(get_sequence_service),
):
    return await service.get(sequence_id)


@router.patch("/{sequence_id}", response_model=SequenceRead)
async def update_sequence(
    sequence_id: UUID,
    body: SequenceUpdate,
    service: SequenceService = Depends(get_sequence_service),
):
    return await service.update(sequence_id, body)


@router.delete("/{sequence_id}", status_code=204)
async def delete_sequence(
    sequence_id: UUID,
    service: SequenceService = Depends(get_sequence_service),
):
    await service.delete(sequence_id)
