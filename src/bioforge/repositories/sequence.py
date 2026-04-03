from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.sequence import Sequence
from bioforge.repositories.base import BaseRepository


class SequenceRepository(BaseRepository[Sequence]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Sequence)

    async def list_by_project(
        self,
        project_id: UUID,
        *,
        sequence_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[Sequence]:
        stmt = (
            select(Sequence)
            .where(Sequence.project_id == project_id)
            .order_by(Sequence.created_at.desc())
        )
        if sequence_type:
            stmt = stmt.where(Sequence.sequence_type == sequence_type)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
