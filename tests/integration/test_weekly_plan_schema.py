"""Integration tests for the ``WeeklyPlan`` and ``WeeklySession`` schemas at the DB level.

Phase-1.2b introduces both tables in a single migration. The DB-level
invariants codified here are:

* ``weekly_plans`` has a unique constraint on
  ``(training_plan_id, week_number)``.
* ``weekly_plans`` execution counters default to zero and persist
  non-negative.
* ``weekly_plans.week_number`` is positive (CHECK).
* ``weekly_sessions.status`` is the inline-union value
  ``scheduled | completed | skipped | missed``.
* ``weekly_sessions.block_position`` is the inline-union value
  ``first | middle | last``.
* ``weekly_sessions.planned_session_id`` is unique when non-null and
  nullable otherwise.
* ``weekly_sessions.approximate_duration_minutes`` is positive
  (CHECK).

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import (
    CheckpointType,
    GoalType,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    WeeklyPlanStatus,
)
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan, WeeklySession
from tests.utils.factories import make_athlete
from tests.utils.schema_helpers import (
    db_check_constraints,
    db_columns,
    db_foreign_keys,
    db_indexes,
    db_unique_constraints,
    get_sync_database_url,
)

WEEKLY_PLANS = "weekly_plans"
WEEKLY_SESSIONS = "weekly_sessions"


async def _new_active_plan(
    db_session: AsyncSession, athlete: Athlete
) -> TrainingPlan:
    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.FITNESS_IMPROVEMENT,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()
    plan = TrainingPlan(
        training_goal_id=goal.id,
        status=TrainingPlanStatus.ACTIVE,
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


async def _new_active_plan_with_closed_goal(
    db_session: AsyncSession, athlete: Athlete
) -> TrainingPlan:
    """Variant of ``_new_active_plan`` whose goal is closed
    (``completed``).

    Used by tests that need a SECOND TrainingPlan for the same
    athlete — ``ix_training_goals_athlete_active`` (a partial unique
    index on ``(athlete_id) WHERE status = 'active'``) forbids two
    active goals per athlete. Plan lifecycle is independent of
    goal status, so the plan can stay ACTIVE.
    """
    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.FITNESS_IMPROVEMENT,
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.COMPLETED,
    )
    db_session.add(goal)
    await db_session.flush()
    plan = TrainingPlan(
        training_goal_id=goal.id,
        status=TrainingPlanStatus.ACTIVE,
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


def _weekly_plan_factory(
    *,
    training_plan_id: uuid.UUID,
    week_number: int = 1,
    week_starts_at: date | None = None,
    week_ends_at: date | None = None,
) -> WeeklyPlan:
    return WeeklyPlan(
        training_plan_id=training_plan_id,
        week_number=week_number,
        adjusted_intent={
            "methodology": "linear",
            "target_distribution": "80/20",
            "objectives": ["aerobic_base"],
            "session_count": 5,
            "adjustment_flags": {"missed_session_sweep": False},
        },
        status=WeeklyPlanStatus.SYNTHESISED,
        week_starts_at=week_starts_at or date(2026, 6, 22),
        week_ends_at=week_ends_at or date(2026, 6, 28),
    )


def _weekly_session_factory(
    *,
    weekly_plan_id: uuid.UUID,
    target_date: date,
    session_type: SessionType = SessionType.EASY_RUN,
    status: str = "scheduled",
    is_checkpoint: bool = False,
    checkpoint_type: CheckpointType | None = None,
    checkpoint_metric: str | None = None,
    intended_duration_minutes: int = 45,
    planned_session_id: uuid.UUID | None = None,
) -> WeeklySession:
    sess = WeeklySession(
        weekly_plan_id=weekly_plan_id,
        target_date=target_date,
        session_type=session_type,
        intent_description="comfortable aerobic",
        approximate_duration_minutes=intended_duration_minutes,
        is_checkpoint=is_checkpoint,
        checkpoint_type=checkpoint_type,
        checkpoint_metric=checkpoint_metric,
        status=status,
        planned_session_id=planned_session_id,
    )
    return sess


# ===========================================================================
# WeeklyPlan
# ===========================================================================


class TestWeeklyPlanDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "training_plan_id",
            "week_number",
            "adjusted_intent",
            "status",
            "sessions_completed",
            "sessions_missed",
            "sessions_skipped",
            "accumulated_fatigue_delta",
            "doubles_days_count",
            "created_at",
            "week_starts_at",
            "week_ends_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(WEEKLY_PLANS)}
        assert expected_column in cols, (
            f"weekly_plans.{expected_column} missing from DB schema."
        )


class TestWeeklyPlanUniqueConstraint:
    """One WeeklyPlan per week per TrainingPlan."""

    async def test_plan_week_unique_constraint_present(
        self, db_session: AsyncSession
    ) -> None:
        uniques = db_unique_constraints(WEEKLY_PLANS)
        matched = [
            u
            for u in uniques
            if tuple(u.get("column_names") or ())
            == ("training_plan_id", "week_number")
        ]
        assert matched, (
            "weekly_plans must have a UNIQUE constraint on "
            "(training_plan_id, week_number). Got: "
            f"{[u.get('column_names') for u in uniques]}"
        )

    async def test_duplicate_week_for_same_plan_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "dup-week@example.com")
        plan = await _new_active_plan(db_session, athlete)
        w1 = _weekly_plan_factory(training_plan_id=plan.id, week_number=3)
        w2 = _weekly_plan_factory(training_plan_id=plan.id, week_number=3)
        db_session.add_all([w1, w2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_same_week_different_plans_both_persist(
        self, db_session: AsyncSession
    ) -> None:
        """Week uniqueness is plan-scoped, not goal-scoped. Two
        TrainingPlans (linked to two distinct TrainingGoals of the
        SAME athlete) both get their own WeeklyPlan row for week 2.

        The two-goals-per-athlete constraint is enforced by the
        partial unique index ``ix_training_goals_athlete_active``
        (``WHERE status = 'active'``), so the second goal must be
        in a closed status (``COMPLETED``). The plan lifecycle is
        independent of the goal lifecycle, so the second plan can
        stay ACTIVE.
        """
        athlete = await make_athlete(db_session, "week-different-plan@example.com")
        plan_a = await _new_active_plan(db_session, athlete)
        plan_b = await _new_active_plan_with_closed_goal(db_session, athlete)
        w_a = _weekly_plan_factory(training_plan_id=plan_a.id, week_number=2)
        w_b = _weekly_plan_factory(training_plan_id=plan_b.id, week_number=2)
        db_session.add_all([w_a, w_b])
        await db_session.flush()
        await db_session.refresh(w_a)
        await db_session.refresh(w_b)
        assert w_a.id != w_b.id
        assert w_a.training_plan_id == plan_a.id
        assert w_b.training_plan_id == plan_b.id


class TestWeeklyPlanCheckConstraints:
    def test_week_number_positive_check(self) -> None:
        checks = db_check_constraints(WEEKLY_PLANS)
        found = any(
            "week_number" in (c.get("sqltext") or "").lower()
            and ">=" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "weekly_plans must declare CHECK constraint "
            "`week_number >= 1`."
        )

    def test_session_counters_non_negative_check(self) -> None:
        checks = db_check_constraints(WEEKLY_PLANS)
        text = " | ".join((c.get("sqltext") or "") for c in checks)
        found = (
            "sessions_completed" in text
            and "sessions_missed" in text
            and "sessions_skipped" in text
            and ">=" in text
        )
        assert found, (
            "weekly_plans must declare a CHECK constraint ensuring "
            "all three session counters are non-negative."
        )

    def test_doubles_days_count_non_negative_check(self) -> None:
        checks = db_check_constraints(WEEKLY_PLANS)
        found = any(
            "doubles_days_count" in (c.get("sqltext") or "").lower()
            and ">=" in (c.get("sqltext") or "").lower()
            for c in checks
        )
        assert found, (
            "weekly_plans must declare CHECK constraint "
            "`doubles_days_count >= 0`."
        )

    async def test_week_number_zero_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "wn-zero@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id, week_number=0)
        db_session.add(week)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_negative_week_number_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "wn-neg@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id, week_number=-1)
        db_session.add(week)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_zero_session_counters_accepted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "counters-zero@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()
        await db_session.refresh(week)
        assert week.sessions_completed == 0
        assert week.sessions_missed == 0
        assert week.sessions_skipped == 0
        assert week.doubles_days_count == 0

    async def test_negative_session_completed_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "sc-neg@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        week.sessions_completed = -1
        db_session.add(week)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestWeeklyPlanForeignKeyCascade:
    def test_training_plan_id_fk_to_training_plans(self) -> None:
        fks = db_foreign_keys(WEEKLY_PLANS)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "training_plans"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_plan_id",)
        ]
        assert matches, (
            "weekly_plans.training_plan_id must reference "
            "training_plans(id)."
        )

    def test_training_plan_id_fk_cascade_in_pg_catalog(self) -> None:
        from sqlalchemy import text

        engine = create_engine(get_sync_database_url())
        try:
            with engine.connect() as conn:
                row = conn.execute(
                    text(
                        """
                        SELECT c.confdeltype,
                               pg_get_constraintdef(c.oid) AS constraint_def
                        FROM pg_constraint c
                        JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
                        JOIN pg_class confrelid_table ON confrelid_table.oid = c.confrelid
                        WHERE c.contype = 'f'
                          AND confrelid_table.relname = 'training_plans'
                          AND conrelid_table.relname = 'weekly_plans'
                        """
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "weekly_plans.training_plan_id FK must exist in pg_constraint."
        )
        assert row[0] == "c", (
            "weekly_plans.training_plan_id FK must CASCADE on delete. "
            f"Got: {row[1]}"
        )

    async def test_cascade_delete_with_plan(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "cascade-wp@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()
        week_id = week.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(TrainingPlan).where(TrainingPlan.id == plan.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(WeeklyPlan).where(WeeklyPlan.id == week_id)
        )
        assert remaining.scalar_one_or_none() is None


class TestWeeklyPlanPersistence:
    async def test_full_weekly_plan_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "wp-rt@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date(2026, 6, 22),
            week_ends_at=date(2026, 6, 28),
        )
        db_session.add(week)
        await db_session.flush()
        await db_session.refresh(week)

        assert week.id is not None
        assert week.training_plan_id == plan.id
        assert week.week_number == 1
        assert week.week_starts_at == date(2026, 6, 22)
        assert week.week_ends_at == date(2026, 6, 28)
        assert week.status is WeeklyPlanStatus.SYNTHESISED
        assert week.adjusted_intent["methodology"] == "linear"

    async def test_jsonb_round_trip_preserves_shape(
        self, db_session: AsyncSession
    ) -> None:
        """The structured ``adjusted_intent`` JSONB survives
        persistence with every key intact."""
        athlete = await make_athlete(db_session, "wp-jsonb@example.com")
        plan = await _new_active_plan(db_session, athlete)
        intent = {
            "methodology": "linear",
            "target_distribution": {"easy": 0.6, "moderate": 0.3, "hard": 0.1},
            "objectives": ["aerobic_base", "durability"],
            "session_count": 5,
            "adjustment_flags": {
                "missed_session_sweep": True,
                "fatigue_compensation": False,
            },
        }
        week = _weekly_plan_factory(training_plan_id=plan.id)
        week.adjusted_intent = intent
        db_session.add(week)
        await db_session.flush()
        await db_session.refresh(week)
        assert week.adjusted_intent == intent


# ===========================================================================
# WeeklySession
# ===========================================================================


class TestWeeklySessionDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "weekly_plan_id",
            "target_date",
            "session_type",
            "intent_description",
            "approximate_duration_minutes",
            "is_checkpoint",
            "checkpoint_type",
            "checkpoint_metric",
            "status",
            "planned_session_id",
            "block_id",
            "block_position",
            "block_session_count",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in db_columns(WEEKLY_SESSIONS)}
        assert expected_column in cols, (
            f"weekly_sessions.{expected_column} missing from DB schema."
        )


class TestWeeklySessionUniqueConstraint:
    """``planned_session_id`` is unique when non-null. Multiple
    sessions with NULL ``planned_session_id`` may coexist because
    SQL NULL = NULL is false."""

    async def test_planned_session_id_unique_constraint_present(
        self, db_session: AsyncSession
    ) -> None:
        uniques = db_unique_constraints(WEEKLY_SESSIONS)
        col_level = next(
            c
            for c in db_columns(WEEKLY_SESSIONS)
            if c["name"] == "planned_session_id"
        )
        matched = [
            u
            for u in uniques
            if tuple(u.get("column_names") or ()) == ("planned_session_id",)
        ]
        assert matched or col_level.get("unique"), (
            "weekly_sessions.planned_session_id must be uniquely "
            "constrained so one WeeklySession maps to at most one "
            "PlannedSession. Got constraints: "
            f"{[u.get('column_names') for u in uniques]} "
            f"and column.unique={col_level.get('unique')}"
        )

    async def test_two_sessions_share_null_planned_session_id(
        self, db_session: AsyncSession
    ) -> None:
        """Multiple NULL ``planned_session_id`` rows coexist — the
        uniqueness only kicks in when value is non-null."""
        athlete = await make_athlete(db_session, "ws-null-pn@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()

        s1 = _weekly_session_factory(
            weekly_plan_id=week.id, target_date=date(2026, 6, 22),
        )
        s2 = _weekly_session_factory(
            weekly_plan_id=week.id, target_date=date(2026, 6, 23),
        )
        # Both have NULL planned_session_id by default.
        db_session.add_all([s1, s2])
        await db_session.flush()
        await db_session.refresh(s1)
        await db_session.refresh(s2)
        assert s1.planned_session_id is None
        assert s2.planned_session_id is None
        assert s1.id != s2.id

    async def test_two_sessions_cannot_share_same_planned_session_id(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "ws-dup-pn@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()

        # Use a random UUID for planned_session_id; the FK to
        # planned_sessions is intentionally NOT present in the mapper
        # for WeeklySession (lazy FK).
        ps_id = uuid.uuid4()
        s1 = _weekly_session_factory(
            weekly_plan_id=week.id,
            target_date=date(2026, 6, 22),
            planned_session_id=ps_id,
        )
        s2 = _weekly_session_factory(
            weekly_plan_id=week.id,
            target_date=date(2026, 6, 23),
            planned_session_id=ps_id,
        )
        db_session.add_all([s1, s2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestWeeklySessionCheckConstraints:
    def test_status_inline_union_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "") for c in db_check_constraints(WEEKLY_SESSIONS)
        )
        for status_value in ("scheduled", "completed", "skipped", "missed"):
            assert status_value in text, (
                f"weekly_sessions.status check must include "
                f"`{status_value}`. Got: {text!r}"
            )

    def test_block_position_inline_union_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "") for c in db_check_constraints(WEEKLY_SESSIONS)
        ).lower()
        assert "block_position" in text
        for pos in ("first", "middle", "last"):
            assert pos in text, (
                f"weekly_sessions.block_position check must include "
                f"`{pos}`. Got: {text!r}"
            )

    def test_duration_positive_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "")
            for c in db_check_constraints(WEEKLY_SESSIONS)
        ).lower()
        assert "approximate_duration_minutes" in text and ">" in text

    async def test_zero_duration_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "ws-dur-zero@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()
        sess = _weekly_session_factory(
            weekly_plan_id=week.id,
            target_date=date(2026, 6, 22),
            intended_duration_minutes=0,
        )
        db_session.add(sess)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_negative_duration_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "ws-dur-neg@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()
        sess = _weekly_session_factory(
            weekly_plan_id=week.id,
            target_date=date(2026, 6, 22),
            intended_duration_minutes=-1,
        )
        db_session.add(sess)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_invalid_status_value_rejected(
        self, db_session: AsyncSession
    ) -> None:
        """An unexpected status MUST raise an IntegrityError at the
        DB layer (the inline-union CHECK binds it)."""
        athlete = await make_athlete(db_session, "ws-status-bad@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()
        sess = _weekly_session_factory(
            weekly_plan_id=week.id,
            target_date=date(2026, 6, 22),
            status="not_a_real_status",
        )
        db_session.add(sess)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


class TestWeeklySessionPersistence:
    async def test_checkpoint_session_persists(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "ws-cp@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()

        sess = _weekly_session_factory(
            weekly_plan_id=week.id,
            target_date=date(2026, 6, 26),
            session_type=SessionType.THRESHOLD,
            is_checkpoint=True,
            checkpoint_type=CheckpointType.BENCHMARK,
            checkpoint_metric="5k_time_minutes" if False else "5k_time",
        )
        # Defensive: the model only has checkpoint_metric as a string
        # column; the SessionType is fine.
        sess.checkpoint_metric = "5k_time"
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.is_checkpoint is True
        assert sess.checkpoint_type is CheckpointType.BENCHMARK
        assert sess.checkpoint_metric == "5k_time"

    async def test_session_persists_with_block_metadata(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session, "ws-block@example.com")
        plan = await _new_active_plan(db_session, athlete)
        week = _weekly_plan_factory(training_plan_id=plan.id)
        db_session.add(week)
        await db_session.flush()
        sess = _weekly_session_factory(
            weekly_plan_id=week.id, target_date=date(2026, 6, 22),
        )
        sess.block_id = "block-1"
        sess.block_position = "first"
        sess.block_session_count = 6
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.block_id == "block-1"
        assert sess.block_position == "first"
        assert sess.block_session_count == 6
