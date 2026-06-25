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
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
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


def _columns() -> dict[str, object]:
    return {column.key: column for column in WorkoutStep.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in WorkoutStep.__table__.indexes}


def _check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in WorkoutStep.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


def _unique_constraints() -> list[UniqueConstraint]:
    return [
        c
        for c in WorkoutStep.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def _foreign_keys_referencing(column_key: str) -> list[ForeignKey]:
    return [
        fk
        for fk in WorkoutStep.__table__.foreign_keys
        if fk.parent.name == column_key
    ]


def _check_text(check: CheckConstraint) -> str:
    """Return the SQL expression text of a CheckConstraint as a string.

    Shared helper across multiple test classes so that each class does
    not have to redefine it. SQLAlchemy exposes the constraint's
    expression via ``.expression`` (modern) or ``.sqltext`` (legacy) —
    this helper accepts either.
    """
    expr = getattr(check, "expression", None) or getattr(
        check, "sqltext", None
    )
    return str(expr) if expr is not None else ""


def _uq_constraint_columns(u: UniqueConstraint) -> tuple[str, ...]:
    """Return the column names of a UniqueConstraint as a tuple.

    SQLAlchemy ``UniqueConstraint`` does not expose a ``.get()`` method
    nor an ``u["column_names"]`` dict-style accessor — use ``c.columns``
    to iterate the column objects and ``col.key`` to get each name.
    """
    return tuple(col.key for col in u.columns)


def _uq_constraint_name(u: UniqueConstraint) -> str | None:
    """Return the named constraint identifier or ``None`` if anonymous.

    Mirrors the ``.name`` attribute of ``UniqueConstraint`` (None when
    the constraint was declared without an explicit ``name=``).
    """
    return getattr(u, "name", None)


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestWorkoutStepRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_generated_workout_id_required_uuid(self) -> None:
        col = _columns()["generated_workout_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_generated_workout_id_cascade_fk_to_generated_workouts(
        self,
    ) -> None:
        """GeneratedWorkout FK ON DELETE CASCADE — workout steps are
        wiped when the parent workout is removed."""
        fks = _foreign_keys_referencing("generated_workout_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "generated_workouts"
        assert fk.ondelete == "CASCADE"

    def test_step_order_required_integer(self) -> None:
        col = _columns()["step_order"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_step_type_required_enum(self) -> None:
        col = _columns()["step_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(StepType))
        assert actual == ["cooldown", "recovery", "warmup", "work"]

    def test_session_type_required_enum(self) -> None:
        col = _columns()["session_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(SessionType))
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
        col = _columns()["physiological_intent"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(PhysiologicalIntent))
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
        col = _columns()["session_purpose"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(SessionPurpose))
        assert actual == ["calibration", "general", "race_specific"]
        # server_default is the string literal "general".
        assert col.server_default is not None
        assert "general" in str(col.server_default.arg)

    def test_target_required_jsonb(self) -> None:
        """``target`` is NOT NULL — always populated with the
        WorkoutTarget shape (primary range, fallback, description).
        Numeric ranges nullable for Tier 5-6 athletes; description
        is always non-empty (CHECK enforces it)."""
        col = _columns()["target"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_duration_seconds_nullable_integer(self) -> None:
        """``duration_seconds`` is nullable — warmup / cooldown can
        be null for some workout variants. When present, the CHECK
        constraint enforces non-negative."""
        col = _columns()["duration_seconds"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)

    def test_description_required_text(self) -> None:
        col = _columns()["description"]
        assert col.nullable is False
        assert isinstance(col.type, Text)


# ---------------------------------------------------------------------------
# Unique constraint — (generated_workout_id, step_order).
# ---------------------------------------------------------------------------


class TestWorkoutStepStepOrderUniqueConstraint:
    """``(generated_workout_id, step_order)`` is UNIQUE — one step
    per order position per workout."""

    def test_step_order_unique_constraint_present(self) -> None:
        uniques = _unique_constraints()
        matched = [
            u
            for u in uniques
            if _uq_constraint_columns(u)
            == ("generated_workout_id", "step_order")
            and _uq_constraint_name(u)
            == "uq_workout_steps_generated_workout_step_order"
        ]
        assert matched, (
            "workout_steps must declare UNIQUE "
            "(generated_workout_id, step_order). "
            f"Got: {[_uq_constraint_columns(u) for u in uniques]}"
        )

    def test_step_order_unique_constraint_columns(self) -> None:
        uniques = _unique_constraints()
        matched = [
            u
            for u in uniques
            if _uq_constraint_name(u)
            == "uq_workout_steps_generated_workout_step_order"
        ]
        assert matched
        u = matched[0]
        assert _uq_constraint_columns(u) == (
            "generated_workout_id",
            "step_order",
        )


# ---------------------------------------------------------------------------
# CHECK constraints — step_order >= 1, duration >= 0, description non-empty.
# ---------------------------------------------------------------------------


class TestWorkoutStepStepOrderCheck:
    """``step_order`` is 1-indexed and positive."""

    def test_step_order_positive_check_present(self) -> None:
        checks = _check_constraints()
        found = any(
            "step_order" in _check_text(c)
            and ">=" in _check_text(c)
            and "1" in _check_text(c)
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
        checks = _check_constraints()
        found = any(
            "duration_seconds" in _check_text(c)
            and ">=" in _check_text(c)
            and "is null" in _check_text(c).lower()
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
        checks = _check_constraints()
        found = any(
            "length(description)" in _check_text(c)
            and "> 0" in _check_text(c)
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
        indexes = _indexes()
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
        assert "updated_at" not in _columns(), (
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
        assert forbidden_field not in _columns(), (
            f"WorkoutStep must not carry `{forbidden_field}`. "
            "Step row shape is restricted to workout linkage, "
            "three-layer hierarchy (session_type/physiological_intent/"
            "session_purpose), target JSONB, duration, description."
        )