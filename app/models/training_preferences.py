import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    String,
    DateTime,
    Date,
    Float,
    Integer,
    ForeignKey,
    text,
    func,
    Enum as SAEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base
from app.models.enums import (
    GoalType,
    GoalEventType,
    SportBackground,
    TrainingTimeOfDay,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
)

if TYPE_CHECKING:
    from app.models.athlete import Athlete


class TrainingPreferences(Base):
    __tablename__ = "training_preferences"
    __table_args__ = (
        Index(
            "ix_training_preferences_athlete_created_at",
            "athlete_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    goal_type: Mapped[Optional[GoalType]] = mapped_column(
        SAEnum(GoalType, native_enum=False, length=20),
    )
    goal_event_type: Mapped[Optional[GoalEventType]] = mapped_column(
        SAEnum(GoalEventType, native_enum=False, length=20),
    )
    custom_distance_km: Mapped[Optional[float]] = mapped_column(Float)
    goal_event_date: Mapped[Optional[date]] = mapped_column(Date)
    goal_description: Mapped[Optional[str]] = mapped_column(String(500))
    weekly_volume_hours: Mapped[Optional[float]] = mapped_column(Float)
    weekly_volume_km: Mapped[Optional[float]] = mapped_column(Float)
    years_structured_training: Mapped[Optional[float]] = mapped_column(Float)
    sport_background: Mapped[Optional[SportBackground]] = mapped_column(
        SAEnum(SportBackground, native_enum=False, length=20),
    )
    recent_injury: Mapped[Optional[bool]]
    weekly_schedule: Mapped[Optional[dict]] = mapped_column(JSONB)
    gps_source: Mapped[Optional[GpsSource]] = mapped_column(
        SAEnum(GpsSource, native_enum=False, length=20),
    )
    hr_source: Mapped[Optional[HrSource]] = mapped_column(
        SAEnum(HrSource, native_enum=False, length=20),
    )
    power_source: Mapped[Optional[PowerSource]] = mapped_column(
        SAEnum(PowerSource, native_enum=False, length=20),
    )
    primary_training_platform: Mapped[Optional[PrimaryTrainingPlatform]] = mapped_column(
        SAEnum(PrimaryTrainingPlatform, native_enum=False, length=20),
    )
    fitness_level: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    athlete: Mapped["Athlete"] = relationship(
        back_populates="training_preferences_versions",
    )