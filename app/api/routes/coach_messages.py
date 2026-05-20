from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_coach_message_service
from app.db.session import get_db
from app.core.unit_of_work import UnitOfWork
from app.services.coach_message_service import CoachMessageService
from app.schemas.coach_message import CoachMessageResponse, CoachMessageListResponse

router = APIRouter(prefix="/athletes", tags=["coach_messages"])


@router.get(
    "/{athlete_id}/coach-messages",
    response_model=CoachMessageListResponse,
    summary="List coach messages for an athlete",
)
async def list_coach_messages(
    athlete_id: UUID,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: CoachMessageService = Depends(get_coach_message_service),
    db: AsyncSession = Depends(get_db),
):
    """Returns paginated list of coach messages for an athlete."""
    async with UnitOfWork(db) as uow:
        return await service.list_by_athlete(athlete_id, uow, limit, offset)


@router.get(
    "/{athlete_id}/coach-messages/latest",
    response_model=CoachMessageResponse,
    summary="Get latest coach message",
)
async def get_latest_coach_message(
    athlete_id: UUID,
    service: CoachMessageService = Depends(get_coach_message_service),
    db: AsyncSession = Depends(get_db),
):
    """Returns the most recent coach message for an athlete."""
    async with UnitOfWork(db) as uow:
        message = await service.get_latest(athlete_id, uow)
        if not message:
            raise HTTPException(
                status_code=404,
                detail="No coach messages found for this athlete",
            )
        return message


@router.get(
    "/{athlete_id}/coach-messages/first",
    response_model=CoachMessageResponse,
    summary="Get first coach message",
)
async def get_first_coach_message(
    athlete_id: UUID,
    service: CoachMessageService = Depends(get_coach_message_service),
    db: AsyncSession = Depends(get_db),
):
    """Returns the first coach message for an athlete."""
    async with UnitOfWork(db) as uow:
        message = await service.get_first_message(athlete_id, uow)
        if not message:
            raise HTTPException(
                status_code=404,
                detail="No first coach message found for this athlete",
            )
        return message