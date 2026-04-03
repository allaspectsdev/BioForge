from uuid import UUID

from fastapi import APIRouter, Depends, Query

from bioforge.api.deps import get_pipeline_service
from bioforge.schemas.pipeline import (
    PipelineCreate,
    PipelineRead,
    PipelineRunCreate,
    PipelineRunRead,
)
from bioforge.services.pipeline import PipelineService

router = APIRouter()


@router.get("/", response_model=list[PipelineRead])
async def list_pipelines(
    project_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: PipelineService = Depends(get_pipeline_service),
):
    return await service.list_definitions(project_id, offset=offset, limit=limit)


@router.post("/", response_model=PipelineRead, status_code=201)
async def create_pipeline(
    body: PipelineCreate,
    service: PipelineService = Depends(get_pipeline_service),
):
    return await service.create_definition(body)


# Static prefix routes MUST come before dynamic /{pipeline_id} routes
@router.get("/runs/{run_id}", response_model=PipelineRunRead)
async def get_run(
    run_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
):
    return await service.get_run(run_id)


@router.get("/{pipeline_id}", response_model=PipelineRead)
async def get_pipeline(
    pipeline_id: UUID,
    service: PipelineService = Depends(get_pipeline_service),
):
    return await service.get_definition(pipeline_id)


@router.post("/{pipeline_id}/run", response_model=PipelineRunRead, status_code=201)
async def run_pipeline(
    pipeline_id: UUID,
    body: PipelineRunCreate,
    service: PipelineService = Depends(get_pipeline_service),
):
    return await service.create_run(pipeline_id, body)


@router.get("/{pipeline_id}/runs", response_model=list[PipelineRunRead])
async def list_runs(
    pipeline_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: PipelineService = Depends(get_pipeline_service),
):
    return await service.list_runs(pipeline_id, offset=offset, limit=limit)
