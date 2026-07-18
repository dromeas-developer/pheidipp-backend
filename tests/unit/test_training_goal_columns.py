"""Unit tests for the ``TrainingGoal`` declarative surface (no DB).

Phase-1.2b introduces the ``TrainingGoal`` schema-only foundation. These
tests pin the column presence, nullability, and indexed partial-unique
contract on the ORM mapper without touching the database. The
corresponding DB-level inspection lives in
``tests/integration/test_training_goal_schema.py``.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/training-goal.md
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import (
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.enums import (
    GoalEventType,
    GoalType,
    InjurySeverity,
    TrainingGoalStatus,
)
from app.models.training_goal import TrainingGoal
from tests.utils.model_helpers import (
    get_columns,
    get_indexes,
    get_check_constraints,
    get_check_text,
    get_enum_values,
)


class TestTrainingGoalRequiredColumns:
    """Every documented field from the architecture doc must be present
    on the declarative mapper."""

    def test_id_column_uuid_primary_key(self) -> None:
        cols = get_columns(TrainingGoal)
        assert "id" in cols
        assert cols["id"].primary_key is True
        assert isinstance(cols["id"].type, PG_UUID)

    def test_athlete_id_is_required_uuid(self) -> None:
        col = get_columns(TrainingGoal)["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_goal_type_is_enum_backed_required(self) -> None:
        col = get_columns(TrainingGoal)["goal_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, GoalType))
        expected = sorted(
            [
                "race_event",
                "target_performance",
                "fitness_improvement",
                "maintenance",
                "recovery",
            ]
        )
        assert actual == expected

    def test_goal_event_type_nullable_enum(self) -> None:
        col = get_columns(TrainingGoal)["goal_event_type"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, GoalEventType))
        expected = sorted(
            [
                "marathon",
                "half_marathon",
                "10k",
                "5k",
                "ultra",
                "trail_race",
                "custom",
            ]
        )
        assert actual == expected

    def test_goal_event_name_nullable_string(self) -> None:
        col = get_columns(TrainingGoal)["goal_event_name"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 255

    def test_goal_event_date_nullable_date(self) -> None:
        col = get_columns(TrainingGoal)["goal_event_date"]
        assert col.nullable is True
        assert isinstance(col.type, Date)

    def test_custom_distance_km_nullable_float(self) -> None:
        col = get_columns(TrainingGoal)["custom_distance_km"]
        assert col.nullable is True
        assert isinstance(col.type, Float)

    def test_goal_description_nullable_text(self) -> None:
        col = get_columns(TrainingGoal)["goal_description"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_weekly_volume_hours_required_float(self) -> None:
        col = get_columns(TrainingGoal)["weekly_volume_hours"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_weekly_volume_km_required_float(self) -> None:
        col = get_columns(TrainingGoal)["weekly_volume_km"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_fitness_level_required_integer(self) -> None:
        col = get_columns(TrainingGoal)["fitness_level"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_recent_injury_nullable_text(self) -> None:
        col = get_columns(TrainingGoal)["recent_injury"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_injury_severity_nullable_enum(self) -> None:
        col = get_columns(TrainingGoal)["injury_severity"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, InjurySeverity))
        assert actual == ["major", "minor", "moderate"]

    def test_target_distance_km_nullable_float(self) -> None:
        col = get_columns(TrainingGoal)["target_distance_km"]
        assert col.nullable is True
        assert isinstance(col.type, Float)

    def test_target_time_minutes_nullable_integer(self) -> None:
        col = get_columns(TrainingGoal)["target_time_minutes"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)

    def test_status_required_enum(self) -> None:
        col = get_columns(TrainingGoal)["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, TrainingGoalStatus))
        assert actual == ["abandoned", "active", "completed"]

    def test_created_at_required_datetime(self) -> None:
        col = get_columns(TrainingGoal)["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_closed_at_nullable_datetime(self) -> None:
        col = get_columns(TrainingGoal)["closed_at"]
        assert col.nullable is True
        assert isinstance(col.type, DateTime)


class TestTrainingGoalActivePartialUniqueIndex:
    """``ix_training_goals_athlete_active`` is unique WHERE
    ``status = 'active'`` — one active goal per athlete."""

    def test_active_goal_partial_unique_index_present(self) -> None:
        indexes = get_indexes(TrainingGoal)
        assert "ix_training_goals_athlete_active" in indexes, (
            "TrainingGoal must declare `ix_training_goals_athlete_active` "
            "to enforce one active goal per athlete."
        )
        idx = indexes["ix_training_goals_athlete_active"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id"}

    def test_active_goal_index_is_unique(self) -> None:
        idx = get_indexes(TrainingGoal)["ix_training_goals_athlete_active"]
        assert idx.unique is True

    def test_active_goal_partial_predicate_is_status_active(self) -> None:
        """The partial predicate must constrain ``status = 'active'`` —
        other statuses don't participate in the unique constraint."""
        idx = get_indexes(TrainingGoal)["ix_training_goals_athlete_active"]
        dialect_opts: Any = idx.dialect_options
        predicate: Any = dialect_opts.get("postgresql", {}).get("where")
        assert predicate is not None, (
            "ix_training_goals_athlete_active must declare a "
            "postgresql_where predicate — without it the index would "
            "block multiple goals in non-active status per athlete."
        )
        rendered = str(predicate).lower()
        assert "status" in rendered and "active" in rendered, (
            "ix_training_goals_athlete_active partial predicate must "
            "constrain status = 'active'. "
            f"Got: {predicate!r}"
        )


class TestTrainingGoalSecondaryIndexes:
    """Athlete/created_at lookup supports recent-goal pagination."""

    def test_athlete_created_at_index_present(self) -> None:
        indexes = get_indexes(TrainingGoal)
        matched = [
            idx
            for idx in indexes.values()
            if {c.key for c in idx.columns} >= {"athlete_id", "created_at"}
        ]
        assert matched, (
            "Expected an index on (athlete_id, created_at) for "
            "recent-goal pagination."
        )


class TestTrainingGoalCheckConstraints:
    """DB-level CHECK constraints codify immutable-semantic-field
    invariants at the schema layer."""

    def test_weekly_volume_hours_non_negative_check(self) -> None:
        checks = get_check_constraints(TrainingGoal)
        found = any(
            "weekly_volume_hours" in get_check_text(c)
            and ">=" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`weekly_volume_hours >= 0`."
        )

    def test_weekly_volume_km_non_negative_check(self) -> None:
        checks = get_check_constraints(TrainingGoal)
        found = any(
            "weekly_volume_km" in get_check_text(c)
            and ">=" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`weekly_volume_km >= 0`."
        )

    def test_fitness_level_range_check(self) -> None:
        checks = get_check_constraints(TrainingGoal)
        found = any(
            "fitness_level" in get_check_text(c)
            and ">=" in get_check_text(c)
            and "<=" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`fitness_level BETWEEN 1 AND 5`."
        )

    def test_custom_distance_positive_check(self) -> None:
        checks = get_check_constraints(TrainingGoal)
        found = any(
            "custom_distance_km" in get_check_text(c).lower()
            and "is null" in get_check_text(c).lower()
            and ">" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`custom_distance_km IS NULL OR custom_distance_km > 0`."
        )

    def test_target_distance_positive_check(self) -> None:
        checks = get_check_constraints(TrainingGoal)
        found = any(
            "target_distance_km" in get_check_text(c).lower()
            and "is null" in get_check_text(c).lower()
            and ">" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`target_distance_km IS NULL OR target_distance_km > 0`."
        )

    def test_target_time_positive_check(self) -> None:
        checks = get_check_constraints(TrainingGoal)
        found = any(
            "target_time_minutes" in get_check_text(c).lower()
            and "is null" in get_check_text(c).lower()
            and ">" in get_check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`target_time_minutes IS NULL OR target_time_minutes > 0`."
        )


class TestTrainingGoalSchemaAntiGoals:
    """Defence-in-depth tripwires: columns that would silently break
    the schema-only contract if added."""

    @pytest.mark.parametrize(
        "forbidden_field",
        [
            "coach_notes",
            "coach_rationale",
            "phases",
            "phase_definitions",
            "weekly_distributions",
            "created_by",
            "updated_at",
            "deleted_at",
            "twin_state_id",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        """Schema-only plan — only the storage shape belongs on this
        table. Plan generation fields land on ``training_plans``."""
        assert forbidden_field not in get_columns(TrainingGoal), (
            f"TrainingGoal must not carry `{forbidden_field}`. The "
            "schema-only contract puts plan generation fields on "
            "`training_plans`, not the goal."
        )
