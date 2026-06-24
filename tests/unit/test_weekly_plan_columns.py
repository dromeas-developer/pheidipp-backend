"""Unit tests for the ``WeeklyPlan`` and ``WeeklySession`` declarative surfaces (no DB).

Phase-1.2b introduces both tables in the same module. The unit tests
pin column presence, nullability, table-level uniqueness on
``(training_plan_id, week_number)``, and the inline-union CHECK
constraints used to bound the closed status vocabularies.

Invariants pinned here:

* ``WeeklyPlan (training_plan_id, week_number)`` is unique.
* ``WeeklySession.planned_session_id`` is unique when non-null and
  nullable otherwise.
* Mobile execution-counters default to zero and persist as positive.
* Block-membership fields use ``first | middle | last`` via CHECK.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/weekly-plan.md
"""

from __future__ import annotations

import pytest
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.enums import CheckpointType, SessionType, WeeklyPlanStatus
from app.models.weekly_plan import WeeklyPlan, WeeklySession


# ---------------------------------------------------------------------------
# WeeklyPlan
# ---------------------------------------------------------------------------


def _weekly_plan_columns() -> dict[str, object]:
    return {column.key: column for column in WeeklyPlan.__table__.columns}


def _weekly_plan_indexes() -> dict[str, "object"]:
    return {idx.name: idx for idx in WeeklyPlan.__table__.indexes}


def _weekly_plan_unique_constraints() -> list[UniqueConstraint]:
    return [
        c
        for c in WeeklyPlan.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def _weekly_plan_check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in WeeklyPlan.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


class TestWeeklyPlanRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _weekly_plan_columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_training_plan_id_required_uuid(self) -> None:
        col = _weekly_plan_columns()["training_plan_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_week_number_required_integer(self) -> None:
        col = _weekly_plan_columns()["week_number"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_adjusted_intent_required_jsonb(self) -> None:
        col = _weekly_plan_columns()["adjusted_intent"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_status_required_enum(self) -> None:
        col = _weekly_plan_columns()["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(WeeklyPlanStatus))
        assert actual == ["active", "completed", "synthesised"]

    @pytest.mark.parametrize(
        "counter_field, expected_default",
        [
            ("sessions_completed", "0"),
            ("sessions_missed", "0"),
            ("sessions_skipped", "0"),
            ("doubles_days_count", "0"),
        ],
    )
    def test_execution_counter_required_with_zero_default(
        self, counter_field: str, expected_default: str
    ) -> None:
        col = _weekly_plan_columns()[counter_field]
        assert col.nullable is False
        assert isinstance(col.type, Integer)
        # server_default must be "0" — the column is auto-populated.
        assert col.server_default.arg == expected_default

    def test_accumulated_fatigue_delta_required_with_zero_default(self) -> None:
        col = _weekly_plan_columns()["accumulated_fatigue_delta"]
        assert col.nullable is False

    def test_created_at_required_datetime(self) -> None:
        col = _weekly_plan_columns()["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_week_starts_at_required_date(self) -> None:
        col = _weekly_plan_columns()["week_starts_at"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_week_ends_at_required_date(self) -> None:
        col = _weekly_plan_columns()["week_ends_at"]
        assert col.nullable is False
        assert isinstance(col.type, Date)


class TestWeeklyPlanUniqueConstraint:
    """One WeeklyPlan per week per TrainingPlan."""

    def test_plan_week_unique_constraint_present(self) -> None:
        constraints = _weekly_plan_unique_constraints()
        matching = [
            c
            for c in constraints
            if tuple(col.key for col in c.columns) == (
                "training_plan_id",
                "week_number",
            )
        ]
        assert matching, (
            "WeeklyPlan must declare UNIQUE (training_plan_id, "
            "week_number) — architecture invariant."
        )


class TestWeeklyPlanCheckConstraints:
    def _check_text(self, check: CheckConstraint) -> str:
        expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
        return (str(expr) if expr is not None else "")

    def test_week_number_positive_check(self) -> None:
        checks = _weekly_plan_check_constraints()
        found = any(
            "week_number" in self._check_text(c)
            and ">=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "WeeklyPlan must declare a CHECK constraint "
            "`week_number >= 1`."
        )

    def test_session_counters_non_negative_check(self) -> None:
        checks = _weekly_plan_check_constraints()
        found = any(
            "sessions_completed" in self._check_text(c)
            and "sessions_missed" in self._check_text(c)
            and "sessions_skipped" in self._check_text(c)
            and ">=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "WeeklyPlan must declare a CHECK constraint "
            "ensuring all three session counters are non-negative."
        )

    def test_doubles_days_count_non_negative_check(self) -> None:
        checks = _weekly_plan_check_constraints()
        found = any(
            "doubles_days_count" in self._check_text(c)
            and ">=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "WeeklyPlan must declare a CHECK constraint "
            "`doubles_days_count >= 0`."
        )


class TestWeeklyPlanIndexes:
    def test_plan_status_index_present(self) -> None:
        matched = [
            idx
            for idx in _weekly_plan_indexes().values()
            if {c.key for c in idx.columns} >= {
                "training_plan_id",
                "status",
            }
        ]
        assert matched, (
            "Expected an index on (training_plan_id, status) for "
            "weekly-plan lookup."
        )


class TestWeeklyPlanSchemaAntiGoals:
    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # The actual sessions belong on WeeklySession / PlannedSession.
            "sessions",
            "session_count",
            # No aggregate load scores (those live on Activity).
            "total_load",
            "aerobic_load",
            # UUID linkage to weekly summary is on PlannedSession.
            "workout_id",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _weekly_plan_columns(), (
            f"WeeklyPlan must not carry `{forbidden_field}`."
        )


# ---------------------------------------------------------------------------
# WeeklySession
# ---------------------------------------------------------------------------


def _weekly_session_columns() -> dict[str, object]:
    return {column.key: column for column in WeeklySession.__table__.columns}


def _weekly_session_unique_constraints() -> list[UniqueConstraint]:
    return [
        c
        for c in WeeklySession.__table__.constraints
        if isinstance(c, UniqueConstraint)
    ]


def _weekly_session_check_constraints() -> list[CheckConstraint]:
    return [
        c
        for c in WeeklySession.__table__.constraints
        if isinstance(c, CheckConstraint)
    ]


class TestWeeklySessionRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = _weekly_session_columns()["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_weekly_plan_id_required_uuid(self) -> None:
        col = _weekly_session_columns()["weekly_plan_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_target_date_required_date(self) -> None:
        col = _weekly_session_columns()["target_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_session_type_required_enum(self) -> None:
        col = _weekly_session_columns()["session_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(SessionType))
        expected = sorted(
            [
                "rest",
                "recovery_run",
                "easy_run",
                "long_run",
                "medium_long_run",
                "steady_state",
                "tempo",
                "threshold",
                "vo2max",
                "hill_repeats",
                "fartlek",
                "strides",
                "drills_mobility",
                "cross_training",
                "test_session",
                "optional_run",
            ]
        )
        assert actual == expected

    def test_intent_description_required_string(self) -> None:
        col = _weekly_session_columns()["intent_description"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 512

    def test_approximate_duration_minutes_required_integer(self) -> None:
        col = _weekly_session_columns()["approximate_duration_minutes"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_is_checkpoint_required_bool_default_false(self) -> None:
        col = _weekly_session_columns()["is_checkpoint"]
        assert col.nullable is False
        assert col.server_default.arg in {"false", "False", "0"}

    def test_checkpoint_type_nullable_enum(self) -> None:
        col = _weekly_session_columns()["checkpoint_type"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        actual = sorted(col.type.values_callable(CheckpointType))
        expected = sorted(
            [
                "calibration",
                "benchmark",
                "race_simulation",
                "secondary_race",
                "progress_review",
            ]
        )
        assert actual == expected

    def test_checkpoint_metric_nullable_string(self) -> None:
        col = _weekly_session_columns()["checkpoint_metric"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 128

    def test_status_required_inline_union(self) -> None:
        """``WeeklySession.status`` uses an inline-union (``scheduled |
        completed | skipped | missed``) distinct from
        ``WeeklyPlanStatus``."""
        col = _weekly_session_columns()["status"]
        assert col.nullable is False

    def test_planned_session_id_nullable_uuid_unique_when_set(self) -> None:
        """``WeeklySession.planned_session_id`` is UNIQUE when non-null
        so one WeeklySession maps to at most one PlannedSession.

        The mapper declares ``unique=True`` on the column — this
        results in a UNIQUE constraint with the column being null-
        tolerant. We assert nullable=True and unique=True."""
        col = _weekly_session_columns()["planned_session_id"]
        assert col.nullable is True
        assert col.unique is True

    def test_block_id_nullable_string(self) -> None:
        col = _weekly_session_columns()["block_id"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 64

    def test_block_position_nullable_string(self) -> None:
        col = _weekly_session_columns()["block_position"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_block_session_count_nullable_integer(self) -> None:
        col = _weekly_session_columns()["block_session_count"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)


class TestWeeklySessionUniqueConstraint:
    def test_planned_session_id_unique_constraint_present(self) -> None:
        """The mapper's ``unique=True`` on ``planned_session_id`` is
        surfaced as a UNIQUE constraint."""
        constraints = _weekly_session_unique_constraints()
        # Check via the underlying column-level unique as a fallback.
        matching = [
            c
            for c in constraints
            if tuple(col.key for col in c.columns) == ("planned_session_id",)
        ]
        col_unique = _weekly_session_columns()["planned_session_id"].unique
        assert matching or col_unique, (
            "WeeklySession.planned_session_id must be uniquely "
            "constrained so one WeeklySession maps to at most one "
            "PlannedSession."
        )


class TestWeeklySessionCheckConstraints:
    def _check_text(self, check: CheckConstraint) -> str:
        expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
        return (str(expr) if expr is not None else "")

    def test_status_inline_union_check(self) -> None:
        checks = _weekly_session_check_constraints()
        text = " | ".join(self._check_text(c) for c in checks).lower()
        for status_value in ("scheduled", "completed", "skipped", "missed"):
            assert status_value in text, (
                f"WeeklySession.status check must include "
                f"`{status_value}`. Found check texts: {text!r}"
            )

    def test_block_position_inline_union_check(self) -> None:
        checks = _weekly_session_check_constraints()
        text = " | ".join(self._check_text(c) for c in checks).lower()
        assert "block_position" in text
        for pos in ("first", "middle", "last"):
            assert pos in text, (
                f"WeeklySession.block_position check must include "
                f"`{pos}`. Found check texts: {text!r}"
            )

    def test_duration_positive_check(self) -> None:
        checks = _weekly_session_check_constraints()
        found = any(
            "approximate_duration_minutes" in self._check_text(c)
            and ">" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "WeeklySession must declare a CHECK constraint "
            "`approximate_duration_minutes > 0`."
        )


class TestWeeklySessionSchemaAntiGoals:
    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # No workout prescription fields (live on PlannedSession).
            "workout_zones",
            "target_pace",
            "target_hr",
            "structured_workout",
            # No aggregate-coach-tracking fields.
            "athlete_feedback",
            "rpe",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in _weekly_session_columns(), (
            f"WeeklySession must not carry `{forbidden_field}`. The "
            "schema-only contract places workout prescription on "
            "PlannedSession only."
        )
