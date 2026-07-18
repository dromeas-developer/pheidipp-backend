"""Integration tests for the ``TrainingGoal`` schema at the DB level.

Phase-1.2b introduces the new ``training_goals`` table that is the
schema-only foundation for ``SecondaryEvent``, ``RegenerationTask``,
``TrainingPlan``, ``WeeklyPlan``, ``WeeklySession``, ``PlannedSession``,
and ``Checkpoint`` — every Phase-1.2b child table references the goal.

The DB-level invariants this plan codifies are:

* The active-goal partial unique index on
  ``(athlete_id) WHERE status = 'active'`` enforces one active goal
  per athlete.
* Volume fields ``weekly_volume_hours`` and ``weekly_volume_km`` are
  non-negative (CHECK constraints).
* ``fitness_level`` is in 1..5 (CHECK constraint).
* ``custom_distance_km`` is null OR > 0 (CHECK constraint).
* ``target_distance_km`` and ``target_time_minutes`` are null OR > 0
  (CHECK constraint).
* Status is enum-backed (active / completed / abandoned).
* ``injury_severity`` (when present) is bound to the InjurySeverity
  closed ontology.

The DEFERRED invariants — application-layer checks for
``goal_type='recovery' <-> injury_severity='' IS NOT NULL''``, and
the immutability of semantic fields — are explicitly out-of-scope
for Phase-1.2b (services own those).

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import (
    GoalEventType,
    GoalType,
    InjurySeverity,
    TrainingGoalStatus,
)
from app.models.training_goal import TrainingGoal
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_check_constraints,
    db_columns,
    db_foreign_keys,
    db_indexes,
    get_sync_database_url,
)

TABLE = "training_goals"


# ---------------------------------------------------------------------------
# Helpers — factories / row creation.
# ---------------------------------------------------------------------------


def _goal_factory(
    *,
    athlete_id: uuid.UUID,
    goal_type: GoalType = GoalType.FITNESS_IMPROVEMENT,
    goal_event_type: GoalEventType | None = None,
    goal_event_name: str | None = None,
    goal_event_date: date | None = None,
    custom_distance_km: float | None = None,
    weekly_volume_hours: float = 5.0,
    weekly_volume_km: float = 30.0,
    fitness_level: int = 3,
    recent_injury: str | None = None,
    injury_severity: InjurySeverity | None = None,
    target_distance_km: float | None = None,
    target_time_minutes: int | None = None,
    status: TrainingGoalStatus = TrainingGoalStatus.ACTIVE,
) -> TrainingGoal:
    return TrainingGoal(
        athlete_id=athlete_id,
        goal_type=goal_type,
        goal_event_type=goal_event_type,
        goal_event_name=goal_event_name,
        goal_event_date=goal_event_date,
        custom_distance_km=custom_distance_km,
        weekly_volume_hours=weekly_volume_hours,
        weekly_volume_km=weekly_volume_km,
        fitness_level=fitness_level,
        recent_injury=recent_injury,
        injury_severity=injury_severity,
        target_distance_km=target_distance_km,
        target_time_minutes=target_time_minutes,
        status=status,
    )


# ---------------------------------------------------------------------------
# DB column presence.
# ---------------------------------------------------------------------------


class TestTrainingGoalDBSchemaColumns:
    """Every documented field is physically present."""

    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "athlete_id",
            "goal_type",
            "goal_event_type",
            "goal_event_name",
            "goal_event_date",
            "custom_distance_km",
            "goal_description",
            "weekly_volume_hours",
            "weekly_volume_km",
            "fitness_level",
            "recent_injury",
            "injury_severity",
            "target_distance_km",
            "target_time_minutes",
            "status",
            "created_at",
            "closed_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(TABLE)}
        assert expected_column in cols, (
            f"training_goals.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# Active-goal partial unique index.
# ---------------------------------------------------------------------------


class TestTrainingGoalActivePartialUniqueIndex:
    """One active goal per athlete (partial unique index on
    ``athlete_id WHERE status = 'active'``)."""

    def _active_partial_index(self) -> dict[str, Any] | None:
        for idx in db_indexes(TABLE):
            cols = set(idx.get("column_names") or [])
            if cols >= {"athlete_id"} and idx.get("unique"):
                return idx
        return None

    async def test_active_partial_unique_index_present(
        self, db_session: AsyncSession
    ) -> None:
        idx = self._active_partial_index()
        assert idx is not None, (
            "Expected a UNIQUE index on (athlete_id) — the active "
            "goal partial unique constraint."
        )

    async def test_partial_predicate_is_status_active(
        self, db_session: AsyncSession
    ) -> None:
        """The Inspector may not surface the partial predicate via
        ``dialect_options``; fall back to ``pg_get_indexdef`` and
        confirm the predicate text contains ``status = 'active'``."""
        idx = self._active_partial_index()
        assert idx is not None
        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        "SELECT pg_get_indexdef(indexrelid) "
                        "FROM pg_index WHERE indexrelid = "
                        "(SELECT oid FROM pg_class WHERE relname = :name)"
                    ),
                    {"name": idx["name"]},
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None
        ddl = (row[0] or "").lower()
        assert "status" in ddl and "active" in ddl, (
            f"Active-goal partial index must predicate on "
            f"`status = 'active'`. DDL: {row[0]!r}"
        )


class TestActiveGoalUniquenessAtDB:
    """Two ACTIVE rows for the same athlete must violate the partial
    unique index, raising ``IntegrityError``."""

    async def test_two_active_goals_same_athlete_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "dup-active-goal@example.com")
        g1 = _goal_factory(athlete_id=athlete.id, status=TrainingGoalStatus.ACTIVE)
        g2 = _goal_factory(athlete_id=athlete.id, status=TrainingGoalStatus.ACTIVE)
        db_session.add_all([g1, g2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_one_active_one_completed_coexist(
        self, db_session: AsyncSession
    ) -> None:
        """A completed goal does NOT participate in the partial
        predicate — the partial index must allow the same athlete
        to keep a completed goal and have a new active one."""
        athlete = await make_athlete(db_session, "active-and-completed@example.com")
        g_done = _goal_factory(
            athlete_id=athlete.id, status=TrainingGoalStatus.COMPLETED
        )
        g_active = _goal_factory(
            athlete_id=athlete.id, status=TrainingGoalStatus.ACTIVE
        )
        db_session.add_all([g_done, g_active])
        await db_session.flush()
        await db_session.refresh(g_done)
        await db_session.refresh(g_active)
        assert g_done.id != g_active.id

    async def test_one_active_one_abandoned_coexist(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "active-and-abandoned@example.com")
        g_done = _goal_factory(
            athlete_id=athlete.id, status=TrainingGoalStatus.ABANDONED
        )
        g_active = _goal_factory(
            athlete_id=athlete.id, status=TrainingGoalStatus.ACTIVE
        )
        db_session.add_all([g_done, g_active])
        await db_session.flush()
        await db_session.refresh(g_done)
        await db_session.refresh(g_active)
        assert g_done.id != g_active.id


# ---------------------------------------------------------------------------
# CHECK constraints — volume / fitness / target fields.
# ---------------------------------------------------------------------------


class TestTrainingGoalVolumeChecks:
    async def test_weekly_volume_hours_non_negative_check_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "weekly_volume_hours" in (c.get("sqltext") or "").lower()
            and ">=" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "training_goals must declare CHECK constraint "
            "`weekly_volume_hours >= 0`."
        )

    async def test_weekly_volume_km_non_negative_check_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "weekly_volume_km" in (c.get("sqltext") or "").lower()
            and ">=" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "training_goals must declare CHECK constraint "
            "`weekly_volume_km >= 0`."
        )

    async def test_negative_weekly_volume_hours_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "neg-hours@example.com")
        goal = _goal_factory(athlete_id=athlete.id, weekly_volume_hours=-0.5)
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_zero_weekly_volume_hours_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "zero-hours@example.com")
        goal = _goal_factory(athlete_id=athlete.id, weekly_volume_hours=0)
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)
        assert goal.weekly_volume_hours == 0


class TestTrainingGoalFitnessLevelRange:
    async def test_fitness_level_range_check_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "fitness_level" in (c.get("sqltext") or "").lower()
            and ">=" in (c.get("sqltext") or "").lower()
            and "<=" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "training_goals must declare CHECK constraint "
            "`fitness_level BETWEEN 1 AND 5`."
        )

    async def test_fitness_level_zero_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "fitness-zero@example.com")
        goal = _goal_factory(athlete_id=athlete.id, fitness_level=0)
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_fitness_level_six_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "fitness-six@example.com")
        goal = _goal_factory(athlete_id=athlete.id, fitness_level=6)
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
    async def test_fitness_level_boundaries_accepted(
        self, db_session: AsyncSession, level: int
    ) -> None:
        email = f"fitness-ok-{level}-{uuid.uuid4().hex[:6]}@example.com"
        athlete = await make_athlete(db_session, email)
        goal = _goal_factory(athlete_id=athlete.id, fitness_level=level)
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)
        assert goal.fitness_level == level


class TestTrainingGoalCustomDistanceCheck:
    async def test_custom_distance_positive_check_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "custom_distance_km" in (c.get("sqltext") or "").lower()
            and "is null" in (c.get("sqltext") or "").lower()
            and ">" in (c.get("sqltext") or "")
            for c in checks
        )
        assert found, (
            "training_goals must declare CHECK constraint "
            "`custom_distance_km IS NULL OR custom_distance_km > 0`."
        )

    async def test_custom_distance_zero_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "cd-zero@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id,
            goal_event_type=GoalEventType.CUSTOM,
            custom_distance_km=0,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_custom_distance_negative_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "cd-neg@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id,
            goal_event_type=GoalEventType.CUSTOM,
            custom_distance_km=-1.0,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_custom_distance_null_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "cd-null@example.com")
        goal = _goal_factory(athlete_id=athlete.id, custom_distance_km=None)
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)
        assert goal.custom_distance_km is None


class TestTrainingGoalTargetPerformanceChecks:
    async def test_target_distance_positive_check_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "target_distance_km" in (c.get("sqltext") or "").lower()
            and "is null" in (c.get("sqltext") or "").lower()
            and ">" in (c.get("sqltext") or "")
            for c in checks
        )
        assert found, (
            "training_goals must declare CHECK constraint "
            "`target_distance_km IS NULL OR target_distance_km > 0`."
        )

    async def test_target_time_positive_check_present(
        self, db_session: AsyncSession
    ) -> None:
        checks = db_check_constraints(TABLE)
        found = any(
            "target_time_minutes" in (c.get("sqltext") or "").lower()
            and "is null" in (c.get("sqltext") or "").lower()
            and ">" in (c.get("sqltext") or "")
            for c in checks
        )
        assert found, (
            "training_goals must declare CHECK constraint "
            "`target_time_minutes IS NULL OR target_time_minutes > 0`."
        )

    async def test_target_distance_zero_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "td-zero@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            target_distance_km=0,
            target_time_minutes=40,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_target_time_negative_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "tt-neg@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            target_distance_km=10.0,
            target_time_minutes=-1,
        )
        db_session.add(goal)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Cascade behavior + FK.
# ---------------------------------------------------------------------------


class TestTrainingGoalForeignKeyCascade:
    async def test_goal_rows_cascade_with_athlete(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "cascade-goal@example.com")
        goal = _goal_factory(athlete_id=athlete.id)
        db_session.add(goal)
        await db_session.flush()
        goal_id = goal.id

        from sqlalchemy import delete as sa_delete

        await db_session.execute(
            sa_delete(Athlete).where(Athlete.id == athlete.id)
        )
        await db_session.commit()

        from sqlalchemy import select

        remaining = await db_session.execute(
            select(TrainingGoal).where(TrainingGoal.id == goal_id)
        )
        assert remaining.scalar_one_or_none() is None

    def test_athlete_id_fk_to_athletes_table(self) -> None:
        """``sport_background`` style: name-independent FK check."""
        fks = db_foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "athletes"
            and tuple(fk.get("constrained_columns") or ()) == ("athlete_id",)
        ]
        assert matches, (
            "training_goals.athlete_id must reference athletes(id). "
            f"Got: {fks}"
        )


# ---------------------------------------------------------------------------
# Persistence — happy-path insert + enum round-trip.
# ---------------------------------------------------------------------------


class TestTrainingGoalPersistence:
    async def test_full_goal_persists_and_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import date

        athlete = await make_athlete(db_session, "round-trip@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            goal_event_type=GoalEventType.MARATHON,
            goal_event_name="Lisbon Marathon",
            goal_event_date=date(2026, 10, 12),
            weekly_volume_hours=8.5,
            weekly_volume_km=60.0,
            fitness_level=4,
            target_distance_km=42.0,
            target_time_minutes=180,
        )
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)

        assert goal.id is not None
        assert goal.athlete_id == athlete.id
        assert goal.goal_type is GoalType.RACE_EVENT
        assert goal.goal_event_type is GoalEventType.MARATHON
        assert goal.goal_event_name == "Lisbon Marathon"
        assert goal.weekly_volume_hours == 8.5
        assert goal.fitness_level == 4
        assert goal.target_distance_km == 42.0
        assert goal.target_time_minutes == 180
        assert goal.status is TrainingGoalStatus.ACTIVE
        assert goal.created_at is not None

    async def test_recovery_goal_with_injury_severity(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "recovery-goal@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id,
            goal_type=GoalType.RECOVERY,
            injury_severity=InjurySeverity.MODERATE,
            recent_injury="Achilles tendinopathy flare",
        )
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)
        assert goal.injury_severity is InjurySeverity.MODERATE
        assert goal.recent_injury == "Achilles tendinopathy flare"

    async def test_minimal_goal_without_event_details(
        self, db_session: AsyncSession
    ) -> None:
        """``fitness_improvement`` goals have no event fields populated."""
        athlete = await make_athlete(db_session, "minimal-goal@example.com")
        goal = _goal_factory(
            athlete_id=athlete.id, goal_type=GoalType.FITNESS_IMPROVEMENT
        )
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)
        assert goal.goal_event_type is None
        assert goal.goal_event_name is None
        assert goal.goal_event_date is None
        assert goal.custom_distance_km is None
        assert goal.injury_severity is None
        assert goal.target_distance_km is None
        assert goal.target_time_minutes is None
