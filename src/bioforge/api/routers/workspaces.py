from uuid import UUID

from fastapi import APIRouter, Depends, Query

from bioforge.api.deps import get_workspace_service
from bioforge.schemas.workspace import WorkspaceCreate, WorkspaceRead, WorkspaceUpdate
from bioforge.services.workspace import WorkspaceService

router = APIRouter()


@router.get("/", response_model=list[WorkspaceRead])
async def list_workspaces(
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    service: WorkspaceService = Depends(get_workspace_service),
):
    return await service.list(offset=offset, limit=limit)


@router.post("/", response_model=WorkspaceRead, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    service: WorkspaceService = Depends(get_workspace_service),
):
    return await service.create(body)


@router.get("/{workspace_id}", response_model=WorkspaceRead)
async def get_workspace(
    workspace_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
):
    return await service.get(workspace_id)


@router.patch("/{workspace_id}", response_model=WorkspaceRead)
async def update_workspace(
    workspace_id: UUID,
    body: WorkspaceUpdate,
    service: WorkspaceService = Depends(get_workspace_service),
):
    return await service.update(workspace_id, body)


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(
    workspace_id: UUID,
    service: WorkspaceService = Depends(get_workspace_service),
):
    await service.delete(workspace_id)
