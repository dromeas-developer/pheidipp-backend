"""GeneratedWorkout — day-of workout for a PlannedSession.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/generated-workout.md.

Schema-only foundation: no ``WorkoutGenerationAgent``,
``WellnessModifierService``, weather adjustment, or
``today`` / ``generate-workout`` API endpoints are added by this
plan. The model persists the row shape including the two-column
``TargetSet`` JSONB shapes (theoretical / adjusted) and the
``recovery_modifier_level`` annotation that drives the at-a-glance
modifier chip.

Invariants codified at the DB layer:

* GeneratedWorkout is append-only — no ``update()`` / ``delete()``
  methods exposed by the future repository (Phase 1.5b).
* One row per ``(planned_session_id, generation_date)`` — the
  partial unique constraint enforces "exactly one workout per
  planned-session per generation day" which is the
  ``(planned_session_id, generation_date)`` idempotency contract
  documented in the architecture doc.
* ``theoretical_targets`` and ``adjusted_targets`` are both always
  written, even when identical (GREEN modifier, no weather). The
  two columns are NOT NULL — a regeneration that produced a row
  with one of them null is a programming error blocked at insert.
* ``twin_state_id`` captures which twin version produced the
  workout. Recalibration does NOT retroactively update an existing
  ``GeneratedWorkout`` row; that decision is owned by Phase-1.5b
  service code.
* ``recovery_modifier_level`` defaults to ``green`` per the
  architecture spec; ``amber`` / ``red`` are written by
  ``WellnessModifierService``. The default is set via
  ``server_default`` so inserts from a future service that forgets
  to specify the modifier are still valid.
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
    Text,
    func,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import RecoveryModifierLevel


class GeneratedWorkout(Base):
    """One day-of workout record per ``(planned_session_id, generation_date)``.

    The two-column target structure (``theoretical_targets`` /
    ``adjusted_targets``) backs the two-column display mandated by
    the daily view vision doc — both fields always populated,
    identical values allowed. The ``WorkoutGenerationAgent`` in
    Phase 1.5b is the only writer.
    """

    __tablename__ = "generated_workouts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    planned_session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("planned_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    twin_state_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin_states.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Two-column target structure — both must always be written.
    # `TargetSet` is the JSONB shape: ``{targets: WorkoutTarget[],
    # description: string}``.
    # ------------------------------------------------------------------
    theoretical_targets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    adjusted_targets: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    recovery_modifier_level: Mapped[RecoveryModifierLevel] = mapped_column(
        SAEnum(
            RecoveryModifierLevel,
            name="recovery_modifier_level",
            native_enum=False,
            length=8,
            values_callable=enum_str_values,
            create_type=False,
        ),
        nullable=False,
        default=RecoveryModifierLevel.GREEN,
        server_default=RecoveryModifierLevel.GREEN.value,
    )
    recovery_modifier_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    generation_date: Mapped[date] = mapped_column(Date, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Idempotency — one workout per planned-session per
        # generation day. The unique constraint supports the
        # "second call returns existing workout (200, not 201)"
        # contract from the architecture doc.
        UniqueConstraint(
            "planned_session_id",
            "generation_date",
            name="uq_generated_workouts_planned_session_generation_date",
        ),
        # Reverse-lookup from the twin-state that produced this
        # workout — supports the "twin_recalibrated" consumer that
        # decides whether to rebuild today vs. wait.
        Index("ix_generated_workouts_twin_state", "twin_state_id"),
        # Today's-view fast path — most frequent read scan.
        Index(
            "ix_generated_workouts_planned_session_generated",
            "planned_session_id",
            "generated_at",
        ),
        # The two target-set columns must always be non-null JSON
        # objects — ``theoretical_targets`` and ``adjusted_targets``
        # are mandatory, never JSON ``null``. A CHECK on the
        # ``jsonb_typeof`` ensures insert-time shape.
        CheckConstraint(
            "jsonb_typeof(theoretical_targets) = 'object' AND "
            "jsonb_typeof(adjusted_targets) = 'object'",
            name="ck_generated_workouts_targets_are_objects",
        ),
        # ``recovery_modifier_level`` is the closed enum; the SAEnum
        # already constrains the string set, but the explicit CHECK
        # mirrors the architecture inline-union annotation.
        CheckConstraint(
            "recovery_modifier_level IN ('green', 'amber', 'red')",
            name="ck_generated_workouts_recovery_modifier_level_valid",
        ),
    )
