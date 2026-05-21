from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
import uuid

from app.core.security import hash_password
from app.core.unit_of_work import UnitOfWork
from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.schemas.athlete import (
    AthleteCreate,
    AthleteUpdate,
)


class AthleteService:
    def __init__(
        self,
        athlete_repo: AthleteRepository,
        profile_repo: AthleteProfileRepository | None = None,
        ):
        self.athlete_repo = athlete_repo
        self.profile_repo = profile_repo

    async def create_athlete(self, data: AthleteCreate) -> Athlete:
        athlete_data = data.model_dump(exclude_unset=True)
        if athlete_data.get("password"):
            athlete_data["hashed_password"] = hash_password(athlete_data["password"])
            del athlete_data["password"]
        try:
            return await self.athlete_repo.create(**athlete_data)
        except IntegrityError as e:
            if "ix_athletes_email" in str(e) or "email" in str(e).lower():
                raise ValueError("An athlete with this email already exists") from e
            raise

    async def get_athlete(self, athlete_id: uuid.UUID) -> Athlete | None:
        return await self.athlete_repo.get_by_id(athlete_id)

    async def get_profile(self, athlete_id: uuid.UUID) -> AthleteProfile | None:
        if self.profile_repo:
            return await self.profile_repo.get_by_athlete_id(athlete_id)
        return None

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

    async def set_onboarding_complete(
        self, athlete_id: uuid.UUID
    ) -> Athlete | None:
        return await self.athlete_repo.update(
            athlete_id, onboarding_complete=True
        )

    async def set_onboarding_complete_uow(
        self, athlete_id: uuid.UUID, uow: UnitOfWork
    ) -> None:
        athlete = await uow.athletes.get_by_id(athlete_id)
        if athlete is None:
            raise ValueError(f"Athlete {athlete_id} not found")
        athlete.onboarding_complete = True
        await uow.athletes.session.flush()

    async def get_profile_uow(
        self, athlete_id: uuid.UUID, uow: UnitOfWork
    ) -> AthleteProfile | None:
        return await uow.profiles.get_by_athlete_id(athlete_id)
    