from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.wellness import AthleteWellness
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.wellness_repository import WellnessRepository
from app.schemas.wellness import (
    WellnessCreate,
    WellnessListParams,
    WellnessUpdate,
)


class WellnessService:
    def __init__(
        self,
        wellness_repo: WellnessRepository,
        athlete_repo: AthleteRepository,
    ):
        self.wellness_repo = wellness_repo
        self.athlete_repo = athlete_repo

    async def create_wellness(self, data: WellnessCreate) -> AthleteWellness:
        athlete = await self.athlete_repo.get_by_id(data.athlete_id)
        if not athlete:
            raise ValueError(f"Athlete with id {data.athlete_id} not found")

        existing = await self.wellness_repo.get_by_athlete_date(
            data.athlete_id, data.metric_date
        )
        if existing:
            raise ValueError(
                f"Wellness record already exists for athlete {data.athlete_id} on {data.metric_date}"
            )

        return await self.wellness_repo.create(**data.model_dump())

    async def get_wellness(self, wellness_id: UUID) -> AthleteWellness | None:
        """Get wellness by wellness_id (primary key)."""
        return await self.wellness_repo.get_by_id(wellness_id)

    async def list_athlete_wellness(
        self, athlete_id: UUID, params: WellnessListParams
    ) -> list[AthleteWellness]:
        return await self.wellness_repo.get_by_athlete(
            athlete_id=athlete_id,
            skip=params.offset,
            limit=params.limit,
            date_from=params.date_from,
            date_to=params.date_to,
        )

    async def update_wellness(
        self, wellness_id: UUID, data: WellnessUpdate
    ) -> AthleteWellness | None:
        """Update wellness by wellness_id (primary key)."""
        existing = await self.wellness_repo.get_by_id(wellness_id)
        if not existing:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "metric_date" in update_data and update_data["metric_date"] is not None:
            new_date = update_data["metric_date"]
            existing_for_date = await self.wellness_repo.get_by_athlete_date(
                existing.athlete_id, new_date
            )
            if existing_for_date and existing_for_date.id != wellness_id:
                raise ValueError(
                    f"Wellness record already exists for athlete {existing.athlete_id} on {new_date}"
                )

        return await self.wellness_repo.update(wellness_id, **update_data)

    async def delete_wellness(self, wellness_id: UUID) -> bool:
        """Delete wellness by wellness_id (primary key)."""
        return await self.wellness_repo.delete(wellness_id)

    async def count_by_athlete(self, athlete_id: UUID) -> int:
        return await self.wellness_repo.count_by_athlete(athlete_id)
