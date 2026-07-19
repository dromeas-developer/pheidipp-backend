"""Plan API surface — four read-only endpoints behind ``require_self``."""

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


async def _resolve_active_plan_id(
    *, athlete_id: uuid.UUID, plans: TrainingPlanRepository
) -> uuid.UUID | None:
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
    return TrainingPlanRepository(session=session)


@plan_router.get(
    "/{athlete_id}/plan",
    response_model=TrainingPlanResponse,
)
async def get_plan(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    plans: TrainingPlanRepository = Depends(build_plan_repository),
) -> TrainingPlanResponse:
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
