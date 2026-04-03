from uuid import UUID

from fastapi import APIRouter, Depends, Query

from bioforge.api.deps import get_result_service
from bioforge.schemas.result import ResultRead
from bioforge.services.result import ResultService

router = APIRouter()


@router.get("/", response_model=list[ResultRead])
async def list_results(
    project_id: UUID,
    result_type: str | None = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: ResultService = Depends(get_result_service),
):
    return await service.list_by_project(
        project_id, result_type=result_type, offset=offset, limit=limit
    )


@router.get("/{result_id}", response_model=ResultRead)
async def get_result(
    result_id: UUID,
    service: ResultService = Depends(get_result_service),
):
    return await service.get(result_id)
