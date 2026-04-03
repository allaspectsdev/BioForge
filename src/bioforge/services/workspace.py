from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.core.exceptions import NotFoundError
from bioforge.models.workspace import Workspace
from bioforge.repositories.workspace import WorkspaceRepository
from bioforge.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceService:
    def __init__(self, session: AsyncSession):
        self.repo = WorkspaceRepository(session)

    async def get(self, id: UUID) -> Workspace:
        ws = await self.repo.get(id)
        if ws is None:
            raise NotFoundError("Workspace", str(id))
        return ws

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[Workspace]:
        return await self.repo.list(offset=offset, limit=limit)

    async def create(self, data: WorkspaceCreate) -> Workspace:
        return await self.repo.create(
            name=data.name,
            description=data.description,
            settings=data.settings,
        )

    async def update(self, id: UUID, data: WorkspaceUpdate) -> Workspace:
        updates = data.model_dump(exclude_unset=True)
        ws = await self.repo.update(id, **updates)
        if ws is None:
            raise NotFoundError("Workspace", str(id))
        return ws

    async def delete(self, id: UUID) -> None:
        if not await self.repo.delete(id):
            raise NotFoundError("Workspace", str(id))
