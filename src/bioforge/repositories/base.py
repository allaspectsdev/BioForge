from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bioforge.models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model_class: type[T]):
        self.session = session
        self.model_class = model_class

    async def get(self, id: UUID) -> T | None:
        return await self.session.get(self.model_class, id)

    async def list(self, *, offset: int = 0, limit: int = 100) -> list[T]:
        stmt = (
            select(self.model_class)
            .order_by(self.model_class.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, **kwargs: object) -> T:
        instance = self.model_class(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: UUID, **kwargs: object) -> T | None:
        instance = await self.get(id)
        if instance is None:
            return None
        for key, value in kwargs.items():
            setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def delete(self, id: UUID) -> bool:
        instance = await self.get(id)
        if instance is None:
            return False
        await self.session.delete(instance)
        await self.session.flush()
        return True
