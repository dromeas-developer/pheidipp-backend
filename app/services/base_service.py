from typing import Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.repositories.base_repository import BaseRepository

ModelType = TypeVar("ModelType", bound=Base)


class BaseService(Generic[ModelType]):
    def __init__(self, repository: BaseRepository[ModelType]):
        self.repository = repository

    async def execute(self):
        raise NotImplementedError

    async def validate(self):
        raise NotImplementedError