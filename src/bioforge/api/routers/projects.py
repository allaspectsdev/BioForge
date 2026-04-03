from uuid import UUID

from fastapi import APIRouter, Depends, Query

from bioforge.api.deps import get_project_service
from bioforge.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate
from bioforge.services.project import ProjectService

router = APIRouter()


@router.get("/", response_model=list[ProjectRead])
async def list_projects(
    workspace_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: ProjectService = Depends(get_project_service),
):
    return await service.list_by_workspace(workspace_id, offset=offset, limit=limit)


@router.post("/", response_model=ProjectRead, status_code=201)
async def create_project(
    body: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
):
    return await service.create(body)


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
):
    return await service.get(project_id)


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: UUID,
    body: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
):
    return await service.update(project_id, body)


@router.delete("/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    service: ProjectService = Depends(get_project_service),
):
    await service.delete(project_id)
