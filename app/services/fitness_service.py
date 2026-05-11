from uuid import UUID
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.fitness import AthleteFitness
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.fitness_repository import FitnessRepository
from app.schemas.fitness import (
    FitnessCreate,
    FitnessListParams,
    FitnessUpdate,
)


class FitnessService:
    def __init__(
        self,
        fitness_repo: FitnessRepository,
        athlete_repo: AthleteRepository,
    ):
        self.fitness_repo = fitness_repo
        self.athlete_repo = athlete_repo

    async def create_fitness(self, data: FitnessCreate) -> AthleteFitness:
        athlete = await self.athlete_repo.get_by_id(data.athlete_id)
        if not athlete:
            raise ValueError(f"Athlete with id {data.athlete_id} not found")

        existing = await self.fitness_repo.get_by_athlete_date(
            data.athlete_id, data.metric_date
        )
        if existing:
            raise ValueError(
                f"Fitness record already exists for athlete {data.athlete_id} on {data.metric_date}"
            )

        return await self.fitness_repo.create(**data.model_dump())

    async def get_fitness(self, fitness_id: UUID) -> AthleteFitness | None:
        """Get fitness by primary key (id)."""
        return await self.fitness_repo.get_by_id(fitness_id)

    async def list_athlete_fitness(
        self, athlete_id: UUID, params: FitnessListParams
    ) -> list[AthleteFitness]:
        return await self.fitness_repo.get_by_athlete(
            athlete_id=athlete_id,
            skip=params.offset,
            limit=params.limit,
            date_from=params.date_from,
            date_to=params.date_to,
        )

    async def update_fitness(
        self, fitness_id: UUID, data: FitnessUpdate
    ) -> AthleteFitness | None:
        """Update fitness by primary key (id)."""
        existing = await self.fitness_repo.get_by_id(fitness_id)
        if not existing:
            return None

        update_data = data.model_dump(exclude_unset=True)

        if "metric_date" in update_data and update_data["metric_date"] is not None:
            new_date = update_data["metric_date"]
            if new_date != existing.metric_date:
                existing_for_date = await self.fitness_repo.get_by_athlete_date(
                    existing.athlete_id, new_date
                )
                if existing_for_date:
                    raise ValueError(
                        f"Fitness record already exists for athlete {existing.athlete_id} on {new_date}"
                    )

        return await self.fitness_repo.update(fitness_id, **update_data)

    async def delete_fitness(self, fitness_id: UUID) -> bool:
        """Delete fitness by primary key (id)."""
        return await self.fitness_repo.delete(fitness_id)

    async def count_by_athlete(self, athlete_id: UUID) -> int:
        return await self.fitness_repo.count_by_athlete(athlete_id)