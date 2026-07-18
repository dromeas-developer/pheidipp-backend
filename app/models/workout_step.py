"""WorkoutStep — one segment inside a ``GeneratedWorkout``.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/workout-step.md.

Schema-only foundation: no ``WorkoutGenerationAgent`` /
``SegmentationService`` / ``ExecutionAnalysisService`` is added by
this plan. The model persists the row shape including the
``physiological_intent`` (never null), the ``session_purpose``
(default ``general``), and the JSONB ``target`` carrying the
``WorkoutTarget`` shape with primary range, optional fallback, and
plain-English description.

Invariants codified at the DB layer:

* ``physiological_intent IS NOT NULL`` — every step has an intent
  including warmup and cooldown.
* ``(generated_workout_id, step_order)`` is unique — step_order is
  1-indexed and unique within a workout; the future
  ``get_steps_for(workout)`` query orders by ``step_order`` ASC.
* ``step_type`` is one of ``StepType`` (warmup / work / recovery /
  cooldown). Mapping to ``physiological_intent`` is owned by
  ``SESSION_INTENT_MAP`` at the application layer.
* ``session_purpose`` defaults to ``general``. ``race_specific`` is
  NOT a ``SessionType``; ``calibration`` annotates test sessions.
* Steps are append-only — no ``update()`` / ``delete()`` in the
  future Phase-1.5b repository.
* ``duration_seconds`` is required and positive when non-null
  (interval work has a duration; warmup / cooldown can be null for
  some workout variants).
* Numeric target ranges are nullable for Tier 5-6 athletes; the
  ``description`` field is always non-null and non-empty.
"""

from __future__ import annotations

from typing import Any

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import (
    PhysiologicalIntent,
    SessionPurpose,
    SessionType,
    StepType,
)


class WorkoutStep(Base):
    """One ordered segment inside a GeneratedWorkout.

    Carries the three-layer hierarchy ``session_type`` /
    ``physiological_intent`` / ``session_purpose``, the
    range-bearing ``WorkoutTarget`` JSONB, the duration, and a
    plain-English description. The ``physiological_intent`` is the
    prescribed state compared against ``PhysiologicalSegment``'s
    inferred state at execution analysis time.
    """

    __tablename__ = "workout_steps"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    generated_workout_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("generated_workouts.id", ondelete="CASCADE"),
        nullable=False,
    )

    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[StepType] = mapped_column(
        SAEnum(
            StepType,
            name="step_type",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # Three-layer hierarchy.
    # ``physiological_intent`` is the primary intent signal and is
    # NEVER null.
    # ``session_purpose`` defaults to ``general``.
    # ------------------------------------------------------------------
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
    physiological_intent: Mapped[PhysiologicalIntent] = mapped_column(
        SAEnum(
            PhysiologicalIntent,
            name="physiological_intent",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    session_purpose: Mapped[SessionPurpose] = mapped_column(
        SAEnum(
            SessionPurpose,
            name="session_purpose",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
        default=SessionPurpose.GENERAL,
        server_default=SessionPurpose.GENERAL.value,
    )

    # ------------------------------------------------------------------
    # Range-based target — ``WorkoutTarget`` JSONB shape with
    # ``signal_type``, ``primary``, ``fallback``, ``description``.
    # Numeric ranges nullable for Tier 5-6 athletes; ``description``
    # must always be present so plain-language coaching is preserved.
    # ------------------------------------------------------------------
    target: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    duration_seconds: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        # ``(generated_workout_id, step_order)`` uniqueness — one
        # step per order position per workout.
        UniqueConstraint(
            "generated_workout_id",
            "step_order",
            name="uq_workout_steps_generated_workout_step_order",
        ),
        # Reverse-lookup / ordered read.
        Index(
            "ix_workout_steps_generated_workout_order",
            "generated_workout_id",
            "step_order",
        ),
        # ``step_order`` is 1-indexed and positive.
        CheckConstraint(
            "step_order >= 1",
            name="ck_workout_steps_step_order_positive",
        ),
        # ``duration_seconds`` is non-negative.
        CheckConstraint(
            "duration_seconds IS NULL OR duration_seconds >= 0",
            name="ck_workout_steps_duration_non_negative",
        ),
        # ``description`` is always present and non-empty.
        CheckConstraint(
            "length(description) > 0",
            name="ck_workout_steps_description_non_empty",
        ),
    )
