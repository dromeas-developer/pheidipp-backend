from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.db.session import get_db
from app.repositories.activity_repository import ActivityRepository
from app.repositories.athlete_repository import AthleteRepository
from app.schemas.activity import (
    ActivityCreate,
    ActivityListParams,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("/", response_model=ActivityResponse)
async def create_activity(
    payload: ActivityCreate,
    db: AsyncSession = Depends(get_db),
):
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    service = ActivityService(activity_repo, athlete_repo)
    activity = await service.create_activity(payload)
    return ActivityResponse.model_validate(activity)


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    service = ActivityService(activity_repo, athlete_repo)
    activity = await service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityResponse.model_validate(activity)


@router.get("/athletes/{athlete_id}/activities", response_model=ActivityListResponse)
async def list_athlete_activities(
    athlete_id: UUID,
    params: ActivityListParams = Depends(),
    db: AsyncSession = Depends(get_db),
):
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    service = ActivityService(activity_repo, athlete_repo)
    activities = await service.list_athlete_activities(athlete_id, params)

    # Get total count
    from sqlalchemy import select, func
    from app.models.activity import Activity

    count_query = select(func.count()).where(Activity.athlete_id == athlete_id)
    result = await db.execute(count_query)
    total = result.scalar_one()

    return ActivityListResponse(
        items=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@router.patch("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: UUID,
    payload: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
):
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    service = ActivityService(activity_repo, athlete_repo)
    activity = await service.update_activity(activity_id, payload)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return ActivityResponse.model_validate(activity)


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    activity_repo = ActivityRepository(db)
    athlete_repo = AthleteRepository(db)
    service = ActivityService(activity_repo, athlete_repo)
    success = await service.delete_activity(activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Activity not found")
    return None
