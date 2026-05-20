from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.models.enums import MessageType


class CoachMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    athlete_id: UUID
    twin_state_id: Optional[UUID] = None
    training_block_id: Optional[UUID] = None
    message_type: MessageType
    content: str
    generation_metadata: dict
    created_at: datetime


class CoachMessageListResponse(BaseModel):
    items: list[CoachMessageResponse]
    total: int