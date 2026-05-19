import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DataSource


class FitnessBase(BaseModel):
    metric_date: date
    tss: Optional[float] = None
    atl: Optional[float] = None
    ctl: Optional[float] = None
    tsb: Optional[float] = None
    source: DataSource = DataSource.MANUAL


class FitnessCreate(FitnessBase):
    athlete_id: uuid.UUID


class FitnessUpdate(BaseModel):
    metric_date: Optional[date] = None
    tss: Optional[float] = None
    atl: Optional[float] = None
    ctl: Optional[float] = None
    tsb: Optional[float] = None
    source: DataSource = DataSource.MANUAL


class FitnessResponse(FitnessBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FitnessListParams(BaseModel):
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    limit: int = Field(default=50, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class FitnessListResponse(BaseModel):
    items: list[FitnessResponse]
    total: int