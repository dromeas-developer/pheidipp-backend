"""TrainingPlan — generated periodised training structure for a goal.

Implements the Phase-1.2b/1.2c schema contract from
docs/architecture/01-entities/training-plan.md and wires the
deferred ``twin_state_id`` foreign key now that ``twin_states``
exists.
"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import TrainingPlanStatus


class TrainingPlan(Base):
    """Periodised training structure owned by a parent ``TrainingGoal``.

    The plan carries:

    * ``phase_definitions`` — the adaptation strategy per phase.
    * ``phases_summary`` — ordered list of ``PhaseDescriptor``-shaped
      objects (label, start/end date, weeks, primary focus,
      weekly_session_count). Stored as JSONB.
    * ``weekly_distributions`` — derived from the phase definitions
      by the deterministic expansion layer.
    * ``checkpoint_schedule`` — ``CheckpointDescriptor[]`` of every
      checkpoint for the plan.
    * ``strategic_rationale`` — ``StrategicRationale`` shape, null for
      ``fitness_improvement`` / ``maintenance`` / ``recovery`` modes.
      Stored as JSONB.

    ``twin_state_id`` records which twin version produced this plan.
    """

    __tablename__ = "training_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    training_goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable UUID column pointing at the twin version that produced
    # this plan. ``ondelete=SET NULL`` matches the column's nullability
    # — orphaning a twin state must not cascade-delete the plan. The
    # explicit name matches the contract asserted by the Phase-1.2c
    # test pack (``fk_training_plans_twin_state``).
    twin_state_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey(
            "twin_states.id", ondelete="SET NULL", name="fk_training_plans_twin_state"
        ),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Top-level plan shape.
    # ------------------------------------------------------------------
    # ``phases_summary`` carries ``PhaseDescriptor[]``: label,
    # start/end date, weeks, primary_focus, weekly_session_count.
    phases_summary: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # ``phase_definitions`` carries ``PhaseDefinition[]``: the
    # adaptation-strategy per phase.
    phase_definitions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # ``weekly_distributions`` carries ``WeeklyDistribution[]``: the
    # deterministic-expansion output for the plan.
    weekly_distributions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    status: Mapped[TrainingPlanStatus] = mapped_column(
        SAEnum(
            TrainingPlanStatus,
            name="training_plan_status",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Optional strategic rationale and checkpoint schedule.
    # Both are JSONB so the architecture shape can be enforced at the
    # application layer without database migration churn.
    # ------------------------------------------------------------------
    strategic_rationale: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    checkpoint_schedule: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    __table_args__ = (
        # Active / superseded lookup — find the current plan for a goal.
        Index(
            "ix_training_plans_goal_status",
            "training_goal_id",
            "status",
        ),
        # Reverse-lookup TwinState → plans via the FK target.
        Index("ix_training_plans_twin_state", "twin_state_id"),
    )
