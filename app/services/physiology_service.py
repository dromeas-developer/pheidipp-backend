import uuid
from datetime import date
from typing import Optional

from app.models.physiology import AthletePhysiology
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.physiology_repository import PhysiologyRepository
from app.schemas.physiology import AthletePhysiologyCreate, AthletePhysiologyUpdate


class PhysiologyService:
    def __init__(
        self,
        physiology_repo: PhysiologyRepository,
        athlete_repo: AthleteRepository,
    ):
        self.physiology_repo = physiology_repo
        self.athlete_repo = athlete_repo

    async def _validate(
        self,
        athlete_id: uuid.UUID,
        effective_from: date,
        effective_to: Optional[date],
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        athlete = await self.athlete_repo.get_by_id(athlete_id)
        if athlete is None:
            raise ValueError("Athlete not found")

        if effective_to is not None and effective_from > effective_to:
            raise ValueError("effective_from must be <= effective_to")

        if await self.physiology_repo.has_overlap(
            athlete_id, effective_from, effective_to, exclude_id
        ):
            raise ValueError(
                "Date range overlaps with an existing physiology record"
            )

    async def create(
        self, data: AthletePhysiologyCreate
    ) -> AthletePhysiology:
        await self._validate(
            data.athlete_id,
            data.effective_from,
            data.effective_to,
        )
        payload = data.model_dump()
        return await self.physiology_repo.create(**payload)

    async def list_by_athlete(
        self, athlete_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> list[AthletePhysiology]:
        athlete = await self.athlete_repo.get_by_id(athlete_id)
        if athlete is None:
            raise ValueError("Athlete not found")
        return await self.physiology_repo.get_by_athlete(
            athlete_id, skip=skip, limit=limit
        )

    async def get_by_id(
        self, physiology_id: uuid.UUID
    ) -> Optional[AthletePhysiology]:
        return await self.physiology_repo.get_by_id(physiology_id)

    async def get_effective(
        self, athlete_id: uuid.UUID, target_date: date
    ) -> Optional[AthletePhysiology]:
        return await self.physiology_repo.get_by_athlete_and_date(
            athlete_id, target_date
        )

    async def update(
        self, physiology_id: uuid.UUID, data: AthletePhysiologyUpdate
    ) -> Optional[AthletePhysiology]:
        existing = await self.physiology_repo.get_by_id(physiology_id)
        if existing is None:
            return None

        update_data = data.model_dump(exclude_unset=True)
        effective_from = update_data.get(
            "effective_from", existing.effective_from
        )
        effective_to = update_data.get("effective_to", existing.effective_to)

        await self._validate(
            existing.athlete_id,
            effective_from,
            effective_to,
            exclude_id=physiology_id,
        )
        return await self.physiology_repo.update(
            physiology_id, **update_data
        )

    async def delete(self, physiology_id: uuid.UUID) -> bool:
        return await self.physiology_repo.delete(physiology_id)
