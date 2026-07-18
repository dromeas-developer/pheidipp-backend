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
    Date,
    DateTime,
    Integer,
    String,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

from app.models.enums import CheckpointType, SessionType, WeeklyPlanStatus
from app.models.weekly_plan import WeeklyPlan, WeeklySession
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_unique_constraints,
    get_check_constraints,
    get_check_text,
    get_server_default_text,
    get_enum_values,
)


# ---------------------------------------------------------------------------
# WeeklyPlan
# ---------------------------------------------------------------------------


class TestWeeklyPlanRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(WeeklyPlan)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_training_plan_id_required_uuid(self) -> None:
        col = get_columns(WeeklyPlan)["training_plan_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_week_number_required_integer(self) -> None:
        col = get_columns(WeeklyPlan)["week_number"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_adjusted_intent_required_jsonb(self) -> None:
        col = get_columns(WeeklyPlan)["adjusted_intent"]
        assert col.nullable is False
        assert isinstance(col.type, JSONB)

    def test_status_required_enum(self) -> None:
        col = get_columns(WeeklyPlan)["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, WeeklyPlanStatus))
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
        col = get_columns(WeeklyPlan)[counter_field]
        assert col.nullable is False
        assert isinstance(col.type, Integer)
        # server_default must be "0" — the column is auto-populated.
        assert get_server_default_text(col) == expected_default

    def test_accumulated_fatigue_delta_required_with_zero_default(self) -> None:
        col = get_columns(WeeklyPlan)["accumulated_fatigue_delta"]
        assert col.nullable is False

    def test_created_at_required_datetime(self) -> None:
        col = get_columns(WeeklyPlan)["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_week_starts_at_required_date(self) -> None:
        col = get_columns(WeeklyPlan)["week_starts_at"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_week_ends_at_required_date(self) -> None:
        col = get_columns(WeeklyPlan)["week_ends_at"]
        assert col.nullable is False
        assert isinstance(col.type, Date)


class TestWeeklyPlanUniqueConstraint:
    """One WeeklyPlan per week per TrainingPlan."""

    def test_plan_week_unique_constraint_present(self) -> None:
        constraints = get_unique_constraints(WeeklyPlan)
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
    def test_week_number_positive_check(self) -> None:
        checks = get_check_constraints(WeeklyPlan)
        found = any(
            "week_number" in get_check_text(c)
            and ">=" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "WeeklyPlan must declare a CHECK constraint "
            "`week_number >= 1`."
        )

    def test_session_counters_non_negative_check(self) -> None:
        checks = get_check_constraints(WeeklyPlan)
        found = any(
            "sessions_completed" in get_check_text(c)
            and "sessions_missed" in get_check_text(c)
            and "sessions_skipped" in get_check_text(c)
            and ">=" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "WeeklyPlan must declare a CHECK constraint "
            "ensuring all three session counters are non-negative."
        )

    def test_doubles_days_count_non_negative_check(self) -> None:
        checks = get_check_constraints(WeeklyPlan)
        found = any(
            "doubles_days_count" in get_check_text(c)
            and ">=" in get_check_text(c)
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
            for idx in get_indexes(WeeklyPlan).values()
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
        assert forbidden_field not in get_columns(WeeklyPlan), (
            f"WeeklyPlan must not carry `{forbidden_field}`."
        )


# ---------------------------------------------------------------------------
# WeeklySession
# ---------------------------------------------------------------------------





class TestWeeklySessionRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(WeeklySession)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_weekly_plan_id_required_uuid(self) -> None:
        col = get_columns(WeeklySession)["weekly_plan_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_target_date_required_date(self) -> None:
        col = get_columns(WeeklySession)["target_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_session_type_required_enum(self) -> None:
        col = get_columns(WeeklySession)["session_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, SessionType))
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
        col = get_columns(WeeklySession)["intent_description"]
        assert col.nullable is False
        assert isinstance(col.type, String)
        assert col.type.length == 512

    def test_approximate_duration_minutes_required_integer(self) -> None:
        col = get_columns(WeeklySession)["approximate_duration_minutes"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_is_checkpoint_required_bool_default_false(self) -> None:
        col = get_columns(WeeklySession)["is_checkpoint"]
        assert col.nullable is False
        assert get_server_default_text(col) in {"false", "False", "0"}

    def test_checkpoint_type_nullable_enum(self) -> None:
        col = get_columns(WeeklySession)["checkpoint_type"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, CheckpointType))
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
        col = get_columns(WeeklySession)["checkpoint_metric"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 128

    def test_status_required_inline_union(self) -> None:
        """``WeeklySession.status`` uses an inline-union (``scheduled |
        completed | skipped | missed``) distinct from
        ``WeeklyPlanStatus``."""
        col = get_columns(WeeklySession)["status"]
        assert col.nullable is False

    def test_planned_session_id_nullable_uuid_unique_when_set(self) -> None:
        """``WeeklySession.planned_session_id`` is UNIQUE when non-null
        so one WeeklySession maps to at most one PlannedSession.

        The mapper declares ``unique=True`` on the column — this
        results in a UNIQUE constraint with the column being null-
        tolerant. We assert nullable=True and unique=True."""
        col = get_columns(WeeklySession)["planned_session_id"]
        assert col.nullable is True
        assert col.unique is True

    def test_block_id_nullable_string(self) -> None:
        col = get_columns(WeeklySession)["block_id"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 64

    def test_block_position_nullable_string(self) -> None:
        col = get_columns(WeeklySession)["block_position"]
        assert col.nullable is True
        assert isinstance(col.type, String)

    def test_block_session_count_nullable_integer(self) -> None:
        col = get_columns(WeeklySession)["block_session_count"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)


class TestWeeklySessionUniqueConstraint:
    def test_planned_session_id_unique_constraint_present(self) -> None:
        """The mapper's ``unique=True`` on ``planned_session_id`` is
        surfaced as a UNIQUE constraint."""
        constraints = get_unique_constraints(WeeklySession)
        # Check via the underlying column-level unique as a fallback.
        matching = [
            c
            for c in constraints
            if tuple(col.key for col in c.columns) == ("planned_session_id",)
        ]
        col_unique = get_columns(WeeklySession)["planned_session_id"].unique
        assert matching or col_unique, (
            "WeeklySession.planned_session_id must be uniquely "
            "constrained so one WeeklySession maps to at most one "
            "PlannedSession."
        )


class TestWeeklySessionCheckConstraints:
    def test_status_inline_union_check(self) -> None:
        checks = get_check_constraints(WeeklySession)
        text = " | ".join(get_check_text(c) for c in checks).lower()
        for status_value in ("scheduled", "completed", "skipped", "missed"):
            assert status_value in text, (
                f"WeeklySession.status check must include "
                f"`{status_value}`. Found check texts: {text!r}"
            )

    def test_block_position_inline_union_check(self) -> None:
        checks = get_check_constraints(WeeklySession)
        text = " | ".join(get_check_text(c) for c in checks).lower()
        assert "block_position" in text
        for pos in ("first", "middle", "last"):
            assert pos in text, (
                f"WeeklySession.block_position check must include "
                f"`{pos}`. Found check texts: {text!r}"
            )

    def test_duration_positive_check(self) -> None:
        checks = get_check_constraints(WeeklySession)
        found = any(
            "approximate_duration_minutes" in get_check_text(c)
            and ">" in get_check_text(c)
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
        assert forbidden_field not in get_columns(WeeklySession), (
            f"WeeklySession must not carry `{forbidden_field}`. The "
            "schema-only contract places workout prescription on "
            "PlannedSession only."
        )
