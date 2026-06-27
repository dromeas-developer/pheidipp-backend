"""Unit tests for the ``WorkoutStep`` declarative surface (no DB).

Phase-1.2c introduces the ``WorkoutStep`` schema — one ordered segment
inside a ``GeneratedWorkout``. Carries the three-layer hierarchy
(``session_type`` / ``physiological_intent`` / ``session_purpose``),
the range-bearing ``WorkoutTarget`` JSONB, the duration, and a
plain-English description.

Invariants pinned here:

* Append-only — no ``update()`` / ``delete()`` helpers on the mapper.
* ``(generated_workout_id, step_order)`` is UNIQUE — one step per
  order position per workout.
* ``physiological_intent`` is NOT NULL — the primary intent signal.
* ``session_purpose`` defaults to ``general``.
* ``target`` JSONB is NOT NULL — the WorkoutTarget shape (primary
  range, fallback, description).
* ``description`` is non-empty (CHECK).
* ``step_order`` is positive (>= 1) (CHECK).
* ``duration_seconds`` is non-negative (CHECK).

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/workout-step.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    Integer,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.enums import (
    PhysiologicalIntent,
    SessionPurpose,
    SessionType,
    StepType,
)
from app.models.workout_step import WorkoutStep

from tests.utils.model_helpers import (
    get_columns,
    get_unique_constraints,
    get_foreign_keys_referencing,
    get_indexes,
    get_check_constraints,
    get_check_text,
    get_server_default_text,
    get_enum_values,
)





# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestWorkoutStepRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(WorkoutStep)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_generated_workout_id_required_uuid(self) -> None:
        col = get_columns(WorkoutStep)["generated_workout_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_generated_workout_id_cascade_fk_to_generated_workouts(
        self,
    ) -> None:
        """GeneratedWorkout FK ON DELETE CASCADE — workout steps are
        wiped when the parent workout is removed."""
        fks = get_foreign_keys_referencing(WorkoutStep, "generated_workout_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "generated_workouts"
        assert fk.ondelete == "CASCADE"

    def test_step_order_required_integer(self) -> None:
        col = get_columns(WorkoutStep)["step_order"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_step_type_required_enum(self) -> None:
        col = get_columns(WorkoutStep)["step_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, StepType))
        assert actual == ["cooldown", "recovery", "warmup", "work"]

    def test_session_type_required_enum(self) -> None:
        col = get_columns(WorkoutStep)["session_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, SessionType))
        expected = sorted(
            [
                "cross_training",
                "drills_mobility",
                "easy_run",
                "fartlek",
                "hill_repeats",
                "long_run",
                "medium_long_run",
                "optional_run",
                "recovery_run",
                "rest",
                "steady_state",
                "strides",
                "tempo",
                "test_session",
                "threshold",
                "vo2max",
            ]
        )
        assert actual == expected

    def test_physiological_intent_required_enum(self) -> None:
        """``physiological_intent`` is NOT NULL — the primary intent
        signal that gets compared against the inferred state at
        execution analysis time. Every step (warmup, cooldown, work)
        must declare one."""
        col = get_columns(WorkoutStep)["physiological_intent"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, PhysiologicalIntent))
        expected = sorted(
            [
                "high_aerobic",
                "low_aerobic",
                "neuromuscular",
                "recovery",
                "threshold",
                "vo2max",
            ]
        )
        assert actual == expected

    def test_session_purpose_required_enum_default_general(self) -> None:
        col = get_columns(WorkoutStep)["session_purpose"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, SessionPurpose))
        assert actual == ["calibration", "general", "race_specific"]
        # server_default is the string literal "general".
        assert col.server_default is not None
        assert "general" in get_server_default_text(col)

    def test_target_required_jsonb(self) -> None:
        """``target`` is NOT NULL — always populated with the
        WorkoutTarget shape (primary range, fallback, description).
        Numeric ranges nullable for Tier 5-6 athletes; description
        is always non-empty (CHECK enforces it)."""
        col = get_columns(WorkoutStep)["target"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_duration_seconds_nullable_integer(self) -> None:
        """``duration_seconds`` is nullable — warmup / cooldown can
        be null for some workout variants. When present, the CHECK
        constraint enforces non-negative."""
        col = get_columns(WorkoutStep)["duration_seconds"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)

    def test_description_required_text(self) -> None:
        col = get_columns(WorkoutStep)["description"]
        assert col.nullable is False
        assert isinstance(col.type, Text)


# ---------------------------------------------------------------------------
# Unique constraint — (generated_workout_id, step_order).
# ---------------------------------------------------------------------------


class TestWorkoutStepStepOrderUniqueConstraint:
    """``(generated_workout_id, step_order)`` is UNIQUE — one step
    per order position per workout."""

    def test_step_order_unique_constraint_present(self) -> None:
        uniques = get_unique_constraints(WorkoutStep)
        matched = [
            u
            for u in uniques
            if tuple(col.key for col in u.columns)
            == ("generated_workout_id", "step_order")
            and getattr(u, "name", None)
            == "uq_workout_steps_generated_workout_step_order"
        ]
        assert matched, (
            "workout_steps must declare UNIQUE "
            "(generated_workout_id, step_order). "
            f"Got: {[(tuple(col.key for col in u.columns), getattr(u, 'name', None)) for u in uniques]}"
        )

    def test_step_order_unique_constraint_columns(self) -> None:
        uniques = get_unique_constraints(WorkoutStep)
        matched = [
            u
            for u in uniques
            if getattr(u, "name", None)
            == "uq_workout_steps_generated_workout_step_order"
        ]
        assert matched
        u = matched[0]
        assert tuple(col.key for col in u.columns) == (
            "generated_workout_id",
            "step_order",
        )


# ---------------------------------------------------------------------------
# CHECK constraints — step_order >= 1, duration >= 0, description non-empty.
# ---------------------------------------------------------------------------


class TestWorkoutStepStepOrderCheck:
    """``step_order`` is 1-indexed and positive."""

    def test_step_order_positive_check_present(self) -> None:
        checks = get_check_constraints(WorkoutStep)
        found = any(
            "step_order" in get_check_text(c)
            and ">=" in get_check_text(c)
            and "1" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "WorkoutStep must declare a CHECK constraint "
            "enforcing `step_order >= 1`."
        )


class TestWorkoutStepDurationCheck:
    """``duration_seconds`` is non-negative when present (NULL
    short-circuits)."""

    def test_duration_non_negative_check_present(self) -> None:
        checks = get_check_constraints(WorkoutStep)
        found = any(
            "duration_seconds" in get_check_text(c)
            and ">=" in get_check_text(c)
            and "is null" in get_check_text(c).lower()
            for c in checks
        )
        assert found, (
            "WorkoutStep must declare a CHECK constraint "
            "enforcing `duration_seconds IS NULL OR >= 0`."
        )


class TestWorkoutStepDescriptionCheck:
    """``description`` is always non-empty — plain-language coaching
    must never be blank."""

    def test_description_non_empty_check_present(self) -> None:
        checks = get_check_constraints(WorkoutStep)
        found = any(
            "length(description)" in get_check_text(c)
            and "> 0" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "WorkoutStep must declare a CHECK constraint "
            "rejecting empty description (length(description) > 0)."
        )


# ---------------------------------------------------------------------------
# Reverse-lookup / ordered read index.
# ---------------------------------------------------------------------------


class TestWorkoutStepOrderedReadIndex:
    """``ix_workout_steps_generated_workout_order`` on
    ``(generated_workout_id, step_order)`` supports the future
    ``get_steps_for(workout)`` repository contract — returns
    steps in execution order."""

    def test_ordered_read_index_present(self) -> None:
        indexes = get_indexes(WorkoutStep)
        assert "ix_workout_steps_generated_workout_order" in indexes
        idx = indexes["ix_workout_steps_generated_workout_order"]
        columns = {c.key for c in idx.columns}
        assert columns == {"generated_workout_id", "step_order"}


# ---------------------------------------------------------------------------
# Append-only contract — no update()/delete() helpers on the mapper.
# ---------------------------------------------------------------------------


class TestWorkoutStepAppendOnlyContract:
    """WorkoutStep is append-only — the ``SegmentationService`` (later
    phase) writes rows but never mutates them."""

    def test_no_update_helper_methods(self) -> None:
        for attr_name in dir(WorkoutStep):
            if attr_name.startswith("__"):
                continue
            attr = getattr(WorkoutStep, attr_name, None)
            if callable(attr) and attr_name in (
                "update",
                "delete",
                "save",
                "merge",
                "upsert",
                "replace",
                "put",
                "patch",
            ):
                assert False, (
                    f"WorkoutStep must not expose a `{attr_name}` "
                    "method — the table is append-only."
                )

    def test_no_updated_at_column(self) -> None:
        """Append-only contract: ``updated_at`` would imply a
        mutation semantic the schema must not permit."""
        assert "updated_at" not in get_columns(WorkoutStep), (
            "WorkoutStep must not carry an `updated_at` column — "
            "rows are immutable after insert."
        )


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on WorkoutStep.
# ---------------------------------------------------------------------------


class TestWorkoutStepSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Soft-delete / mutation columns.
            "deleted_at",
            "is_deleted",
            "updated_at",
            # Twin / fitness fields.
            "twin_state_id",
            "fitness_score",
            "fatigue_score",
            "form",
            # Activity / completion tracking.
            "completed_at",
            "completed",
            "actual_duration_seconds",
            "actual_target",
            # Workout-level fields belong on GeneratedWorkout.
            "planned_session_id",
            "theoretical_targets",
            "adjusted_targets",
            "recovery_modifier_level",
            "generation_date",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(WorkoutStep), (
            f"WorkoutStep must not carry `{forbidden_field}`. "
            "Step row shape is restricted to workout linkage, "
            "three-layer hierarchy (session_type/physiological_intent/"
            "session_purpose), target JSONB, duration, description."
        )