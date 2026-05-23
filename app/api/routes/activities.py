from fastapi import APIRouter, Depends, HTTPException, status
from uuid import UUID

from app.api.dependencies import get_activity_service, get_current_athlete_id
from app.schemas.activity import (
    ActivityCreate,
    ActivityListParams,
    ActivityListResponse,
    ActivityResponse,
    ActivityUpdate,
)
from app.services.activity_service import ActivityService

router = APIRouter(prefix="/activities", tags=["activities"])


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    payload: ActivityCreate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: ActivityService = Depends(get_activity_service),
):
    if payload.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        activity = await service.create_activity(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ActivityResponse.model_validate(activity)


@router.get("/{activity_id}", response_model=ActivityResponse)
async def get_activity(
    activity_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: ActivityService = Depends(get_activity_service),
):
    activity = await service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return ActivityResponse.model_validate(activity)


@router.patch("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: UUID,
    payload: ActivityUpdate,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: ActivityService = Depends(get_activity_service),
):
    activity = await service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity not found")
    if activity.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    try:
        activity = await service.update_activity(activity_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return ActivityResponse.model_validate(activity)


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(
    activity_id: UUID,
    current_athlete_id: UUID = Depends(get_current_athlete_id),
    service: ActivityService = Depends(get_activity_service),
):
    activity = await service.get_activity(activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    if activity.athlete_id != current_athlete_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    success = await service.delete_activity(activity_id)
    if not success:
        raise HTTPException(status_code=404, detail="Activity not found")
    return None
