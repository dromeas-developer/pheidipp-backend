import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import ConfigDict, BaseModel

from app.models.enums import DataSource


class AthletePhysiologyBase(BaseModel):
    ftp: Optional[int] = None
    lt1: Optional[int] = None
    lt2: Optional[int] = None
    vo2_max: Optional[float] = None
    max_hr: Optional[int] = None
    source: DataSource = DataSource.MANUAL
    effective_from: date
    effective_to: Optional[date] = None


class AthletePhysiologyCreate(AthletePhysiologyBase):
    athlete_id: uuid.UUID


class AthletePhysiologyUpdate(BaseModel):
    ftp: Optional[int] = None
    lt1: Optional[int] = None
    lt2: Optional[int] = None
    vo2_max: Optional[float] = None
    max_hr: Optional[int] = None
    source: Optional[DataSource] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None


class AthletePhysiologyResponse(AthletePhysiologyBase):
    id: uuid.UUID
    athlete_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
