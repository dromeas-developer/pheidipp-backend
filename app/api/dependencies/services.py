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
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.wellness_repository import WellnessRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.planned_session_repository import PlannedSessionRepository
from app.services.activity_service import ActivityService
from app.services.athlete_profile_service import AthleteProfileService
from app.services.athlete_preferences_service import AthletePreferencesService
from app.services.athlete_service import AthleteService
from app.services.fitness_service import FitnessService
from app.services.physiology_service import PhysiologyService
from app.services.training_block_service import TrainingBlockService
from app.services.wellness_service import WellnessService
from app.services.twin_state_service import TwinStateService
from app.services.twin_initialisation_service import TwinInitialisationService
from app.services.onboarding_service import OnboardingService
from app.services.coach_message_service import CoachMessageService
from app.services.phase_arc_computer import PhaseArcComputer
from app.services.plan_generation_brief_builder import PlanGenerationBriefBuilder
from app.services.methodology_profile_builder import MethodologyProfileBuilder
from app.services.plan_constraint_validator import PlanConstraintValidator
from app.services.plan_repair_engine import PlanRepairEngine
from app.services.training_plan_service import TrainingPlanService
from app.services.auth_service import AuthService
from app.agents.plan_generation_agent import PlanGenerationAgent


def get_auth_service() -> AuthService:
    """Factory for AuthService - no constructor args needed."""
    return AuthService()


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


def get_twin_state_service() -> TwinStateService:
    return TwinStateService()


def get_twin_initialisation_service() -> TwinInitialisationService:
    return TwinInitialisationService()


async def get_onboarding_service(
    db: AsyncSession = Depends(get_db),
) -> OnboardingService:
    athlete_service = AthleteService(
        AthleteRepository(db), AthleteProfileRepository(db)
    )
    ap_service = AthletePreferencesService(AthletePreferencesRepository(db))
    tb_service = TrainingBlockService(TrainingBlockRepository(db))
    twin_init_service = TwinInitialisationService()
    return OnboardingService(athlete_service, ap_service, tb_service, twin_init_service)


def get_coach_message_service(
    db: AsyncSession = Depends(get_db),
) -> CoachMessageService:
    return CoachMessageService()


def get_training_plan_service(
    db: AsyncSession = Depends(get_db),
) -> TrainingPlanService:
    plan_repo = TrainingPlanRepository(db)
    session_repo = PlannedSessionRepository(db)
    phase_arc_computer = PhaseArcComputer()
    brief_builder = PlanGenerationBriefBuilder()
    methodology_builder = MethodologyProfileBuilder()
    validator = PlanConstraintValidator()
    repair_engine = PlanRepairEngine()
    agent = PlanGenerationAgent()
    return TrainingPlanService(
        training_plan_repo=plan_repo,
        planned_session_repo=session_repo,
        phase_arc_computer=phase_arc_computer,
        brief_builder=brief_builder,
        agent=agent,
        validator=validator,
        repair_engine=repair_engine,
        methodology_profile_builder=methodology_builder,
    )