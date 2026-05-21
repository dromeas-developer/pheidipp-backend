import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    ForeignKey,
    DateTime,
    Enum as SAEnum,
    Text,
    text,
    func,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TrainingPlanStatus

if TYPE_CHECKING:
    from app.models.athlete import Athlete
    from app.models.training_block import TrainingBlock
    from app.models.planned_session import PlannedSession


class TrainingPlan(Base):
    __tablename__ = "training_plans"

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
    training_block_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_blocks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[TrainingPlanStatus] = mapped_column(
        SAEnum(TrainingPlanStatus, native_enum=False, length=20),
        default=TrainingPlanStatus.ACTIVE,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    generation_metadata: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    plan_rationale: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="training_plans")
    training_block: Mapped[Optional["TrainingBlock"]] = relationship(
        back_populates="training_plans"
    )
    planned_sessions: Mapped[list["PlannedSession"]] = relationship(
        back_populates="training_plan",
        cascade="all, delete-orphan",
        order_by="PlannedSession.scheduled_date.asc()",
    )

    __table_args__ = (
        Index(
            "ix_training_plans_active_per_athlete",
            "athlete_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_training_plans_athlete_created_at", "athlete_id", "created_at"),
    )