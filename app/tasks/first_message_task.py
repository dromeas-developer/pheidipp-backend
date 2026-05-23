import uuid
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.core.unit_of_work import UnitOfWork
from app.services.first_message_brief_builder import FirstMessageBriefBuilder
from app.agents.first_message_agent import FirstMessageAgent
from app.services.coach_message_service import CoachMessageService
from app.models.enums import MessageType, GenerationOutcome
from app.core.telemetry import GenerationEvent, log_generation_event

logger = logging.getLogger("pheidipp.tasks")


async def generate_first_coach_message(
    athlete_id: uuid.UUID,
    session: Optional[AsyncSession] = None,
) -> None:
    """
    Background task that generates and stores the first coach message.
    Runs as a FastAPI BackgroundTask after onboarding completes.

    Args:
        athlete_id: The athlete to generate a message for.
        session: Optional AsyncSession for testing. If None, creates one from
            AsyncSessionLocal (production path).
    """
    own_session = session is None
    if own_session:
        session = AsyncSessionLocal()

    try:
        if own_session:
            async with session:
                await _generate_first_message(athlete_id, session)
        else:
            await _generate_first_message(athlete_id, session)
    except Exception as e:
        logger.error(f"Error generating first coach message for athlete {athlete_id}: {e}")
        # Do not re-raise - background task must not crash the app
    finally:
        if own_session:
            await session.close()


async def _generate_first_message(
    athlete_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    async with UnitOfWork(session) as uow:
        # Check if first message already exists
        has_first = await uow.coach_messages.has_first_message(athlete_id)
        if has_first:
            logger.info(f"First message already exists for athlete {athlete_id}")
            return

        # Fetch athlete, profile, preferences, training_block, twin_state
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

        profile = await uow.profiles.get_by_athlete_id(athlete_id)
        if not profile:
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
                error_message="AthleteProfile not found",
            )
            log_generation_event(event)
            return

        preferences = await uow.preferences.get_by_athlete(athlete_id)
        if not preferences:
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
                error_message="AthletePreferences not found",
            )
            log_generation_event(event)
            return

        training_block = await uow.blocks.get_active_by_athlete(athlete_id)
        if not training_block:
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
                error_message="TrainingBlock not found",
            )
            log_generation_event(event)
            return

        twin_state = await uow.twin_states.get_by_athlete_id(athlete_id)
        if not twin_state:
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
                error_message="TwinState not found",
            )
            log_generation_event(event)
            return

        # Build brief
        brief_builder = FirstMessageBriefBuilder()
        brief = await brief_builder.build(
            athlete=athlete,
            profile=profile,
            preferences=preferences,
            training_block=training_block,
            twin_state=twin_state,
        )

        # Generate message
        agent = FirstMessageAgent()
        content, metadata = await agent.generate(athlete_id, brief)

        # Create coach message
        await uow.coach_messages.create(
            athlete_id=athlete_id,
            twin_state_id=twin_state.id,
            training_block_id=training_block.id,
            message_type=MessageType.FIRST_MESSAGE,
            content=content,
            generation_metadata=metadata,
        )

        logger.info(f"First coach message generated for athlete {athlete_id}")