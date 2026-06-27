"""Unit tests for the ``GeneratedWorkout`` declarative surface (no DB).

Phase-1.2c introduces the ``GeneratedWorkout`` schema — an
append-only day-of-workout record attached to a PlannedSession. The
two-column ``TargetSet`` JSONB shape (``theoretical_targets`` /
``adjusted_targets``) backs the daily-view two-column display; both
fields always populated, identical values allowed.

Invariants pinned here:

* Append-only — no ``update()`` / ``delete()`` helpers on the mapper.
* ``(planned_session_id, generation_date)`` is UNIQUE — idempotency
  contract for the workout generation pipeline.
* ``theoretical_targets`` and ``adjusted_targets`` are NOT NULL JSONB
  and must be JSON objects (CHECK).
* ``recovery_modifier_level`` defaults to ``green``.
* ``recovery_modifier_level`` is bounded to ``green|amber|red``
  (CHECK).

Reference plan: docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md
Architecture: docs/architecture/01-entities/generated-workout.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    Date,
    DateTime,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.enums import RecoveryModifierLevel
from app.models.generated_workout import GeneratedWorkout
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_check_constraints,
    get_unique_constraints,
    get_foreign_keys_referencing,
    get_check_text,
    get_server_default_text,
    get_enum_values,
)


# ---------------------------------------------------------------------------
# Column presence and type.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(GeneratedWorkout)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_planned_session_id_required_uuid(self) -> None:
        col = get_columns(GeneratedWorkout)["planned_session_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_planned_session_id_cascade_fk_to_planned_sessions(self) -> None:
        """PlannedSession FK ON DELETE CASCADE — generated workouts
        are wiped when the parent planned session is removed."""
        fks = get_foreign_keys_referencing(GeneratedWorkout, "planned_session_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "planned_sessions"
        assert fk.ondelete == "CASCADE"

    def test_twin_state_id_required_uuid(self) -> None:
        col = get_columns(GeneratedWorkout)["twin_state_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_twin_state_id_cascade_fk_to_twin_states(self) -> None:
        """TwinState FK ON DELETE CASCADE — generated workouts are
        wiped when the parent twin state is removed."""
        fks = get_foreign_keys_referencing(GeneratedWorkout, "twin_state_id")
        assert len(fks) == 1
        fk = fks[0]
        assert fk.column.table.name == "twin_states"
        assert fk.ondelete == "CASCADE"

    def test_theoretical_targets_required_jsonb(self) -> None:
        """``theoretical_targets`` is NOT NULL — the architectural
        decision is to always populate both columns even when they
        are identical (GREEN modifier, no weather adjustment)."""
        col = get_columns(GeneratedWorkout)["theoretical_targets"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_adjusted_targets_required_jsonb(self) -> None:
        col = get_columns(GeneratedWorkout)["adjusted_targets"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_recovery_modifier_level_required_enum_default_green(
        self,
    ) -> None:
        col = get_columns(GeneratedWorkout)["recovery_modifier_level"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, RecoveryModifierLevel))
        assert actual == ["amber", "green", "red"]
        # server_default is the string literal "green" — not the
        # enum's Python repr.
        assert col.server_default is not None
        assert "green" in get_server_default_text(col)

    def test_recovery_modifier_reason_nullable_text(self) -> None:
        col = get_columns(GeneratedWorkout)["recovery_modifier_reason"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_generation_date_required_date(self) -> None:
        col = get_columns(GeneratedWorkout)["generation_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_generated_at_required_datetime(self) -> None:
        col = get_columns(GeneratedWorkout)["generated_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)


# ---------------------------------------------------------------------------
# Unique constraint — (planned_session_id, generation_date) idempotency.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutIdempotencyUniqueConstraint:
    """``(planned_session_id, generation_date)`` is UNIQUE — the
    "exactly one workout per planned-session per generation day"
    idempotency contract."""

    def test_idempotency_unique_constraint_present(self) -> None:
        uniques = get_unique_constraints(GeneratedWorkout)
        matched = [
            u
            for u in uniques
            if tuple(col.key for col in u.columns)
            == ("planned_session_id", "generation_date")
            and getattr(u, "name", None)
            == "uq_generated_workouts_planned_session_generation_date"
        ]
        assert matched, (
            "generated_workouts must declare UNIQUE "
            "(planned_session_id, generation_date). "
            f"Got: {[(tuple(col.key for col in u.columns), getattr(u, 'name', None)) for u in uniques]}"
        )

    def test_idempotency_unique_constraint_columns(self) -> None:
        uniques = get_unique_constraints(GeneratedWorkout)
        matched = [
            u
            for u in uniques
            if getattr(u, "name", None)
            == "uq_generated_workouts_planned_session_generation_date"
        ]
        assert matched
        u = matched[0]
        assert tuple(col.key for col in u.columns) == (
            "planned_session_id",
            "generation_date",
        )


# ---------------------------------------------------------------------------
# CHECK constraints — targets are JSONB objects + modifier level valid.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutTargetsAreObjectsCheck:
    """Both ``theoretical_targets`` and ``adjusted_targets`` must be
    JSONB objects — null or non-object shapes (string, number,
    array) are programming errors blocked at the DB layer."""

    def test_targets_are_objects_check_present(self) -> None:
        checks = get_check_constraints(GeneratedWorkout)
        found = any(
            "jsonb_typeof" in get_check_text(c)
            and "theoretical_targets" in get_check_text(c)
            and "adjusted_targets" in get_check_text(c)
            and "object" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "GeneratedWorkout must declare a CHECK constraint "
            "enforcing `jsonb_typeof(theoretical_targets) = 'object'` "
            "and `jsonb_typeof(adjusted_targets) = 'object'`."
        )


class TestGeneratedWorkoutRecoveryModifierLevelCheck:
    """``recovery_modifier_level`` is bounded to green|amber|red."""

    def test_modifier_level_check_present(self) -> None:
        checks = get_check_constraints(GeneratedWorkout)
        found = any(
            "recovery_modifier_level" in get_check_text(c)
            and "green" in get_check_text(c)
            and "amber" in get_check_text(c)
            and "red" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "GeneratedWorkout must declare a CHECK constraint "
            "bounding `recovery_modifier_level` to "
            "`green|amber|red`."
        )


# ---------------------------------------------------------------------------
# Reverse-lookup indexes.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutSecondaryIndexes:
    """``ix_generated_workouts_twin_state`` for reverse lookup from
    twin state; ``ix_generated_workouts_planned_session_generated``
    supports the today-view fast path."""

    def test_twin_state_reverse_lookup_index_present(self) -> None:
        indexes = get_indexes(GeneratedWorkout)
        assert "ix_generated_workouts_twin_state" in indexes

    def test_planned_session_generated_index_present(self) -> None:
        indexes = get_indexes(GeneratedWorkout)
        assert "ix_generated_workouts_planned_session_generated" in indexes
        idx = indexes["ix_generated_workouts_planned_session_generated"]
        columns = {c.key for c in idx.columns}
        assert columns == {"planned_session_id", "generated_at"}


# ---------------------------------------------------------------------------
# Append-only contract — no update()/delete() helpers on the mapper.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutAppendOnlyContract:
    """GeneratedWorkout is append-only — the ``WorkoutGenerationAgent``
    (Phase 1.5b) writes rows but never mutates them."""

    def test_no_update_helper_methods(self) -> None:
        for attr_name in dir(GeneratedWorkout):
            if attr_name.startswith("__"):
                continue
            attr = getattr(GeneratedWorkout, attr_name, None)
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
                    f"GeneratedWorkout must not expose a `{attr_name}` "
                    "method — the table is append-only."
                )

    def test_no_updated_at_column(self) -> None:
        """Append-only contract: ``updated_at`` would imply a
        mutation semantic the schema must not permit."""
        assert "updated_at" not in get_columns(GeneratedWorkout), (
            "GeneratedWorkout must not carry an `updated_at` column — "
            "rows are immutable after insert."
        )


# ---------------------------------------------------------------------------
# Schema anti-goals — fields that must NOT appear on GeneratedWorkout.
# ---------------------------------------------------------------------------


class TestGeneratedWorkoutSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract or violate the architecture."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # Soft-delete / mutation columns.
            "deleted_at",
            "is_deleted",
            "updated_at",
            # Workout step fields live on WorkoutStep, not here.
            "step_order",
            "physiological_intent",
            "target",
            "duration_seconds",
            # Activity / completion tracking belongs elsewhere.
            "completed_at",
            "completed",
            "actual_duration_seconds",
            # Twin state fields.
            "fitness",
            "fatigue",
            "form",
            "trigger",
            "model_version",
            "metric_confidence",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(GeneratedWorkout), (
            f"GeneratedWorkout must not carry `{forbidden_field}`. "
            "Workout row shape is restricted to planned_session_id, "
            "twin_state_id, two target JSONBs, modifier, dates."
        )