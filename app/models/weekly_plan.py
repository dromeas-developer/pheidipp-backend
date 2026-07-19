"""WeeklyPlan — single-week training schedule within a TrainingPlan.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/weekly-plan.md.

Schema-only foundation: no weekly-synthesis, pre-week-review or
missed-session-sweep services in this plan. The model persists the
row shape (one per week per TrainingPlan) so Phase-1.2b's migration
can bring up the table while plan-agent services land in later
phases.

Invariants codified at the DB layer:

* ``weekly_plans(training_plan_id, week_number)`` is unique — the
  "one WeeklyPlan per week per TrainingPlan" contract.
* ``WeeklySession.planned_session_id`` is unique when non-null and
  nullable otherwise. Sessions array immutability once
  ``status = active`` is enforced at the application layer in later
  phases.
"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import (
    CheckpointType,
    SessionType,
    WeeklyPlanStatus,
)


class WeeklyPlan(Base):
    """One plan for a single ``(training_plan_id, week_number)`` week.

    Carries:

    * ``adjusted_intent`` — the post-pre-week-review AdjustedWeeklyIntent
      shape (methodology, target_distribution, objectives,
      session_count, adjustment flags). JSONB for shape flexibility.
    * Execution summary counters (completed / missed / skipped /
      accumulated fatigue / doubles count) — updated by session
      lifecycle services later.
    * ``week_starts_at`` / ``week_ends_at`` — inclusive date bounds.
    """

    __tablename__ = "weekly_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    training_plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)

    adjusted_intent: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    status: Mapped[WeeklyPlanStatus] = mapped_column(
        SAEnum(
            WeeklyPlanStatus,
            name="weekly_plan_status",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Execution summary — populated as sessions complete.
    # ------------------------------------------------------------------
    sessions_completed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    sessions_missed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    sessions_skipped: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    accumulated_fatigue_delta: Mapped[float] = mapped_column(
        nullable=False, default=0.0, server_default="0"
    )
    doubles_days_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    week_starts_at: Mapped[date] = mapped_column(Date, nullable=False)
    week_ends_at: Mapped[date] = mapped_column(Date, nullable=False)

    __table_args__ = (
        # Architecture invariant: one WeeklyPlan per week per TrainingPlan.
        UniqueConstraint(
            "training_plan_id",
            "week_number",
            name="uq_weekly_plans_plan_week",
        ),
        # Execution counters must be non-negative.
        CheckConstraint(
            "sessions_completed >= 0 AND sessions_missed >= 0 AND "
            "sessions_skipped >= 0",
            name="ck_weekly_plans_session_counters_non_negative",
        ),
        CheckConstraint(
            "doubles_days_count >= 0",
            name="ck_weekly_plans_doubles_days_count_non_negative",
        ),
        # ``week_number`` is 1-indexed within the plan and positive.
        CheckConstraint(
            "week_number >= 1",
            name="ck_weekly_plans_week_number_positive",
        ),
        Index("ix_weekly_plans_plan_status", "training_plan_id", "status"),
    )


class WeeklySession(Base):
    """Single session scheduled for a date inside a ``WeeklyPlan``.

    Marked as a checkpoint via ``is_checkpoint = true`` and a
    non-null ``checkpoint_type``. ``planned_session_id`` becomes
    non-null when the workout generation agent creates a
    ``PlannedSession`` for this session.

    Block membership is set by the weekly synthesis agent for
    compound-stimulation adaptation windows.
    """

    __tablename__ = "weekly_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    weekly_plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("weekly_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    session_type: Mapped[SessionType] = mapped_column(
        SAEnum(
            SessionType,
            name="session_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    intent_description: Mapped[str] = mapped_column(String(512), nullable=False)
    approximate_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    is_checkpoint: Mapped[bool] = mapped_column(
        nullable=False, default=False, server_default="false"
    )
    checkpoint_type: Mapped[CheckpointType | None] = mapped_column(
        SAEnum(
            CheckpointType,
            name="checkpoint_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
            create_type=False,
        ),
        nullable=True,
    )
    checkpoint_metric: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # ------------------------------------------------------------------
    # Lifecycle.
    # ------------------------------------------------------------------
    # Inline-union: 'scheduled' | 'completed' | 'skipped' | 'missed'
    # — string column with CHECK enforcement. The architecture
    # documents this as an inline union distinct from
    # ``WeeklyPlanStatus``.
    status: Mapped[str] = mapped_column(Text, nullable=False)

    # Lazy FK to ``planned_sessions``. Unique when non-null so one
    # WeeklySession maps to at most one PlannedSession.
    planned_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True, unique=True
    )

    block_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # 'first' | 'middle' | 'last' — inline union; CHECK constraint
    # enforces membership.
    block_position: Mapped[str | None] = mapped_column(String(16), nullable=True)
    block_session_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'skipped', 'missed')",
            name="ck_weekly_sessions_status_valid",
        ),
        CheckConstraint(
            "block_position IS NULL OR block_position IN ('first', 'middle', 'last')",
            name="ck_weekly_sessions_block_position_valid",
        ),
        CheckConstraint(
            "approximate_duration_minutes > 0",
            name="ck_weekly_sessions_duration_positive",
        ),
        Index("ix_weekly_sessions_plan_date", "weekly_plan_id", "target_date"),
        Index("ix_weekly_sessions_plan", "weekly_plan_id"),
    )
