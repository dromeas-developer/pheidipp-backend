import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict

from app.models.enums import (
    Gender,
    UnitPreference,
)
from app.schemas.athlete import AthleteResponse


class AthleteProfileBase(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    country_code: Optional[str] = Field(default=None, max_length=2)
    timezone: Optional[str] = Field(default=None, max_length=100)
    language_code: Optional[str] = Field(default=None, max_length=5)
    unit_preference: Optional[UnitPreference] = UnitPreference.METRIC


class AthleteProfileCreate(AthleteProfileBase):
    pass


class AthleteProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    country_code: Optional[str] = Field(default=None, max_length=2)
    timezone: Optional[str] = Field(default=None, max_length=100)
    language_code: Optional[str] = Field(default=None, max_length=5)
    unit_preference: Optional[UnitPreference] = None


class AthleteProfileResponse(AthleteProfileBase):
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AthleteWithProfileResponse(AthleteResponse):
    profile: Optional[AthleteProfileResponse] = None
