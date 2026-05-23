from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.services import get_training_plan_service
from app.api.dependencies.services import get_db
from app.api.dependencies.auth import require_self
from app.core.unit_of_work import UnitOfWork
from app.services.training_plan_service import TrainingPlanService
from app.schemas.training_plan import TrainingPlanResponse

router = APIRouter(prefix="/athletes", tags=["training_plans"])


@router.get(
    "/{athlete_id}/training-plans/active",
    response_model=TrainingPlanResponse,
    summary="Get the active training plan for an athlete",
)
async def get_active_training_plan(
    athlete_id: UUID,
    _: UUID = Depends(require_self),
    service: TrainingPlanService = Depends(get_training_plan_service),
    db: AsyncSession = Depends(get_db),
):
    async with UnitOfWork(db) as uow:
        result = await service.get_active_plan(athlete_id, uow)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active training plan found for this athlete",
        )
    return result


@router.get(
    "/{athlete_id}/training-plans/{plan_id}",
    response_model=TrainingPlanResponse,
    summary="Get a specific training plan by ID",
)
async def get_training_plan(
    athlete_id: UUID,
    plan_id: UUID,
    _: UUID = Depends(require_self),
    service: TrainingPlanService = Depends(get_training_plan_service),
    db: AsyncSession = Depends(get_db),
):
    async with UnitOfWork(db) as uow:
        result = await service.get_plan_by_id(plan_id, uow)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Training plan not found",
        )
    if result.training_plan.athlete_id != athlete_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied",
        )
    return result