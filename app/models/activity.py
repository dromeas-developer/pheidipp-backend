import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Float,
    ForeignKey,
    Enum as SAEnum,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ActivityType, PerceivedEffort


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    activity_type: Mapped[ActivityType] = mapped_column(
        SAEnum(ActivityType, native_enum=False, length=20),
        default=ActivityType.RUNNING,
    )
    title: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    perceived_effort: Mapped[Optional[PerceivedEffort]] = mapped_column(
        SAEnum(PerceivedEffort, native_enum=False, length=20),
        nullable=True,
    )
    avg_heart_rate: Mapped[Optional[int]] = mapped_column(Integer)
    max_heart_rate: Mapped[Optional[int]] = mapped_column(Integer)
    avg_speed_m_per_s: Mapped[Optional[float]] = mapped_column(Float)
    max_speed_m_per_s: Mapped[Optional[float]] = mapped_column(Float)
    avg_power: Mapped[Optional[int]] = mapped_column(Integer)
    max_power: Mapped[Optional[int]] = mapped_column(Integer)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float)
    elevation_gain_meters: Mapped[Optional[float]] = mapped_column(Float)
    elevation_loss_meters: Mapped[Optional[float]] = mapped_column(Float)
    calories: Mapped[Optional[int]] = mapped_column(Integer)
    source: Mapped[Optional[str]] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Future extension point for activity_intervals / activity_segments
    athlete: Mapped["Athlete"] = relationship(back_populates="activities")
