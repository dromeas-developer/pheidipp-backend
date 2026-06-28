"""Plan API surface — four read-only endpoints behind ``require_self``.

Implements the Phase-1.4 contract from
``docs/implementation/phase-1/phase-1-4-p1-plan-generation.md``.

All endpoints live under ``/athletes/{athlete_id}/plan`` and depend
on ``require_self`` so the JWT's ``athlete_id`` must equal the path
parameter — mismatches surface as HTTP 403, never 404, so
authentication and authorization failures remain distinguishable.

ORM-to-response mapping is delegated to Pydantic's
``model_validate(row)`` (with ``from_attributes=True`` on the
response schemas) so the conversion lives in one place. The plan
read endpoints query the repositories directly using the
``get_db`` dependency — the read path is read-only, so a service
class is not strictly required.

Query patterns:

* ``GET /plan`` resolves the athlete's active TrainingGoal then
  fetches the active TrainingPlan via ``TrainingPlanRepository.
  get_active_for_athlete``. 404 when either is missing.
* ``GET /plan/sessions`` joins through ``PlannedSession.weekly_plan_id →
  WeeklyPlan.training_plan_id`` so the denormalised ``planned_sessions
  .training_plan_id`` is not used directly (the architectural
  staleness invariant).
* ``GET /plan/upcoming`` caps the response at the next five
  ``PlannedSession`` rows from today onwards, ordered by ``target_date
  ASC, session_slot ASC``.
* ``GET /plan/checkpoints`` walks the ``PlannedSession → WeeklyPlan →
  TrainingPlan`` join to find checkpoints for the active plan only.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_self
from app.models.checkpoint import Checkpoint
from app.models.planned_session import PlannedSession
from app.models.weekly_plan import WeeklyPlan
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.schemas.plan import (
    CheckpointResponse,
    PlannedSessionResponse,
    TrainingPlanResponse,
    UpcomingSessionsResponse,
)


plan_router = APIRouter(prefix="/athletes", tags=["plan"])


# ---------------------------------------------------------------------------
# Internal helpers — kept module-level so each endpoint stays a thin
# wrapper around the repositories.
# ---------------------------------------------------------------------------


async def _resolve_active_plan_id(
    *, athlete_id: uuid.UUID, plans: TrainingPlanRepository
) -> uuid.UUID | None:
    """Look up the active TrainingPlan id for *athlete_id*.

    Returns ``None`` when the athlete has no active goal or no active
    plan — the API layer maps that to HTTP 404.
    """
    plan = await plans.get_active_for_athlete(athlete_id)
    if plan is None:
        return None
    return plan.id


def _plan_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=(
            "No active training plan found. Complete onboarding first "
            "to generate a plan."
        ),
    )


def build_plan_repository(
    session: AsyncSession = Depends(get_db),
) -> TrainingPlanRepository:
    """Construct a :class:`TrainingPlanRepository` for the current request."""
    return TrainingPlanRepository(session=session)


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------


@plan_router.get(
    "/{athlete_id}/plan",
    response_model=TrainingPlanResponse,
)
async def get_plan(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    plans: TrainingPlanRepository = Depends(build_plan_repository),
) -> TrainingPlanResponse:
    """Return the active ``TrainingPlan`` for the path athlete.

    404 when no active plan exists. 403 when the JWT athlete_id does
    not match the path athlete (``require_self``).
    """
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    plan = await plans.get_by_id(plan_id)
    if plan is None:
        raise _plan_not_found()
    return TrainingPlanResponse.model_validate(plan)


@plan_router.get(
    "/{athlete_id}/plan/sessions",
    response_model=list[PlannedSessionResponse],
)
async def get_plan_sessions(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    plans: TrainingPlanRepository = Depends(build_plan_repository),
    session: AsyncSession = Depends(get_db),
) -> list[PlannedSessionResponse]:
    """Return all ``PlannedSession`` rows for the active plan.

    Joins through ``WeeklyPlan.training_plan_id`` (the architectural
    source-of-truth) per the ``PlannedSession.training_plan_id``
    staleness invariant. 200 + empty list when the plan exists but
    has no sessions yet. 404 when no active plan exists.
    """
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    result = await session.execute(
        select(PlannedSession)
        .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
        .where(WeeklyPlan.training_plan_id == plan_id)
        .order_by(
            PlannedSession.target_date.asc(),
            PlannedSession.session_slot.asc(),
        )
    )
    rows = list(result.scalars().all())
    return [PlannedSessionResponse.model_validate(r) for r in rows]


@plan_router.get(
    "/{athlete_id}/plan/upcoming",
    response_model=UpcomingSessionsResponse,
)
async def get_upcoming_sessions(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    plans: TrainingPlanRepository = Depends(build_plan_repository),
    session: AsyncSession = Depends(get_db),
) -> UpcomingSessionsResponse:
    """Return the next five ``PlannedSession`` rows from today onwards.

    Today is evaluated against the server's UTC clock (the
    architecture's target-date / timezone interpretation lands in
    Phase 2). 404 when no active plan exists; 200 with empty list
    when there are no upcoming sessions.
    """
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    today = datetime.now(timezone.utc).date()
    result = await session.execute(
        select(PlannedSession)
        .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
        .where(
            WeeklyPlan.training_plan_id == plan_id,
            PlannedSession.target_date >= today,
        )
        .order_by(
            PlannedSession.target_date.asc(),
            PlannedSession.session_slot.asc(),
        )
        .limit(5)
    )
    rows = list(result.scalars().all())
    return UpcomingSessionsResponse(
        sessions=[PlannedSessionResponse.model_validate(r) for r in rows],
    )


@plan_router.get(
    "/{athlete_id}/plan/checkpoints",
    response_model=list[CheckpointResponse],
)
async def get_plan_checkpoints(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    plans: TrainingPlanRepository = Depends(build_plan_repository),
    session: AsyncSession = Depends(get_db),
) -> list[CheckpointResponse]:
    """Return all ``Checkpoint`` rows for the active plan.

    Joins through ``PlannedSession → WeeklyPlan → TrainingPlan`` so
    checkpoints belonging to a superseded plan are filtered out. 404
    when no active plan exists.
    """
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    result = await session.execute(
        select(Checkpoint)
        .join(PlannedSession, PlannedSession.id == Checkpoint.planned_session_id)
        .join(WeeklyPlan, WeeklyPlan.id == PlannedSession.weekly_plan_id)
        .where(WeeklyPlan.training_plan_id == plan_id)
        .order_by(PlannedSession.target_date.asc())
    )
    rows = list(result.scalars().all())
    return [CheckpointResponse.model_validate(r) for r in rows]
