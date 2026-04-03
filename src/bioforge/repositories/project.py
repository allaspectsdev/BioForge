from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.project import Project
from bioforge.repositories.base import BaseRepository


class ProjectRepository(BaseRepository[Project]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Project)

    async def list_by_workspace(
        self, workspace_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[Project]:
        stmt = (
            select(Project)
            .where(Project.workspace_id == workspace_id)
            .order_by(Project.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
