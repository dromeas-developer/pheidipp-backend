import uuid
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    text,
    func,
    CheckConstraint,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models.enums import (
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform
    )

if TYPE_CHECKING:
    from app.models.athlete import Athlete


class AthletePreferences(Base):
    __tablename__ = "athlete_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # enforces one-to-one at DB level
        index=True,
    )

    # Stable athlete configuration
    sport_background: Mapped[Optional[SportBackground]] = mapped_column(
        SAEnum(SportBackground, native_enum=False, length=30), nullable=True
    )
    years_structured_training: Mapped[Optional[float]] = mapped_column(nullable=True)
    training_time_of_day: Mapped[Optional[TrainingTimeOfDay]] = mapped_column(
        SAEnum(TrainingTimeOfDay, native_enum=False, length=20), nullable=True
    )
    # Structured JSONB — validated at schema layer via WeeklySchedule Pydantic model.
    # Shape:
    # {
    #   "days": {
    #     "mon": {"available": true,  "max_hours": 1.0,  "long_workout": false},
    #     "tue": {"available": false, "max_hours": 0,    "long_workout": false},
    #     "wed": {"available": true,  "max_hours": 1.5,  "long_workout": false},
    #     "thu": {"available": false, "max_hours": 0,    "long_workout": false},
    #     "fri": {"available": true,  "max_hours": 1.0,  "long_workout": false},
    #     "sat": {"available": true,  "max_hours": 2.5,  "long_workout": true},
    #     "sun": {"available": true,  "max_hours": 3.0,  "long_workout": true}
    #   },
    #   "available_days_count": 5  # must match count of days where available=true
    # }
    weekly_schedule: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Equipment — determines data tier for twin model
    gps_source: Mapped[Optional[GpsSource]] = mapped_column(
        SAEnum(GpsSource, native_enum=False, length=20), nullable=True
    )
    hr_source: Mapped[Optional[HrSource]] = mapped_column(
        SAEnum(HrSource, native_enum=False, length=20), nullable=True
    )
    power_source: Mapped[Optional[PowerSource]] = mapped_column(
        SAEnum(PowerSource, native_enum=False, length=20), nullable=True
    )
    primary_training_platform: Mapped[Optional[PrimaryTrainingPlatform]] = mapped_column(
        SAEnum(PrimaryTrainingPlatform, native_enum=False, length=30), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="preferences")

    __table_args__ = (
        CheckConstraint(
            "years_structured_training >= 0",
            name="ck_athlete_preferences_years_non_negative",
        ),
    )
