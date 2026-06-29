"""Workout API surface — two endpoints behind ``require_self``.

Implements the Phase-1.5b contract from
``docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md``:

* ``GET /athletes/{athlete_id}/today`` — return today's
  ``PlannedSession`` plus its ``GeneratedWorkout`` (auto-triggered
  on first view) and ``WorkoutStep[]``.
* ``POST /athletes/{athlete_id}/sessions/{session_id}/generate-workout`` —
  explicit generation trigger. Idempotent at the
  ``(planned_session_id, generation_date)`` key — second call returns
  HTTP 409 with the existing workout id.

All endpoints depend on ``require_self`` so the JWT's ``athlete_id``
must equal the path parameter — mismatches surface as HTTP 403, never
404, so authentication and authorization failures remain
distinguishable.

Transaction ownership mirrors the first-message-agent pattern
(``Pattern B`` from the FirstMessageAgent docstring): the agent does
not commit. Each route handler calls ``session.commit()`` after the
agent returns so all flushed writes (``GeneratedWorkout``,
``WorkoutStep[]``, ``GenerationEvent``, ``SystemEvent``,
``SystemEventOutbox``) become durable atomically.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_self
from app.core.prompt_registry import PromptRegistry
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.generated_workout_repository import (
    GeneratedWorkoutRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.planned_session_repository import (
    PlannedSessionRepository,
)
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.workout_step_repository import WorkoutStepRepository
from app.schemas.plan import PlannedSessionResponse
from app.schemas.workout import (
    GenerateWorkoutResponse,
    GeneratedWorkoutResponse,
    TodayResponse,
    WorkoutAlreadyGeneratedConflictResponse,
    WorkoutStepResponse,
)
from app.services.context_budget_service import ContextBudgetService
from app.services.workout_generation_agent import WorkoutGenerationAgent
from app.services.workout_generation_errors import (
    LLMServiceUnavailableError as WorkoutLLMServiceUnavailableError,
    PlannedSessionNotFoundError,
    WorkoutAlreadyGeneratedError,
)


workout_router = APIRouter(prefix="/athletes", tags=["workout"])


# ---------------------------------------------------------------------------
# Dependency factories — kept module-level so each endpoint stays a thin
# wrapper around the agent + repositories.
# ---------------------------------------------------------------------------


def build_workout_generation_agent(
    session: AsyncSession = Depends(get_db),
) -> WorkoutGenerationAgent:
    """Construct a :class:`WorkoutGenerationAgent` for the current request.

    Mirrors :func:`build_first_message_agent` — every request gets its
    own ``AsyncSession`` so the generation transaction is isolated from
    concurrent requests and the underlying connection pool.
    """
    generated_workouts = GeneratedWorkoutRepository(session)
    workout_steps = WorkoutStepRepository(session)
    generation_events = GenerationEventRepository(session)
    planned_sessions = PlannedSessionRepository(session)
    twin_states = TwinStateRepository(session)

    context_budget = ContextBudgetService(
        twin_states=twin_states,
        training_goals=TrainingGoalRepository(session),
        plans=TrainingPlanRepository(session),
        profiles=AthleteProfileRepository(session),
        preferences=AthletePreferencesRepository(session),
        planned_sessions=planned_sessions,
    )
    prompt_registry = PromptRegistry()

    return WorkoutGenerationAgent(
        session=session,
        generated_workouts=generated_workouts,
        workout_steps=workout_steps,
        generation_events=generation_events,
        planned_sessions=planned_sessions,
        twin_states=twin_states,
        context_budget=context_budget,
        prompt_registry=prompt_registry,
    )


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------


@workout_router.get(
    "/{athlete_id}/today",
    response_model=TodayResponse,
)
async def get_today(
    athlete_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    agent: WorkoutGenerationAgent = Depends(build_workout_generation_agent),
    session: AsyncSession = Depends(get_db),
) -> TodayResponse:
    """Return today's ``PlannedSession`` plus its ``GeneratedWorkout``.

    Behaviour (per plan step 9):

    * 404 when the athlete has no ``PlannedSession`` scheduled for today
      on their active plan.
    * 200 + existing workout when ``GeneratedWorkout`` already exists
      for the day — no LLM call.
    * 200 + freshly generated workout when no workout exists yet — the
      LLM is invoked inline and the session is committed before the
      response is returned.

    Cross-athlete access surfaces as 403 via ``require_self``. The
    twin-state pre-condition is enforced inside the agent; missing
    twin state surfaces as 502.
    """
    today = datetime.now(timezone.utc).date()
    planned_sessions = PlannedSessionRepository(session)
    sessions = await planned_sessions.get_today_for_athlete(
        athlete_id=athlete_id,
        target_date=today,
    )
    if not sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No planned session scheduled for today on the "
                "athlete's active plan."
            ),
        )

    # Single-session day is the typical case; for double-session days
    # the today response picks the AM session deterministically. A
    # multi-session today view is a future enhancement.
    planned_session = sessions[0]

    generated_workout = await agent.generate(
        athlete_id=athlete_id,
        planned_session_id=planned_session.id,
        generation_date=today,
        allow_existing=True,
    )
    await session.commit()

    step_rows = await agent.load_steps(generated_workout.id)

    return TodayResponse(
        planned_session=PlannedSessionResponse.model_validate(planned_session),
        generated_workout=GeneratedWorkoutResponse.model_validate(
            generated_workout
        ),
        steps=[WorkoutStepResponse.model_validate(s) for s in step_rows],
    )


@workout_router.post(
    "/{athlete_id}/sessions/{session_id}/generate-workout",
    response_model=GenerateWorkoutResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_generate_workout(
    athlete_id: uuid.UUID,
    session_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    agent: WorkoutGenerationAgent = Depends(build_workout_generation_agent),
    session: AsyncSession = Depends(get_db),
) -> GenerateWorkoutResponse:
    """Explicit workout-generation trigger.

    Behaviour (per plan step 10):

    * 201 + new workout on first call.
    * 409 + ``WorkoutAlreadyGeneratedConflictResponse`` when a
      ``GeneratedWorkout`` already exists for
      ``(planned_session_id, generation_date)``.
    * 502 when the LLM service is unavailable. The architecture
      doc surfaces this as 502 (Bad Gateway upstream) to distinguish
      from the first-message agent's 503.
    * 404 when the ``PlannedSession`` does not exist.
    * 403 when the JWT athlete_id does not match the path athlete.

    The session ownership rule: the agent flushes inside the
    caller's transaction; this handler calls ``session.commit()``
    after the agent returns. On 409 / 502 we do NOT commit because
    no writes were made (the agent's idempotency gate returns
    before any insert).
    """
    today = datetime.now(timezone.utc).date()

    # Validate the planned session exists before invoking the agent
    # so the 404 path is clean (the agent's contract error would
    # also surface, but pre-checking keeps the error mapping tight).
    planned_sessions = PlannedSessionRepository(session)
    planned_session = await planned_sessions.get_by_id(session_id)
    if planned_session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planned session {session_id} not found.",
        )

    try:
        generated_workout = await agent.generate(
            athlete_id=athlete_id,
            planned_session_id=session_id,
            generation_date=today,
            allow_existing=False,
        )
    except PlannedSessionNotFoundError:
        # Defensive: the agent raises this if its own internal
        # lookup runs after a row was deleted between the pre-check
        # and the generate call.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Planned session {session_id} not found.",
        )
    except WorkoutAlreadyGeneratedError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=WorkoutAlreadyGeneratedConflictResponse(
                existing_workout_id=exc.existing_workout_id,
                planned_session_id=session_id,
                generation_date=today,
            ).model_dump(mode="json"),
        )
    except WorkoutLLMServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Workout generation service temporarily unavailable.",
        )

    await session.commit()

    step_rows = await agent.load_steps(generated_workout.id)

    return GenerateWorkoutResponse(
        generated_workout=GeneratedWorkoutResponse.model_validate(
            generated_workout
        ),
        steps=[WorkoutStepResponse.model_validate(s) for s in step_rows],
    )