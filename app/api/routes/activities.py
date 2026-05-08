from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.activity import (
    ActivityCreate,
    ActivityListParams,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
from app.services.activity_service import ActivityService
from app.repositories.activity_repository import ActivityRepository

router = APIRouter(prefix="/activities", tags=["activities"])


async def get_activity_service(
    db: AsyncSession = Depends(get_db),
) -> ActivityService:
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    return ActivityService(activity_repo, athlete_repo)


@router.post("/", response_model=ActivityResponse)
async def create_activity(
    payload: ActivityCreate,
    service: ActivityService = Depends(get_activity_service),
):
    activity = await service.create_activity(payload)
    return ActivityResponse.model_validate(activity)


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: UUID,
    service: ActivityService = Depends(get_activity_service),
):
    activity = await service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityResponse.model_validate(activity)


@router.get("/athletes/{athlete_id}/activities", response_model=ActivityListResponse)
async def list_athlete_activities(
    athlete_id: UUID,
    params: ActivityListParams = Depends(),
    service: ActivityService = Depends(get_activity_service),
):
    activities = await service.list_athlete_activities(athlete_id, params)

    total = await service.count_by_athlete(athlete_id)

    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.patch("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: UUID,
    payload: ActivityUpdate,
    service: ActivityService = Depends(get_activity_service),
):
    activity = await service.update_activity(activity_id, payload)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityResponse.model_validate(activity)


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: UUID,
    service: ActivityService = Depends(get_activity_service),
):
    success = await service.delete_activity(activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Activity not found")
    return None
