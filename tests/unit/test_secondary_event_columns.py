"""Unit tests for the ``SecondaryEvent`` declarative surface (no DB).

Phase-1.2b adds ``SecondaryEvent`` as a supporting storage table for
a ``TrainingGoal``'s B/C-races. The unit tests pin column presence,
nullability, the FK to ``training_goals``, and the absence of any
service-layer fields (this is storage only).

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
Architecture: docs/architecture/01-entities/training-goal.md (SecondaryEvent section)
"""

from __future__ import annotations

import pytest
from sqlalchemy import Date, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from app.models.enums import GoalEventType, SecondaryEventPriority
from app.models.secondary_event import SecondaryEvent
from tests.utils.model_helpers import get_columns, get_indexes, get_foreign_keys_referencing, get_enum_values


class TestSecondaryEventRequiredColumns:
    def test_id_column_uuid_primary_key(self) -> None:
        col = get_columns(SecondaryEvent)["id"]
        assert col.primary_key is True
        assert isinstance(col.type, PG_UUID)

    def test_training_goal_id_required_uuid(self) -> None:
        col = get_columns(SecondaryEvent)["training_goal_id"]
        assert col.nullable is False
        assert isinstance(col.type, PG_UUID)

    def test_event_type_required_enum(self) -> None:
        col = get_columns(SecondaryEvent)["event_type"]
        assert col.nullable is False
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

    def test_event_date_required_date(self) -> None:
        col = get_columns(SecondaryEvent)["event_date"]
        assert col.nullable is False
        assert isinstance(col.type, Date)

    def test_event_name_nullable_string(self) -> None:
        col = get_columns(SecondaryEvent)["event_name"]
        assert col.nullable is True
        assert isinstance(col.type, String)
        assert col.type.length == 255

    def test_priority_required_enum(self) -> None:
        col = get_columns(SecondaryEvent)["priority"]
        assert col.nullable is False
        assert isinstance(col.type, SAEnum)
        actual = sorted(get_enum_values(col, SecondaryEventPriority))
        assert actual == ["B", "C"]


class TestSecondaryEventForeignKey:
    def test_training_goal_id_has_fk_to_training_goals(self) -> None:
        foreign_keys = get_foreign_keys_referencing(SecondaryEvent, "training_goal_id")
        assert foreign_keys, (
            "SecondaryEvent.training_goal_id must declare an FK to "
            "training_goals.id."
        )
        for fk in foreign_keys:
            assert fk.column.table.name == "training_goals"


class TestSecondaryEventIndexes:
    def test_goal_index_present(self) -> None:
        matched = [
            idx
            for idx in get_indexes(SecondaryEvent).values()
            if {c.key for c in idx.columns} >= {"training_goal_id"}
        ]
        assert matched, (
            "Expected an index on (training_goal_id) for the "
            "secondary-events-per-goal lookup."
        )

    def test_goal_date_index_present(self) -> None:
        matched = [
            idx
            for idx in get_indexes(SecondaryEvent).values()
            if {c.key for c in idx.columns} >= {
                "training_goal_id",
                "event_date",
            }
        ]
        assert matched, (
            "Expected an index on (training_goal_id, event_date) for "
            "the upcoming-secondary-events query."
        )


class TestSecondaryEventSchemaAntiGoals:
    @pytest.mark.parametrize(
        "forbidden_field",
        [
            # No plan-schedule linkage (the conflict-with-taper
            # derivation lives on the application side).
            "conflicts_with_taper",
            "taper_week_index",
            # No coach-tracking fields.
            "coach_notes",
            "athlete_notes",
            # No linkage to a plan row at insert time (Population
            # registration is goal-scoped).
            "training_plan_id",
        ],
    )
    def test_forbidden_columns_are_absent(self, forbidden_field: str) -> None:
        assert forbidden_field not in get_columns(SecondaryEvent), (
            f"SecondaryEvent must not carry `{forbidden_field}`. The "
            "schema-only contract keeps goal-linkage fields out of "
            "supporting storage tables."
        )
