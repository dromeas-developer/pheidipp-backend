"""Checkpoint — one planned assessment point inside a training plan.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/checkpoint.md.

Schema-only foundation: no creation, completion, or replan-handling
services are added by this plan. The model persists the row shape
including the one-to-one FK to ``PlannedSession`` and the atomic
completion fields.

Invariants codified at the DB layer:

* ``planned_session_id`` is UNIQUE and NOT NULL — one checkpoint per
  planned session.
* No redundant ``training_plan_id`` — derivation goes through
  ``PlannedSession → WeeklyPlan → TrainingPlan``.
* Trajectory-validation status and "trigger" snapshot fields are
  serialised JSONB / scalar strings because they are reserved for
  later target-performance flows; the partial CHECK keeps the
  inline-union set bounded.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import CheckpointStatus, CheckpointType


class Checkpoint(Base):
    """One checkpoint record attached to the planned session that IS
    the checkpoint.

    Atomic-completion invariant: ``metric_updated``,
    ``confidence_changed``, ``replan_triggered`` and ``completed_at``
    are set together when ``status`` transitions to ``completed``.
    Service-layer code in a later phase owns that atomicity; the
    schema allows ``null`` for those fields until completion.

    ``trajectory_status`` is set only on ``target_performance`` plans
    with coach-driven trajectory tracking. Inline-union values
    ('ahead' | 'on_track' | 'behind' | 'at_risk') are enforced by
    CHECK constraint.

    ``secondary_metrics`` is stored as ``ARRAY(String)`` per the
    architecture schema (``secondary_metrics: string[]``).
    """

    __tablename__ = "checkpoints"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # One-to-one FK — strict uniqueness + not-null enforced at DB
    # level via the unique index below.
    planned_session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("planned_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # ------------------------------------------------------------------
    # Checkpoint definition.
    # ------------------------------------------------------------------
    type: Mapped[CheckpointType] = mapped_column(
        SAEnum(
            CheckpointType,
            name="checkpoint_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    target_metric: Mapped[str] = mapped_column(String(128), nullable=False)
    secondary_metrics: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list, server_default="{}"
    )

    twin_update_expected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    replan_trigger: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ------------------------------------------------------------------
    # Lifecycle.
    # ------------------------------------------------------------------
    status: Mapped[CheckpointStatus] = mapped_column(
        SAEnum(
            CheckpointStatus,
            name="checkpoint_status",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Completion fields — set atomically when ``status → 'completed'``.
    # ------------------------------------------------------------------
    metric_updated: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    confidence_changed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    replan_triggered: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ------------------------------------------------------------------
    # Trajectory validation — target_performance mode only.
    # ------------------------------------------------------------------
    trajectory_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    proposal: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        # Type/status combination lookup — "all upcoming calibration
        # checkpoints" type filter scan.
        Index(
            "ix_checkpoints_type_status",
            "type",
            "status",
        ),
        # Tighter pre-existing unique on planned_session_id is also
        # surfaced as a named index for downstream intent.
        Index(
            "ix_checkpoints_planned_session",
            "planned_session_id",
        ),
        CheckConstraint(
            "trajectory_status IS NULL OR "
            "trajectory_status IN ('ahead', 'on_track', 'behind', 'at_risk')",
            name="ck_checkpoints_trajectory_status_valid",
        ),
        # Status must be one of three canonical values.
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'skipped')",
            name="ck_checkpoints_status_valid",
        ),
    )
