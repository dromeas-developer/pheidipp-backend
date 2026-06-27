"""Integration tests for the ``SecondaryEvent`` schema at the DB level.

Phase-1.2b adds ``secondary_events`` as the supporting storage for a
``TrainingGoal``'s B/C-races. The DB-level invariants codified here:

* ``secondary_events.training_goal_id`` carries an FK with
  ``ondelete='CASCADE'``.
* ``event_type`` is the GoalEventType enum (re-used from the goal).
* ``priority`` is bounded to ``{B, C}``.
* ``event_date`` is required.

Maximum-3-per-goal and conflict-with-taper semantics are enforced at
the application layer; the schema only stores the rows.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import (
    GoalEventType,
    GoalType,
    SecondaryEventPriority,
    TrainingGoalStatus,
)
from app.models.secondary_event import SecondaryEvent
from app.models.training_goal import TrainingGoal
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_columns,
    db_foreign_keys,
    db_indexes,
)


TABLE = "secondary_events"


async def _new_goal(
    db_session: AsyncSession, athlete: Athlete
) -> TrainingGoal:
    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=GoalEventType.MARATHON,
        weekly_volume_hours=8.0,
        weekly_volume_km=60.0,
        fitness_level=4,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()
    return goal


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestSecondaryEventDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "training_goal_id",
            "event_type",
            "event_date",
            "event_name",
            "priority",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"secondary_events.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestSecondaryEventForeignKeyCascade:
    def test_training_goal_id_fk_to_training_goals(self) -> None:
        fks = db_foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "training_goals"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_goal_id",)
        ]
        assert matches, (
            "secondary_events.training_goal_id must reference "
            "training_goals(id)."
        )

    def test_fk_ondelete_cascade_in_pg_catalog(self) -> None:
        fks = db_foreign_keys(TABLE)
        goal_fks = [
            fk for fk in fks
            if fk.get("referred_table") == "training_goals"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_goal_id",)
        ]
        assert goal_fks, (
            "secondary_events.training_goal_id FK must reference "
            "training_goals(id)."
        )
        options = goal_fks[0].get("options", {})
        assert options.get("ondelete") == "CASCADE", (
            "secondary_events.training_goal_id FK must CASCADE on delete. "
            f"Got ondelete={options.get('ondelete')!r}"
        )

    async def test_cascade_delete_with_goal(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "se-cascade@example.com")
        goal = await _new_goal(db_session, athlete)
        from datetime import date as _date

        se = SecondaryEvent(
            training_goal_id=goal.id,
            event_type=GoalEventType.TEN_K,
            event_date=_date(2026, 9, 14),
            event_name="Park 10K",
            priority=SecondaryEventPriority.B,
        )
        db_session.add(se)
        await db_session.flush()
        se_id = se.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(TrainingGoal).where(TrainingGoal.id == goal.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(SecondaryEvent).where(SecondaryEvent.id == se_id)
        )
        assert remaining.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# Persistence — happy path.
# ---------------------------------------------------------------------------


class TestSecondaryEventPersistence:
    async def test_full_secondary_event_persists(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import date as _date

        athlete = await make_athlete(db_session, "se-rt@example.com")
        goal = await _new_goal(db_session, athlete)
        se = SecondaryEvent(
            training_goal_id=goal.id,
            event_type=GoalEventType.HALF_MARATHON,
            event_date=_date(2026, 9, 28),
            event_name="City Half",
            priority=SecondaryEventPriority.C,
        )
        db_session.add(se)
        await db_session.flush()
        await db_session.refresh(se)
        assert se.id is not None
        assert se.training_goal_id == goal.id
        assert se.event_type is GoalEventType.HALF_MARATHON
        assert se.event_date == _date(2026, 9, 28)
        assert se.event_name == "City Half"
        assert se.priority is SecondaryEventPriority.C

    async def test_minimal_secondary_event_persists(
        self, db_session: AsyncSession
    ) -> None:
        """``event_name`` is nullable — a bare ``{B|C}`` priority race
        type/date is a valid row."""
        from datetime import date as _date

        athlete = await make_athlete(db_session, "se-min@example.com")
        goal = await _new_goal(db_session, athlete)
        se = SecondaryEvent(
            training_goal_id=goal.id,
            event_type=GoalEventType.FIVE_K,
            event_date=_date(2026, 7, 4),
            priority=SecondaryEventPriority.B,
        )
        db_session.add(se)
        await db_session.flush()
        await db_session.refresh(se)
        assert se.event_name is None


# ---------------------------------------------------------------------------
# Indexes.
# ---------------------------------------------------------------------------


class TestSecondaryEventIndexes:
    def test_goal_index_present(self) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or []) >= {"training_goal_id"}
        ]
        assert matched, (
            "Expected an index on (training_goal_id) for the "
            "secondary-events-per-goal lookup."
        )

    def test_goal_date_index_present(self) -> None:
        matched = [
            idx
            for idx in db_indexes(TABLE)
            if set(idx.get("column_names") or [])
            >= {"training_goal_id", "event_date"}
        ]
        assert matched, (
            "Expected an index on (training_goal_id, event_date) for "
            "the upcoming-secondary-events query."
        )
