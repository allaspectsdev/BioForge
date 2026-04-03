from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.core.exceptions import NotFoundError
from bioforge.models.project import Project
from bioforge.repositories.project import ProjectRepository
from bioforge.schemas.project import ProjectCreate, ProjectUpdate


class ProjectService:
    def __init__(self, session: AsyncSession):
        self.repo = ProjectRepository(session)

    async def get(self, id: UUID) -> Project:
        proj = await self.repo.get(id)
        if proj is None:
            raise NotFoundError("Project", str(id))
        return proj

    async def list_by_workspace(
        self, workspace_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[Project]:
        return await self.repo.list_by_workspace(workspace_id, offset=offset, limit=limit)

    async def create(self, data: ProjectCreate) -> Project:
        return await self.repo.create(
            workspace_id=data.workspace_id,
            name=data.name,
            description=data.description,
            metadata_=data.metadata,
        )

    async def update(self, id: UUID, data: ProjectUpdate) -> Project:
        updates = data.model_dump(exclude_unset=True)
        if "metadata" in updates:
            updates["metadata_"] = updates.pop("metadata")
        proj = await self.repo.update(id, **updates)
        if proj is None:
            raise NotFoundError("Project", str(id))
        return proj

    async def delete(self, id: UUID) -> None:
        if not await self.repo.delete(id):
            raise NotFoundError("Project", str(id))
