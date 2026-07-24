"""Plan API surface — four read-only endpoints behind ``require_self``."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import (
    build_plan_query_service,
    build_plan_repository,
    require_self,
)
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.schemas.plan import (
    CheckpointResponse,
    PlannedSessionResponse,
    TrainingPlanResponse,
    UpcomingSessionsResponse,
)
from app.services.plan_query_service import PlanQueryService


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
    plan_query: PlanQueryService = Depends(build_plan_query_service),
) -> list[PlannedSessionResponse]:
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    rows = await plan_query.get_sessions_for_plan(plan_id)
    return [PlannedSessionResponse.model_validate(r) for r in rows]


@plan_router.get(
    "/{athlete_id}/plan/upcoming",
    response_model=UpcomingSessionsResponse,
)
async def get_upcoming_sessions(
    athlete_id: uuid.UUID,
    athlete_id_dep: uuid.UUID = Depends(require_self),
    plans: TrainingPlanRepository = Depends(build_plan_repository),
    plan_query: PlanQueryService = Depends(build_plan_query_service),
) -> UpcomingSessionsResponse:
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    rows = await plan_query.get_upcoming_sessions(
        plan_id=plan_id, limit=5
    )
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
    plan_query: PlanQueryService = Depends(build_plan_query_service),
) -> list[CheckpointResponse]:
    plan_id = await _resolve_active_plan_id(
        athlete_id=athlete_id, plans=plans
    )
    if plan_id is None:
        raise _plan_not_found()

    rows = await plan_query.get_checkpoints_for_plan(plan_id)
    return [CheckpointResponse.model_validate(r) for r in rows]

