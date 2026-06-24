"""Integration tests for the ``PlannedSession`` schema at the DB level.

Phase-1.2b introduces the ``planned_sessions`` table. The DB-level
invariants codified here are:

* ``(weekly_plan_id, target_date, session_slot)`` is unique.
* The denormalised ``training_plan_id`` FK is populated at insert.
* ``session_slot`` is nullable for single-session days.
* ``activity_id`` is a free-standing nullable UUID — the FK to
  ``activities`` is intentionally NOT present at the schema layer
  (the activity contract is owned by ingestion services).
* ``approximate_duration_minutes > 0`` and ``week_number >= 1`` are
  CHECK-enforced.

Reference plan: docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md
"""

from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import (
    GoalType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan


TABLE = "planned_sessions"


def _sync_url() -> str:
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable not set")
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg2://",
        )
    return database_url


def _columns(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_columns(table))
    finally:
        engine.dispose()


def _unique_constraints(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_unique_constraints(table))
    finally:
        engine.dispose()


def _check_constraints(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_check_constraints(table))
    finally:
        engine.dispose()


def _indexes(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_indexes(table))
    finally:
        engine.dispose()


def _foreign_keys(table: str) -> list[dict]:
    engine = create_engine(_sync_url())
    try:
        with engine.connect() as conn:
            return list(inspect(conn).get_foreign_keys(table))
    finally:
        engine.dispose()


async def _new_athlete(db_session: AsyncSession, email: str) -> Athlete:
    a = Athlete(email=email)
    db_session.add(a)
    await db_session.flush()
    return a


async def _new_active_plan_with_week(
    db_session: AsyncSession, athlete: Athlete
) -> tuple[TrainingPlan, WeeklyPlan]:
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
    week = WeeklyPlan(
        training_plan_id=plan.id,
        week_number=1,
        adjusted_intent={"session_count": 5},
        status="synthesised",
        week_starts_at=date(2026, 6, 22),
        week_ends_at=date(2026, 6, 28),
    )
    db_session.add(week)
    await db_session.flush()
    return plan, week


def _planned_session_factory(
    *,
    weekly_plan_id: uuid.UUID,
    training_plan_id: uuid.UUID,
    target_date: date,
    session_type: SessionType = SessionType.EASY_RUN,
    session_slot: SessionSlot | None = None,
    session_priority: SessionPriority = SessionPriority.PRIMARY,
    week_number: int = 1,
    phase_label: PhaseLabel = PhaseLabel.AEROBIC_BASE,
    status: PlannedSessionStatus = PlannedSessionStatus.PENDING,
    activity_id: uuid.UUID | None = None,
    approximate_duration_minutes: int = 45,
) -> PlannedSession:
    return PlannedSession(
        weekly_plan_id=weekly_plan_id,
        training_plan_id=training_plan_id,
        target_date=target_date,
        week_number=week_number,
        phase_label=phase_label,
        session_type=session_type,
        intent_description="comfortable aerobic",
        approximate_duration_minutes=approximate_duration_minutes,
        status=status,
        activity_id=activity_id,
        session_slot=session_slot,
        session_priority=session_priority,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestPlannedSessionDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "weekly_plan_id",
            "training_plan_id",
            "target_date",
            "week_number",
            "phase_label",
            "session_type",
            "intent_description",
            "approximate_duration_minutes",
            "checkpoint_type",
            "checkpoint_metric",
            "status",
            "skip_reason",
            "redistributed_to_date",
            "activity_id",
            "session_slot",
            "session_priority",
            "block_id",
            "block_position",
            "block_session_count",
            "is_suggested",
            "created_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in _columns(TABLE)}
        assert expected_column in cols, (
            f"planned_sessions.{expected_column} missing from DB schema."
        )


# ---------------------------------------------------------------------------
# (weekly_plan_id, target_date, session_slot) UNIQUE — AM/PM disambiguation.
# ---------------------------------------------------------------------------


class TestPlannedSessionSlotDateUnique:
    async def test_plan_date_slot_unique_constraint_present(
        self, db_session: AsyncSession
    ) -> None:
        uniques = _unique_constraints(TABLE)
        matched = [
            u
            for u in uniques
            if tuple(u.get("column_names") or ())
            == ("weekly_plan_id", "target_date", "session_slot")
            and u.get("name") == "uq_planned_sessions_plan_date_slot"
        ]
        assert matched, (
            "planned_sessions must declare UNIQUE "
            "(weekly_plan_id, target_date, session_slot). Got: "
            f"{[u.get('column_names') for u in uniques]}"
        )

    async def test_double_day_am_pm_both_persist(
        self, db_session: AsyncSession
    ) -> None:
        """The AM/PM disambiguation contract: two PlannedSession rows
        for the same date with distinct slots (am vs pm) coexist."""
        athlete = await _new_athlete(db_session, "ps-double-day@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)

        sess_am = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 24),
            session_slot=SessionSlot.AM,
            session_type=SessionType.STRIDES,
            session_priority=SessionPriority.SECONDARY,
        )
        sess_pm = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 24),
            session_slot=SessionSlot.PM,
            session_type=SessionType.TEMPO,
            session_priority=SessionPriority.PRIMARY,
        )
        db_session.add_all([sess_am, sess_pm])
        await db_session.flush()
        await db_session.refresh(sess_am)
        await db_session.refresh(sess_pm)
        assert sess_am.id != sess_pm.id
        assert sess_am.session_slot is SessionSlot.AM
        assert sess_pm.session_slot is SessionSlot.PM

    async def test_duplicate_am_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-dup-am@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)

        sess_a = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 24),
            session_slot=SessionSlot.AM,
        )
        sess_b = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 24),
            session_slot=SessionSlot.AM,
        )
        db_session.add_all([sess_a, sess_b])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# activity_id has NO FK (intentional schema-only deferral).
# ---------------------------------------------------------------------------


class TestPlannedSessionActivityIdDeferred:
    """``planned_sessions.activity_id`` is a free-standing nullable
    UUID column. The FK to ``activities`` lands in a later migration
    once the activity contract is settled."""

    def test_no_fk_to_activities_on_activity_id(self) -> None:
        fks = _foreign_keys(TABLE)
        matches = [
            fk
            for fk in fks
            if fk.get("referred_table") == "activities"
            and tuple(fk.get("constrained_columns") or ()) == ("activity_id",)
        ]
        assert not matches, (
            "planned_sessions.activity_id must NOT carry an FK to "
            "activities in Phase-1.2b. Got: "
            f"{matches}"
        )

    async def test_random_activity_id_persists_with_no_fk_violation(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-act-deferred@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
            activity_id=uuid.uuid4(),  # no FK enforces, so persists
        )
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.activity_id is not None


# ---------------------------------------------------------------------------
# FKs to weekly_plans and training_plans.
# ---------------------------------------------------------------------------


class TestPlannedSessionForeignKeys:
    def test_weekly_plan_id_fk_to_weekly_plans(self) -> None:
        fks = _foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "weekly_plans"
            and tuple(fk.get("constrained_columns") or ())
            == ("weekly_plan_id",)
        ]
        assert matches, (
            "planned_sessions.weekly_plan_id must reference "
            "weekly_plans(id)."
        )

    def test_training_plan_id_fk_to_training_plans(self) -> None:
        fks = _foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "training_plans"
            and tuple(fk.get("constrained_columns") or ())
            == ("training_plan_id",)
        ]
        assert matches, (
            "planned_sessions.training_plan_id must reference "
            "training_plans(id). The denormalisation is intentional; "
            "the FK still enforces referential integrity."
        )

    async def test_cascade_delete_with_weekly_plan(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-cascade-wp@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
        )
        db_session.add(sess)
        await db_session.flush()
        sess_id = sess.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(WeeklyPlan).where(WeeklyPlan.id == week.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(PlannedSession).where(PlannedSession.id == sess_id)
        )
        assert remaining.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# CHECK constraints.
# ---------------------------------------------------------------------------


class TestPlannedSessionCheckConstraints:
    def test_block_position_inline_union_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "") for c in _check_constraints(TABLE)
        ).lower()
        assert "block_position" in text
        for pos in ("first", "middle", "last"):
            assert pos in text

    def test_duration_positive_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "").lower()
            for c in _check_constraints(TABLE)
        )
        assert "approximate_duration_minutes" in text and ">" in text

    def test_week_number_positive_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "").lower()
            for c in _check_constraints(TABLE)
        )
        assert "week_number" in text and ">= 1" in text

    async def test_zero_duration_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-dur-zero@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
            approximate_duration_minutes=0,
        )
        db_session.add(sess)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_week_number_zero_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-wn-zero@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
            week_number=0,
        )
        db_session.add(sess)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Is_suggested default + persistence.
# ---------------------------------------------------------------------------


class TestPlannedSessionDefaults:
    async def test_is_suggested_defaults_to_false(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-suggested@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
        )
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.is_suggested is False


class TestPlannedSessionPersistence:
    async def test_full_session_persists_and_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "ps-rt@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 26),
            session_type=SessionType.THRESHOLD,
            session_slot=SessionSlot.AM,
            session_priority=SessionPriority.PRIMARY,
            phase_label=PhaseLabel.THRESHOLD_BUILD,
            status=PlannedSessionStatus.GENERATED,
        )
        sess.checkpoint_type = "benchmark" if False else None
        sess.checkpoint_metric = "5k_time"
        sess.block_id = "block-2"
        sess.block_position = "middle"
        sess.block_session_count = 4
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.id is not None
        assert sess.training_plan_id == plan.id
        assert sess.weekly_plan_id == week.id
        assert sess.target_date == date(2026, 6, 26)
        assert sess.week_number == 1
        assert sess.phase_label is PhaseLabel.THRESHOLD_BUILD
        assert sess.session_type is SessionType.THRESHOLD
        assert sess.session_slot is SessionSlot.AM
        assert sess.session_priority is SessionPriority.PRIMARY
        assert sess.checkpoint_metric == "5k_time"
        assert sess.block_position == "middle"
        assert sess.status is PlannedSessionStatus.GENERATED

    async def test_session_with_null_slot_persists(
        self, db_session: AsyncSession
    ) -> None:
        """``session_slot = NULL`` for single-session days."""
        athlete = await _new_athlete(db_session, "ps-null-slot@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
            session_slot=None,  # single-session day
        )
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.session_slot is None

    async def test_skip_reason_persists(
        self, db_session: AsyncSession
    ) -> None:
        """The skip_reason field is a free-form text used when status
        transitions to ``skipped``."""
        athlete = await _new_athlete(db_session, "ps-skip@example.com")
        plan, week = await _new_active_plan_with_week(db_session, athlete)
        sess = _planned_session_factory(
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date(2026, 6, 22),
            status=PlannedSessionStatus.SKIPPED,
        )
        sess.skip_reason = "athlete illness"
        sess.redistributed_to_date = date(2026, 6, 23)
        db_session.add(sess)
        await db_session.flush()
        await db_session.refresh(sess)
        assert sess.skip_reason == "athlete illness"
        assert sess.redistributed_to_date == date(2026, 6, 23)
