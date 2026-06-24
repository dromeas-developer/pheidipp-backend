"""TrainingPlan — generated periodised training structure for a goal.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/training-plan.md.

Schema-only foundation: there is no plan generation, supersession, or
service-layer schedule logic in this plan. The model persists the
adapter-strategy structure (``phase_definitions``, ``weekly_distributions``,
``checkpoint_schedule``) so Phase-1.2b's migration can land the
shape without coupling to the generation pipeline.

Phase-1.2b deliverable deliberately defers the ``twin_state_id`` FK
to Phase-1.2c (when ``TwinState`` exists). The column is present in
this model — it is a nullable ``UUID`` — and the migration creates
the column without a foreign key. Phase-1.2c wires the FK.
"""

from __future__ import annotations

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

    ``twin_state_id`` is present now (so the schema records which
    twin version generated the plan) but its FK is DELAYED to
    Phase-1.2c when ``twin_states`` exists.
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
    # Nullable UUID column only. The FK to ``twin_states`` is added by
    # Phase-1.2c when that table exists. Adding it here would couple
    # this plan to a future sub-phase and break the head.
    twin_state_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )

    # ------------------------------------------------------------------
    # Top-level plan shape.
    # ------------------------------------------------------------------
    # ``phases_summary`` carries ``PhaseDescriptor[]``: label,
    # start/end date, weeks, primary_focus, weekly_session_count.
    phases_summary: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # ``phase_definitions`` carries ``PhaseDefinition[]``: the
    # adaptation-strategy per phase.
    phase_definitions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # ``weekly_distributions`` carries ``WeeklyDistribution[]``: the
    # deterministic-expansion output for the plan.
    weekly_distributions: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    # ------------------------------------------------------------------
    # Lifecycle.
    # ------------------------------------------------------------------
    status: Mapped[TrainingPlanStatus] = mapped_column(
        SAEnum(
            TrainingPlanStatus,
            name="training_plan_status",
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
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
    strategic_rationale: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    checkpoint_schedule: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )

    __table_args__ = (
        # Active / superseded lookup — find the current plan for a goal.
        Index(
            "ix_training_plans_goal_status",
            "training_goal_id",
            "status",
        ),
        # Reverse-lookup TwinState → plans using the (deferred) FK
        # target. Indexed even though the FK is added in Phase-1.2c.
        Index("ix_training_plans_twin_state", "twin_state_id"),
    )
