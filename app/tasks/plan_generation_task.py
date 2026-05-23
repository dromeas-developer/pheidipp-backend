import uuid
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.unit_of_work import UnitOfWork
from app.services.phase_arc_computer import PhaseArcComputer
from app.services.plan_generation_brief_builder import PlanGenerationBriefBuilder
from app.services.methodology_profile_builder import MethodologyProfileBuilder
from app.services.plan_constraint_validator import PlanConstraintValidator
from app.services.plan_repair_engine import PlanRepairEngine
from app.services.training_plan_service import TrainingPlanService
from app.agents.plan_generation_agent import PlanGenerationAgent
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.planned_session_repository import PlannedSessionRepository
from app.models.enums import GenerationOutcome
from app.core.telemetry import GenerationEvent, log_generation_event

logger = logging.getLogger("pheidipp.tasks")


async def generate_training_plan(
    athlete_id: uuid.UUID,
    session: Optional[AsyncSession] = None,
) -> None:
    """
    Background task that generates a structured training plan for an athlete.
    Runs as a FastAPI BackgroundTask after onboarding completes.
    Idempotent: skips if an active plan already exists.

    Args:
        athlete_id: The athlete to generate a plan for.
        session: Optional AsyncSession for testing. If None, creates one from
            AsyncSessionLocal (production path).
    """
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        if own_session:
            async with session:
                await _generate_plan(athlete_id, session)
        else:
            await _generate_plan(athlete_id, session)
    except Exception as e:
        logger.error(
            f"Error generating training plan for athlete {athlete_id}: {e}"
        )
        # Do not re-raise — background task must not crash the app
    finally:
        if own_session:
            await session.close()


async def _generate_plan(
    athlete_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    async with UnitOfWork(session) as uow:
        # Idempotency: skip if active plan exists
        existing = await uow.training_plans.get_active_by_athlete(athlete_id)
        if existing:
            logger.info(
                f"Active training plan already exists for athlete {athlete_id}"
            )
            return

        # Fetch athlete
        athlete = await uow.athletes.get_by_id(athlete_id)
        if not athlete:
            event = GenerationEvent(
                athlete_id=athlete_id,
                outcome=GenerationOutcome.MISSING_DATA,
                model="",
                prompt_version="",
                brief_version="",
                data_tier="",
                confidence_level="",
                latency_ms=0,
                error_type="MissingData",
                error_message="Athlete not found",
            )
            log_generation_event(event)
            return

        # Fetch required data
        preferences = await uow.preferences.get_by_athlete(athlete_id)
        training_block = await uow.blocks.get_active_by_athlete(athlete_id)
        twin_state = await uow.twin_states.get_by_athlete_id(athlete_id)

        if not preferences or not training_block or not twin_state:
            missing = []
            if not preferences:
                missing.append("AthletePreferences")
            if not training_block:
                missing.append("TrainingBlock")
            if not twin_state:
                missing.append("TwinState")
            event = GenerationEvent(
                athlete_id=athlete_id,
                outcome=GenerationOutcome.MISSING_DATA,
                model="",
                prompt_version="",
                brief_version="",
                data_tier="",
                confidence_level="",
                latency_ms=0,
                error_type="MissingData",
                error_message=f"Missing data: {', '.join(missing)}",
            )
            log_generation_event(event)
            return

        # Construct service with UoW repositories
        plan_repo = TrainingPlanRepository(session)
        session_repo = PlannedSessionRepository(session)
        phase_arc_computer = PhaseArcComputer()
        brief_builder = PlanGenerationBriefBuilder()
        methodology_builder = MethodologyProfileBuilder()
        validator = PlanConstraintValidator()
        repair_engine = PlanRepairEngine()
        agent = PlanGenerationAgent()

        service = TrainingPlanService(
            training_plan_repo=plan_repo,
            planned_session_repo=session_repo,
            phase_arc_computer=phase_arc_computer,
            brief_builder=brief_builder,
            agent=agent,
            validator=validator,
            repair_engine=repair_engine,
            methodology_profile_builder=methodology_builder,
        )

        await service.generate_plan(athlete_id, uow)
        logger.info(f"Training plan generated for athlete {athlete_id}")