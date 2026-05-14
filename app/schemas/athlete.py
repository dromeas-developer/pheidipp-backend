import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.enums import AthleteStatus


class AthleteBase(BaseModel):
    email: EmailStr


class AthleteCreate(AthleteBase):
    password: Optional[str] = Field(default=None, min_length=8)


class AthleteUpdate(BaseModel):
    status: Optional[AthleteStatus] = None
    password: Optional[str] = Field(default=None, min_length=8)


class AthleteResponse(AthleteBase):
    id: uuid.UUID
    status: AthleteStatus
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
