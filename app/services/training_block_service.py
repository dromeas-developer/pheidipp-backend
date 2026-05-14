import uuid
from fastapi import HTTPException, status
from app.repositories.training_block_repository import TrainingBlockRepository
from app.schemas.training_block import TrainingBlockCreate, TrainingBlockUpdate
from app.models.training_block import TrainingBlock
from app.models.enums import GoalStatus


class TrainingBlockService:
    def __init__(self, repo: TrainingBlockRepository):
        self.repo = repo

    async def create_for_athlete(
        self, athlete_id: uuid.UUID, data: TrainingBlockCreate
    ) -> TrainingBlock:
        existing = await self.repo.get_active_by_athlete(athlete_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "An active training block already exists. "
                    "Complete or abandon it before starting a new one."
                ),
            )
        payload = data.model_dump(exclude_unset=True)
        payload["athlete_id"] = athlete_id
        payload["status"] = GoalStatus.ACTIVE
        return await self.repo.create(**payload)

    async def get_active_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> TrainingBlock | None:
        return await self.repo.get_active_by_athlete(athlete_id)

    async def list_by_athlete(
        self, athlete_id: uuid.UUID
    ) -> list[TrainingBlock]:
        return await self.repo.list_by_athlete(athlete_id)

    async def update(
        self, block_id: uuid.UUID, data: TrainingBlockUpdate
    ) -> TrainingBlock | None:
        # TrainingBlockUpdate only permits status, event date, description.
        # Semantic fields are excluded from the schema and cannot be updated here.
        return await self.repo.update(
            block_id, **data.model_dump(exclude_unset=True)
        )

    async def complete_block(self, block_id: uuid.UUID) -> TrainingBlock | None:
        return await self.repo.update(block_id, status=GoalStatus.COMPLETED)

    async def abandon_block(self, block_id: uuid.UUID) -> TrainingBlock | None:
        return await self.repo.update(block_id, status=GoalStatus.ABANDONED)
    