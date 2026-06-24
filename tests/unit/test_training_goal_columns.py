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

import pytest
from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Index,
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


def _columns() -> dict[str, object]:
    return {column.key: column for column in TrainingGoal.__table__.columns}


def _indexes() -> dict[str, Index]:
    return {idx.name: idx for idx in TrainingGoal.__table__.indexes}


def _check_constraints() -> list[CheckConstraint]:
    return [c for c in TrainingGoal.__table__.constraints if isinstance(c, CheckConstraint)]


class TestTrainingGoalRequiredColumns:
    """Every documented field from the architecture doc must be present
    on the declarative mapper."""

    def test_id_column_uuid_primary_key(self) -> None:
        cols = _columns()
        assert "id" in cols
        assert cols["id"].primary_key is True
        assert isinstance(cols["id"].type, PG_UUID)

    def test_athlete_id_is_required_uuid(self) -> None:
        col = _columns()["athlete_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_goal_type_is_enum_backed_required(self) -> None:
        col = _columns()["goal_type"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(GoalType))
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
        col = _columns()["goal_event_type"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(GoalEventType))
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
        col = _columns()["goal_event_name"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 255

    def test_goal_event_date_nullable_date(self) -> None:
        col = _columns()["goal_event_date"]
        assert col.nullable is True
        assert isinstance(col.type, Date)

    def test_custom_distance_km_nullable_float(self) -> None:
        col = _columns()["custom_distance_km"]
        assert col.nullable is True
        assert isinstance(col.type, Float)

    def test_goal_description_nullable_text(self) -> None:
        col = _columns()["goal_description"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_weekly_volume_hours_required_float(self) -> None:
        col = _columns()["weekly_volume_hours"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_weekly_volume_km_required_float(self) -> None:
        col = _columns()["weekly_volume_km"]
        assert col.nullable is False
        assert isinstance(col.type, Float)

    def test_fitness_level_required_integer(self) -> None:
        col = _columns()["fitness_level"]
        assert col.nullable is False
        assert isinstance(col.type, Integer)

    def test_recent_injury_nullable_text(self) -> None:
        col = _columns()["recent_injury"]
        assert col.nullable is True
        assert isinstance(col.type, Text)

    def test_injury_severity_nullable_enum(self) -> None:
        col = _columns()["injury_severity"]
        assert col.nullable is True
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(InjurySeverity))
        assert actual == ["major", "minor", "moderate"]

    def test_target_distance_km_nullable_float(self) -> None:
        col = _columns()["target_distance_km"]
        assert col.nullable is True
        assert isinstance(col.type, Float)

    def test_target_time_minutes_nullable_integer(self) -> None:
        col = _columns()["target_time_minutes"]
        assert col.nullable is True
        assert isinstance(col.type, Integer)

    def test_status_required_enum(self) -> None:
        col = _columns()["status"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        values_callable = col.type.values_callable
        assert values_callable is not None
        actual = sorted(values_callable(TrainingGoalStatus))
        assert actual == ["abandoned", "active", "completed"]

    def test_created_at_required_datetime(self) -> None:
        col = _columns()["created_at"]
        assert col.nullable is False
        assert isinstance(col.type, DateTime)

    def test_closed_at_nullable_datetime(self) -> None:
        col = _columns()["closed_at"]
        assert col.nullable is True
        assert isinstance(col.type, DateTime)


class TestTrainingGoalActivePartialUniqueIndex:
    """``ix_training_goals_athlete_active`` is unique WHERE
    ``status = 'active'`` — one active goal per athlete."""

    def test_active_goal_partial_unique_index_present(self) -> None:
        indexes = _indexes()
        assert "ix_training_goals_athlete_active" in indexes, (
            "TrainingGoal must declare `ix_training_goals_athlete_active` "
            "to enforce one active goal per athlete."
        )
        idx = indexes["ix_training_goals_athlete_active"]
        columns = {c.key for c in idx.columns}
        assert columns == {"athlete_id"}

    def test_active_goal_index_is_unique(self) -> None:
        idx = _indexes()["ix_training_goals_athlete_active"]
        assert idx.unique is True

    def test_active_goal_partial_predicate_is_status_active(self) -> None:
        """The partial predicate must constrain ``status = 'active'`` —
        other statuses don't participate in the unique constraint."""
        idx = _indexes()["ix_training_goals_athlete_active"]
        predicate = idx.dialect_options.get("postgresql", {}).get("where")
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
        indexes = _indexes()
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

    def _check_text(self, check: CheckConstraint) -> str:
        """``CheckConstraint`` exposes ``expression`` (newer SA) or
        ``sqltext`` (older SA). Normalise to a string for assertions."""
        expr = getattr(check, "expression", None) or getattr(check, "sqltext", None)
        return (str(expr) if expr is not None else "")

    def test_weekly_volume_hours_non_negative_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "weekly_volume_hours" in self._check_text(c)
            and ">=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`weekly_volume_hours >= 0`."
        )

    def test_weekly_volume_km_non_negative_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "weekly_volume_km" in self._check_text(c)
            and ">=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`weekly_volume_km >= 0`."
        )

    def test_fitness_level_range_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "fitness_level" in self._check_text(c)
            and ">=" in self._check_text(c)
            and "<=" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`fitness_level BETWEEN 1 AND 5`."
        )

    def test_custom_distance_positive_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "custom_distance_km" in self._check_text(c).lower()
            and "is null" in self._check_text(c).lower()
            and ">" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`custom_distance_km IS NULL OR custom_distance_km > 0`."
        )

    def test_target_distance_positive_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "target_distance_km" in self._check_text(c).lower()
            and "is null" in self._check_text(c).lower()
            and ">" in self._check_text(c)
            for c in checks
        )
        assert found, (
            "TrainingGoal must declare a CHECK constraint "
            "`target_distance_km IS NULL OR target_distance_km > 0`."
        )

    def test_target_time_positive_check(self) -> None:
        checks = _check_constraints()
        found = any(
            "target_time_minutes" in self._check_text(c).lower()
            and "is null" in self._check_text(c).lower()
            and ">" in self._check_text(c)
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
        assert forbidden_field not in _columns(), (
            f"TrainingGoal must not carry `{forbidden_field}`. The "
            "schema-only contract puts plan generation fields on "
            "`training_plans`, not the goal."
        )
