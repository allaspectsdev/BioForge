from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.core.exceptions import NotFoundError
from bioforge.models.result import Result
from bioforge.repositories.result import ResultRepository


class ResultService:
    def __init__(self, session: AsyncSession):
        self.repo = ResultRepository(session)

    async def get(self, id: UUID) -> Result:
        result = await self.repo.get(id)
        if result is None:
            raise NotFoundError("Result", str(id))
        return result

    async def list_by_project(
        self, project_id: UUID, *, result_type: str | None = None, offset: int = 0, limit: int = 100
    ) -> list[Result]:
        return await self.repo.list_by_project(
            project_id, result_type=result_type, offset=offset, limit=limit
        )
