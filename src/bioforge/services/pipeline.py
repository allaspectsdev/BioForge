from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.core.exceptions import NotFoundError
from bioforge.models.pipeline import PipelineDefinition, PipelineRun
from bioforge.repositories.pipeline import PipelineDefinitionRepository, PipelineRunRepository
from bioforge.schemas.pipeline import PipelineCreate, PipelineRunCreate


class PipelineService:
    def __init__(self, session: AsyncSession):
        self.def_repo = PipelineDefinitionRepository(session)
        self.run_repo = PipelineRunRepository(session)

    async def get_definition(self, id: UUID) -> PipelineDefinition:
        defn = await self.def_repo.get(id)
        if defn is None:
            raise NotFoundError("PipelineDefinition", str(id))
        return defn

    async def list_definitions(
        self, project_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[PipelineDefinition]:
        return await self.def_repo.list_by_project(project_id, offset=offset, limit=limit)

    async def create_definition(self, data: PipelineCreate) -> PipelineDefinition:
        definition = {
            "steps": [step.model_dump() for step in data.steps],
        }
        return await self.def_repo.create(
            project_id=data.project_id,
            name=data.name,
            description=data.description,
            definition=definition,
        )

    async def create_run(self, definition_id: UUID, data: PipelineRunCreate) -> PipelineRun:
        defn = await self.get_definition(definition_id)
        return await self.run_repo.create(
            definition_id=defn.id,
            inputs=data.inputs,
            status="pending",
        )

    async def get_run(self, run_id: UUID) -> PipelineRun:
        run = await self.run_repo.get(run_id)
        if run is None:
            raise NotFoundError("PipelineRun", str(run_id))
        return run

    async def list_runs(
        self, definition_id: UUID, *, offset: int = 0, limit: int = 100
    ) -> list[PipelineRun]:
        return await self.run_repo.list_by_definition(definition_id, offset=offset, limit=limit)
