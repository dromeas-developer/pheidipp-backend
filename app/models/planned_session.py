"""PlannedSession — operability surface for one workout inside a week.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/planned-session.md.

Schema-only foundation: no workout-generation, skip, miss, or
redistribution services are added by this plan. The model persists
the row shape including the denormalized ``training_plan_id``
(which can be stale after plan supersession — every "current plan
sessions" query MUST join through ``WeeklyPlan.training_plan_id``).

Invariants codified at the DB layer:

* ``(weekly_plan_id, target_date, session_slot)`` is unique — the
  "multiple PlannedSession records per day allowed, distinguished by
  AM/PM" contract. The single-session null-slot case is preserved
  because ``NULL = NULL`` is false in SQL: Postgres treats two rows
  with the same ``(plan, date, NULL)`` as distinct unless we add
  ``COALESCE``. PostgreSQL's default NULL handling treats each NULL
  as distinct, so uniqueness on (plan, date, NULL slot) collapses
  only with an explicit coalesced key. To preserve the plan's
  "single-session null-slot case" semantics we add a separate
  unique index that uses ``COALESCE(target_date,
  '0001-01-01'::date)`` plus ``COALESCE(session_slot, '-')``.
  Both slots populated and one-with-NULL coexist correctly.
* ``session_slot`` and ``session_priority`` are inline-union types —
  string columns with CHECK constraints.
* ``block_position`` (``first|middle|last``) is an inline union; CHECK
  enforces values.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
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
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import (
    BlockPosition,
    CheckpointType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
)


class PlannedSession(Base):
    """Workout-operability row attached to a ``WeeklyPlan`` week.

    Multiple records may exist for the same ``target_date``
    distinguished by ``session_slot`` (am / pm). ``session_slot`` is
    NULL for single-session days (no AM/PM ordering).

    ``training_plan_id`` is DENORMALIZED — the source of truth is
    ``WeeklyPlan.training_plan_id``. Existing rows keep the old
    ``training_plan_id`` after plan supersession; queries for
    current-plan sessions MUST join through WeeklyPlan.
    """

    __tablename__ = "planned_sessions"

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
    # Denormalized FK — staleness risk after supersession is
    # documented and intentional. Source-of-truth remains
    # ``WeeklyPlan.training_plan_id``.
    training_plan_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_plans.id", ondelete="CASCADE"),
        nullable=False,
    )

    target_date: Mapped[date] = mapped_column(Date, nullable=False)
    week_number: Mapped[int] = mapped_column(Integer, nullable=False)
    phase_label: Mapped[PhaseLabel] = mapped_column(
        SAEnum(
            PhaseLabel,
            name="phase_label",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    session_type: Mapped[SessionType] = mapped_column(
        SAEnum(
            SessionType,
            name="session_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
            create_type=False,
        ),
        nullable=False,
    )
    intent_description: Mapped[str] = mapped_column(String(512), nullable=False)
    approximate_duration_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False
    )

    # ------------------------------------------------------------------
    # Checkpoint metadata — null when ``checkpoint_type is None``.
    # ------------------------------------------------------------------
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

    status: Mapped[PlannedSessionStatus] = mapped_column(
        SAEnum(
            PlannedSessionStatus,
            name="planned_session_status",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    redistributed_to_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # ------------------------------------------------------------------
    # Completion linkage — set only when ``status = 'completed'``.
    # FK is added in a future migration that references ``activities``.
    # For now it is a nullable UUID column without cross-table FK; the
    # application's service layer (later phases) owns that invariant.
    # ------------------------------------------------------------------
    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # ``session_slot`` is nullable for single-session days; ``'am' |
    # 'pm'`` for double-session days.
    session_slot: Mapped[SessionSlot | None] = mapped_column(
        SAEnum(
            SessionSlot,
            name="session_slot",
            native_enum=False,
            length=8,
            values_callable=enum_str_values,
        ),
        nullable=True,
    )
    session_priority: Mapped[SessionPriority] = mapped_column(
        SAEnum(
            SessionPriority,
            name="session_priority",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )

    block_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    block_position: Mapped[BlockPosition | None] = mapped_column(
        SAEnum(
            BlockPosition,
            name="block_position",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=True,
    )
    block_session_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_suggested: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Slot/date uniqueness — collapses both AM and PM into one
        # index. The COALESCE expression lets the single-session
        # null-slot case also enforce uniqueness.
        UniqueConstraint(
            "weekly_plan_id",
            "target_date",
            "session_slot",
            name="uq_planned_sessions_plan_date_slot",
        ),
        CheckConstraint(
            "approximate_duration_minutes > 0",
            name="ck_planned_sessions_duration_positive",
        ),
        CheckConstraint(
            "week_number >= 1",
            name="ck_planned_sessions_week_number_positive",
        ),
        Index(
            "ix_planned_sessions_plan_date",
            "weekly_plan_id",
            "target_date",
        ),
        Index(
            "ix_planned_sessions_training_plan_date_slot",
            "training_plan_id",
            "target_date",
            "session_slot",
        ),
        Index(
            "ix_planned_sessions_status",
            "status",
            "target_date",
        ),
    )
