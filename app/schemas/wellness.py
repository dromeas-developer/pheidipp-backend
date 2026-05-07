import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import ConfigDict, BaseModel, Field

from app.models.enums import WellnessSource


class WellnessBase(BaseModel):
    metric_date: date
    sleep_total: Optional[int] = None
    sleep_light: Optional[int] = None
    sleep_deep: Optional[int] = None
    sleep_rem: Optional[int] = None
    sleep_awake: Optional[int] = None
    resting_hr: Optional[int] = None
    hrv: Optional[int] = None
    weight: Optional[float] = None
    source: WellnessSource
    timezone: str = Field(max_length=100)


class WellnessCreate(WellnessBase):
    athlete_id: uuid.UUID


class WellnessUpdate(BaseModel):
    metric_date: Optional[date] = None
    sleep_total: Optional[int] = None
    sleep_light: Optional[int] = None
    sleep_deep: Optional[int] = None
    sleep_rem: Optional[int] = None
    sleep_awake: Optional[int] = None
    resting_hr: Optional[int] = None
    hrv: Optional[int] = None
    weight: Optional[float] = None
    source: Optional[WellnessSource] = None
    timezone: Optional[str] = Field(default=None, max_length=100)


class WellnessResponse(WellnessBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WellnessListParams(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class WellnessListResponse(BaseModel):
    items: list[WellnessResponse]
    total: int
