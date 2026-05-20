from typing import Optional
from uuid import UUID

from app.schemas.coach_message import CoachMessageResponse, CoachMessageListResponse
from app.core.unit_of_work import UnitOfWork


class CoachMessageService:
    def __init__(self):
        pass

    async def get_latest(
        self, athlete_id: UUID, uow: UnitOfWork
    ) -> Optional[CoachMessageResponse]:
        message = await uow.coach_messages.get_latest_by_athlete(athlete_id)
        if message:
            return CoachMessageResponse.model_validate(message)
        return None

    async def get_first_message(
        self, athlete_id: UUID, uow: UnitOfWork
    ) -> Optional[CoachMessageResponse]:
        message = await uow.coach_messages.get_first_message_by_athlete(athlete_id)
        if message:
            return CoachMessageResponse.model_validate(message)
        return None

    async def has_first_message(
        self, athlete_id: UUID, uow: UnitOfWork
    ) -> bool:
        return await uow.coach_messages.has_first_message(athlete_id)

    async def list_by_athlete(
        self,
        athlete_id: UUID,
        uow: UnitOfWork,
        limit: int = 50,
        offset: int = 0,
    ) -> CoachMessageListResponse:
        messages, total = await uow.coach_messages.list_by_athlete(
            athlete_id, limit, offset
        )
        return CoachMessageListResponse(
            items=[CoachMessageResponse.model_validate(m) for m in messages],
            total=total,
        )