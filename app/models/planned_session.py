import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    Date,
    DateTime,
    Boolean,
    Integer,
    ForeignKey,
    Enum as SAEnum,
    text,
    func,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import SessionType, PhysiologicalIntent, TrainingPhase

if TYPE_CHECKING:
    from app.models.training_plan import TrainingPlan


class PlannedSession(Base):
    __tablename__ = "planned_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    training_plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scheduled_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    session_type: Mapped[SessionType] = mapped_column(
        SAEnum(SessionType, native_enum=False, length=30),
        nullable=False,
    )
    dominant_physiological_intent: Mapped[PhysiologicalIntent] = mapped_column(
        SAEnum(PhysiologicalIntent, native_enum=False, length=30),
        nullable=False,
    )
    target_duration_minutes: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    is_key_session: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    week_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    phase: Mapped[TrainingPhase] = mapped_column(
        SAEnum(TrainingPhase, native_enum=False, length=20),
        nullable=False,
    )
    generation_metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    training_plan: Mapped["TrainingPlan"] = relationship(
        back_populates="planned_sessions"
    )

    __table_args__ = (
        Index("ix_planned_sessions_plan_date", "training_plan_id", "scheduled_date"),
        Index("ix_planned_sessions_plan_week", "training_plan_id", "week_number"),
    )