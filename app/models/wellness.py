import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    String,
    DateTime,
    Date,
    Integer,
    Float,
    ForeignKey,
    text,
    func,
    Enum as SAEnum,
)
from sqlalchemy import UniqueConstraint as UC
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import WellnessSource

if TYPE_CHECKING:
    from app.models.athlete import Athlete


class AthleteWellness(Base):
    __tablename__ = "athlete_wellness"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    sleep_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_light: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_deep: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_rem: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sleep_awake: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    resting_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hrv: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[WellnessSource] = mapped_column(
        SAEnum(WellnessSource, native_enum=False, length=20),
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="wellness_metrics")

    __table_args__ = (
        UC("athlete_id", "metric_date", name="uq_athlete_wellness_date"),
    )
