from collections.abc import AsyncGenerator

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.core.config import Settings
from bioforge.core.storage import ObjectStorage
from bioforge.services.pipeline import PipelineService
from bioforge.services.project import ProjectService
from bioforge.services.result import ResultService
from bioforge.services.sequence import SequenceService
from bioforge.services.workspace import WorkspaceService


async def get_session(request: Request) -> AsyncGenerator[AsyncSession, None]:
    factory = request.app.state.session_factory
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_storage(request: Request) -> ObjectStorage:
    return request.app.state.storage


async def get_workspace_service(
    session: AsyncSession = Depends(get_session),
) -> WorkspaceService:
    return WorkspaceService(session)


async def get_project_service(
    session: AsyncSession = Depends(get_session),
) -> ProjectService:
    return ProjectService(session)


async def get_sequence_service(
    session: AsyncSession = Depends(get_session),
) -> SequenceService:
    return SequenceService(session)


async def get_pipeline_service(
    session: AsyncSession = Depends(get_session),
) -> PipelineService:
    return PipelineService(session)


async def get_result_service(
    session: AsyncSession = Depends(get_session),
) -> ResultService:
    return ResultService(session)
