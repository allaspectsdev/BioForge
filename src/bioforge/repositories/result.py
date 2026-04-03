from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.result import Result
from bioforge.repositories.base import BaseRepository


class ResultRepository(BaseRepository[Result]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Result)

    async def list_by_project(
        self, project_id: UUID, *, result_type: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[Result]:
        stmt = (
            select(Result)
            .where(Result.project_id == project_id)
            .order_by(Result.created_at.desc())
        )
        if result_type:
            stmt = stmt.where(Result.result_type == result_type)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
