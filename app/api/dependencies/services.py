from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.activity_repository import ActivityRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.fitness_repository import FitnessRepository
from app.repositories.physiology_repository import PhysiologyRepository
from app.repositories.training_block_repository import TrainingBlockRepository
from app.repositories.wellness_repository import WellnessRepository
from app.services.activity_service import ActivityService
from app.services.athlete_profile_service import AthleteProfileService
from app.services.athlete_preferences_service import AthletePreferencesService
from app.services.athlete_service import AthleteService
from app.services.fitness_service import FitnessService
from app.services.physiology_service import PhysiologyService
from app.services.training_block_service import TrainingBlockService
from app.services.wellness_service import WellnessService


async def get_activity_service(
    db: AsyncSession = Depends(get_db),
) -> ActivityService:
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    return ActivityService(activity_repo, athlete_repo)


async def get_wellness_service(
    db: AsyncSession = Depends(get_db),
) -> WellnessService:
    wellness_repo = WellnessRepository(db)
    athlete_repo = AthleteRepository(db)
    return WellnessService(wellness_repo, athlete_repo)


async def get_fitness_service(
    db: AsyncSession = Depends(get_db),
) -> FitnessService:
    fitness_repo = FitnessRepository(db)
    athlete_repo = AthleteRepository(db)
    return FitnessService(fitness_repo, athlete_repo)


async def get_athlete_service(
    db: AsyncSession = Depends(get_db),
) -> AthleteService:
    athlete_repo = AthleteRepository(db)
    profile_repo = AthleteProfileRepository(db)
    return AthleteService(athlete_repo, profile_repo)


async def get_athlete_profile_service(
    db: AsyncSession = Depends(get_db),
) -> AthleteProfileService:
    profile_repo = AthleteProfileRepository(db)
    return AthleteProfileService(profile_repo)


def get_athlete_preferences_service(
    db: AsyncSession = Depends(get_db),
) -> AthletePreferencesService:
    return AthletePreferencesService(AthletePreferencesRepository(db))


def get_training_block_service(
    db: AsyncSession = Depends(get_db),
) -> TrainingBlockService:
    return TrainingBlockService(TrainingBlockRepository(db))


async def get_physiology_service(
    db: AsyncSession = Depends(get_db),
) -> PhysiologyService:
    physiology_repo = PhysiologyRepository(db)
    athlete_repo = AthleteRepository(db)
    return PhysiologyService(physiology_repo=physiology_repo, athlete_repo=athlete_repo)