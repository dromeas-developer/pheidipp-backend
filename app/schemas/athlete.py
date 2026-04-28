import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from app.models.enums import (
    AthleteStatus,
    Gender,
    CountryCode,
    Timezone,
    LanguageCode,
    UnitPreference,
)


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


class AthleteProfileBase(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=100)
    last_name: Optional[str] = Field(default=None, max_length=100)
    display_name: Optional[str] = Field(default=None, max_length=100)
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    country_code: Optional[CountryCode] = None
    timezone: Optional[Timezone] = None
    language_code: Optional[LanguageCode] = None
    unit_preference: Optional[UnitPreference] = UnitPreference.METRIC


class AthleteProfileCreate(AthleteProfileBase):
    pass


class AthleteProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[Gender] = None
    country_code: Optional[CountryCode] = None
    timezone: Optional[Timezone] = None
    language_code: Optional[LanguageCode] = None
    unit_preference: Optional[UnitPreference] = None


class AthleteProfileResponse(AthleteProfileBase):
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AthleteWithProfileResponse(AthleteResponse):
    profile: Optional[AthleteProfileResponse] = None
