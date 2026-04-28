from typing import Generic, TypeVar
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.base_repository import BaseRepository

ModelType = TypeVar("ModelType")


class BaseService(Generic[ModelType]):
    def __init__(self, repository: BaseRepository[ModelType]):
        self.repository = repository

    async def execute(self):
        raise NotImplementedError

    async def validate(self):
        raise NotImplementedError