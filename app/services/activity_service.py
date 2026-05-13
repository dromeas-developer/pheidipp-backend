from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity, ActivityType
from app.models.enums import PerceivedEffort
from app.repositories.activity_repository import ActivityRepository
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.activity import (
    ActivityCreate,
    ActivityListParams,
    ActivityUpdate,
)


class ActivityService:
    def __init__(
        self,
        activity_repo: ActivityRepository,
        athlete_repo: AthleteRepository,
    ):
        self.activity_repo = activity_repo
        self.athlete_repo = athlete_repo

    async def create_activity(self, data: ActivityCreate) -> Activity:
        # Verify athlete exists
        athlete = await self.athlete_repo.get_by_id(data.athlete_id)
        if not athlete:
            raise ValueError(f"Athlete with id {data.athlete_id} not found")

        # Validate finished_at > started_at
        if data.finished_at and data.started_at:
            if data.finished_at <= data.started_at:
                raise ValueError("finished_at must be after started_at")

        # Compute duration_seconds if not provided
        activity_data = data.model_dump(exclude_unset=True)
        if data.started_at and data.finished_at and "duration_seconds" not in activity_data:
            activity_data["duration_seconds"] = int(
                (data.finished_at - data.started_at).total_seconds()
            )

        # Auto-generate title if missing
        if not activity_data.get("title") and activity_data.get("activity_type"):
            activity_type = activity_data["activity_type"]
            if isinstance(activity_type, ActivityType):
                activity_type = activity_type.value

            suffix = ""
            if data.started_at:
                hour = data.started_at.hour
                if 5 <= hour < 12:
                    suffix = "Morning"
                elif 12 <= hour < 17:
                    suffix = "Afternoon"
                else:
                    suffix = "Evening"

            activity_data["title"] = f"{suffix} {activity_type.title()}"

        return await self.activity_repo.create(**activity_data)

    async def get_activity(self, activity_id: UUID) -> Activity | None:
        return await self.activity_repo.get_by_id(activity_id)

    async def list_athlete_activities(
        self, athlete_id: UUID, params: ActivityListParams
    ) -> list[Activity]:
        return await self.activity_repo.get_by_athlete(
            athlete_id=athlete_id,
            skip=params.offset,
            limit=params.limit,
            activity_type=params.activity_type,
            date_from=params.date_from,
            date_to=params.date_to,
        )

    async def update_activity(
        self, activity_id: UUID, data: ActivityUpdate
    ) -> Activity | None:
        update_data = data.model_dump(exclude_unset=True)

        # Recompute duration_seconds if timestamps changed
        if "started_at" in update_data or "finished_at" in update_data:
            if update_data.get("started_at") and update_data.get("finished_at"):
                update_data["duration_seconds"] = int(
                    (update_data["finished_at"] - update_data["started_at"]).total_seconds()
                )
            elif update_data.get("started_at") is None and update_data.get("finished_at") is None:
                # If both are being unset, keep existing duration if present
                existing = await self.activity_repo.get_by_id(activity_id)
                if existing and existing.duration_seconds is not None:
                    update_data["duration_seconds"] = existing.duration_seconds

        return await self.activity_repo.update(activity_id, **update_data)

    async def delete_activity(self, activity_id: UUID) -> bool:
        return await self.activity_repo.delete(activity_id)

    async def count_by_athlete(
        self,
        athlete_id: UUID,
        activity_type: Optional[ActivityType] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> int:
        return await self.activity_repo.count_by_athlete(
            athlete_id,
            activity_type=activity_type,
            date_from=date_from,
            date_to=date_to,
        )
