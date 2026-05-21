import uuid
from datetime import date, datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String,
    Float,
    Integer,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    text,
    func,
    Index,
    CheckConstraint,
    Enum as SAEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import GoalType, GoalEventType, GoalStatus

if TYPE_CHECKING:
    from app.models.athlete import Athlete
    from app.models.training_plan import TrainingPlan


class TrainingBlock(Base):
    __tablename__ = "training_blocks"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, server_default=text("gen_random_uuid()")
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Goal definition — immutable after creation
    goal_type: Mapped[Optional[GoalType]] = mapped_column(
        SAEnum(GoalType, native_enum=False, length=30), nullable=True
    )
    goal_event_type: Mapped[Optional[GoalEventType]] = mapped_column(
        SAEnum(GoalEventType, native_enum=False, length=20), nullable=True
    )
    goal_event_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    goal_event_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    goal_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    custom_distance_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Bootstrap snapshot — captured at block creation, feeds twin initialisation
    # These are point-in-time estimates, not updated after creation
    weekly_volume_hours: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weekly_volume_km: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fitness_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1–5
    recent_injury: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    # Lifecycle — the only field routinely updated after creation
    status: Mapped[GoalStatus] = mapped_column(
        SAEnum(GoalStatus, native_enum=False, length=20),
        nullable=False,
        default=GoalStatus.ACTIVE,
        server_default="active",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="training_blocks")
    training_plans: Mapped[list["TrainingPlan"]] = relationship(
        back_populates="training_block",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # DB-level domain invariants
        CheckConstraint(
            "fitness_level >= 1 AND fitness_level <= 5",
            name="ck_training_blocks_fitness_level_range",
        ),
        CheckConstraint(
            "custom_distance_km > 0",
            name="ck_training_blocks_distance_positive",
        ),
        CheckConstraint(
            "weekly_volume_hours >= 0",
            name="ck_training_blocks_volume_hours_non_negative",
        ),
        CheckConstraint(
            "weekly_volume_km >= 0",
            name="ck_training_blocks_volume_km_non_negative",
        ),
        Index("ix_training_blocks_athlete_status", "athlete_id", "status"),
        Index("ix_training_blocks_athlete_created_at", "athlete_id", "created_at"),
    )