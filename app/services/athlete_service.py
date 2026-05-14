from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid

from app.core.security import hash_password
from app.models.athlete import Athlete
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
)


class AthleteService:
    def __init__(
        self,
        athlete_repo: AthleteRepository,
        ):
        self.athlete_repo = athlete_repo

    async def create_athlete(self, data: AthleteCreate) -> Athlete:
        athlete_data = data.model_dump(exclude_unset=True)
        if athlete_data.get("password"):
            athlete_data["hashed_password"] = hash_password(athlete_data["password"])
            del athlete_data["password"]
        return await self.athlete_repo.create(**athlete_data)

    async def get_athlete(self, athlete_id: uuid.UUID) -> Athlete | None:
        return await self.athlete_repo.get_by_id(athlete_id)

    async def get_athlete_with_profile(self, athlete_id: uuid.UUID) -> Athlete | None:
        result = await self.athlete_repo.session.execute(
            select(Athlete)
            .options(selectinload(Athlete.profile))
            .where(Athlete.id == athlete_id)
        )
        return result.scalar_one_or_none()

    async def update_athlete(self, athlete_id: uuid.UUID, data: AthleteUpdate) -> Athlete | None:
        update_data = data.model_dump(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = hash_password(update_data["password"])
            del update_data["password"]
        return await self.athlete_repo.update(athlete_id, **update_data)
    