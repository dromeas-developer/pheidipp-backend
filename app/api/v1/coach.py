"""Coach endpoints — first message and message list."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_self
from app.models.enums import MessageType
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.coaching_message_repository import (
    CoachingMessageRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.schemas.coaching import (
    CoachingMessageResponse,
    FirstMessageConflictResponse,
    MessagesListResponse,
)
from app.services.context_budget_service import ContextBudgetService
from app.agents.first_message_agent import (
    FirstMessageAgent,
    FirstMessageAlreadyExistsError,
    LLMServiceUnavailableError,
)
from app.core.prompt_registry import PromptRegistry


coach_router = APIRouter(prefix="/athletes", tags=["coach"])


def build_coaching_message_repository(
    session: AsyncSession = Depends(get_db),
) -> CoachingMessageRepository:
    return CoachingMessageRepository(session=session)


def build_first_message_agent(
    session: AsyncSession = Depends(get_db),
) -> FirstMessageAgent:
    coaching_messages = CoachingMessageRepository(session)
    generation_events = GenerationEventRepository(session)
    twin_states = TwinStateRepository(session)
    context_budget = ContextBudgetService(
        twin_states=twin_states,
        training_goals=TrainingGoalRepository(session),
        plans=TrainingPlanRepository(session),
        profiles=AthleteProfileRepository(session),
        preferences=AthletePreferencesRepository(session),
    )
    prompt_registry = PromptRegistry()

    return FirstMessageAgent(
        session=session,
        coaching_messages=coaching_messages,
        generation_events=generation_events,
        context_budget=context_budget,
        prompt_registry=prompt_registry,
        training_goals=TrainingGoalRepository(session),
        plans=TrainingPlanRepository(session),
        twin_states=twin_states,
    )


@coach_router.post(
    "/{athlete_id}/coach/first-message",
    response_model=CoachingMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_first_message(
    athlete_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    agent: FirstMessageAgent = Depends(build_first_message_agent),
    session: AsyncSession = Depends(get_db),
) -> CoachingMessageResponse:
    try:
        result = await agent.generate(athlete_id)
    except FirstMessageAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=FirstMessageConflictResponse(
                existing_message_id=exc.existing_message_id
            ).model_dump(mode="json"),
        )
    except LLMServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coach service temporarily unavailable.",
        )
    await session.commit()
    return result


@coach_router.get(
    "/{athlete_id}/coach/messages",
    response_model=MessagesListResponse,
)
async def get_coach_messages(
    athlete_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    coaching_messages: CoachingMessageRepository = Depends(
        build_coaching_message_repository
    ),
    message_type: Optional[MessageType] = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> MessagesListResponse:
    messages = await coaching_messages.get_by_athlete_id(
        athlete_id, message_type=message_type, limit=limit, offset=offset
    )

    total = await coaching_messages.get_all_count(athlete_id, message_type=message_type)

    return MessagesListResponse(
        messages=[CoachingMessageResponse.model_validate(m) for m in messages],
        total=total,
    )
