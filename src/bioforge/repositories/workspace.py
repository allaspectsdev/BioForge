from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.workspace import Workspace
from bioforge.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Workspace)
