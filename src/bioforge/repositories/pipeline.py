from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.pipeline import PipelineDefinition, PipelineRun
from bioforge.repositories.base import BaseRepository


class PipelineDefinitionRepository(BaseRepository[PipelineDefinition]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PipelineDefinition)

    async def list_by_project(
        self, project_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[PipelineDefinition]:
        stmt = (
            select(PipelineDefinition)
            .where(PipelineDefinition.project_id == project_id)
            .order_by(PipelineDefinition.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class PipelineRunRepository(BaseRepository[PipelineRun]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, PipelineRun)

    async def list_by_definition(
        self, definition_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[PipelineRun]:
        stmt = (
            select(PipelineRun)
            .where(PipelineRun.definition_id == definition_id)
            .order_by(PipelineRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
