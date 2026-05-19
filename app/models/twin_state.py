import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    UUID,
    Float,
    Text,
    DateTime,
    ForeignKey,
    func,
    CheckConstraint,
    Enum as SAEnum,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TwinTrigger, ConfidenceLevel, DataTier

if TYPE_CHECKING:
    from app.models.athlete import Athlete
    from app.models.athlete_preferences import AthletePreferences


class TwinState(Base):
    __tablename__ = "twin_states"

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
    athlete_preferences_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athlete_preferences.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger: Mapped[TwinTrigger] = mapped_column(
        SAEnum(TwinTrigger, native_enum=False, length=30),
        nullable=False,
    )
    confidence_level: Mapped[ConfidenceLevel] = mapped_column(
        SAEnum(ConfidenceLevel, native_enum=False, length=10),
        nullable=False,
        default=ConfidenceLevel.LOW,
    )
    data_tier: Mapped[DataTier] = mapped_column(
        SAEnum(DataTier, native_enum=False, length=10),
        nullable=False,
    )
    fitness_score: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    max_hr_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    lt1_hr_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    lt2_hr_estimate: Mapped[float] = mapped_column(Float, nullable=False)
    lt1_pace_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    lt2_pace_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)
    structural_capacity_score: Mapped[float] = mapped_column(Float, nullable=False)
    fitness_time_constant: Mapped[float] = mapped_column(Float, nullable=False, default=42.0)
    fatigue_time_constant: Mapped[float] = mapped_column(Float, nullable=False, default=7.0)
    computation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    computation_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    athlete: Mapped["Athlete"] = relationship(
        back_populates="twin_states",
    )
    preferences: Mapped["AthletePreferences"] = relationship(
        back_populates="twin_states",
    )

    __table_args__ = (
        CheckConstraint(
            "fitness_score >= 0 AND fitness_score <= 100",
            name="ck_twin_states_fitness_score_range",
        ),
        CheckConstraint(
            "max_hr_estimate >= 140 AND max_hr_estimate <= 220",
            name="ck_twin_states_max_hr_range",
        ),
        CheckConstraint(
            "fatigue_score >= 0",
            name="ck_twin_states_fatigue_non_negative",
        ),
        CheckConstraint(
            "structural_capacity_score >= 0 AND structural_capacity_score <= 1",
            name="ck_twin_states_structural_capacity_range",
        ),
    )