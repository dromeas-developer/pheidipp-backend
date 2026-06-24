"""Integration tests for the ``Checkpoint`` schema at the DB level.

Phase-1.2b introduces the ``checkpoints`` table. The DB-level
invariants codified here are:

* One Checkpoint per PlannedSession — strict uniqueness +
  not-null on ``planned_session_id``.
* No redundant ``training_plan_id`` column — derivation goes
  through ``PlannedSession → WeeklyPlan → TrainingPlan``.
* Status enum is bounded to ``scheduled | completed | skipped``.
* Trajectory status, when present, is bounded to
  ``ahead | on_track | behind | at_risk``.
* Atomic completion fields are nullable until ``status`` transitions
  to ``completed`` (the application layer enforces atomicity).

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
from app.models.checkpoint import Checkpoint
from app.models.enums import (
    CheckpointStatus,
    CheckpointType,
    GoalType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan


TABLE = "checkpoints"


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


async def _new_active_plan_with_week_and_session(
    db_session: AsyncSession, athlete: Athlete
) -> tuple[TrainingPlan, WeeklyPlan, PlannedSession]:
    """Build the full chain: athlete → active goal → active plan →
    week → planned_session. The PlannedSession is the dedicated
    checkpoint host."""
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
        training_goal_id=goal.id, status=TrainingPlanStatus.ACTIVE
    )
    db_session.add(plan)
    await db_session.flush()
    week = WeeklyPlan(
        training_plan_id=plan.id,
        week_number=8,
        adjusted_intent={"session_count": 5},
        status="synthesised",
        week_starts_at=date(2026, 8, 17),
        week_ends_at=date(2026, 8, 23),
    )
    db_session.add(week)
    await db_session.flush()
    sess = PlannedSession(
        weekly_plan_id=week.id,
        training_plan_id=plan.id,
        target_date=date(2026, 8, 21),
        week_number=8,
        phase_label=PhaseLabel.THRESHOLD_BUILD,
        session_type=SessionType.THRESHOLD,
        intent_description="calibration threshold session",
        approximate_duration_minutes=50,
        status=PlannedSessionStatus.GENERATED,
        session_priority=SessionPriority.PRIMARY,
    )
    db_session.add(sess)
    await db_session.flush()
    return plan, week, sess


def _checkpoint_factory(
    *,
    planned_session_id: uuid.UUID,
    type: CheckpointType = CheckpointType.CALIBRATION,
    target_metric: str = "max_hr",
    secondary_metrics: list[str] | None = None,
    status: CheckpointStatus = CheckpointStatus.SCHEDULED,
) -> Checkpoint:
    return Checkpoint(
        planned_session_id=planned_session_id,
        type=type,
        target_metric=target_metric,
        secondary_metrics=secondary_metrics or [],
        status=status,
    )


# ---------------------------------------------------------------------------
# Column presence.
# ---------------------------------------------------------------------------


class TestCheckpointDBSchemaColumns:
    @pytest.mark.parametrize(
        "expected_column",
        [
            "id",
            "planned_session_id",
            "type",
            "target_metric",
            "secondary_metrics",
            "twin_update_expected",
            "replan_trigger",
            "status",
            "metric_updated",
            "confidence_changed",
            "replan_triggered",
            "trajectory_status",
            "proposal",
            "created_at",
            "completed_at",
        ],
    )
    async def test_required_column_present(
        self, db_session: AsyncSession, expected_column: str
    ) -> None:
        cols = {col["name"] for col in _columns(TABLE)}
        assert expected_column in cols, (
            f"checkpoints.{expected_column} missing from DB schema."
        )

    def test_no_training_plan_id_column(self) -> None:
        """Architecture forbids the redundant ``training_plan_id`` on
        checkpoints — derivation goes PlannedSession → WeeklyPlan →
        TrainingPlan."""
        cols = {col["name"] for col in _columns(TABLE)}
        assert "training_plan_id" not in cols, (
            "checkpoints must NOT carry training_plan_id — derivation "
            "goes through PlannedSession."
        )


# ---------------------------------------------------------------------------
# One-to-one uniqueness.
# ---------------------------------------------------------------------------


class TestCheckpointOneToOne:
    """``planned_session_id`` is UNIQUE and NOT NULL — one checkpoint
    per planned session. Redundancy is forbidden."""

    async def test_planned_session_id_unique_constraint(
        self, db_session: AsyncSession
    ) -> None:
        uniques = _unique_constraints(TABLE)
        col_level = next(
            c for c in _columns(TABLE) if c["name"] == "planned_session_id"
        )
        matched = [
            u for u in uniques
            if tuple(u.get("column_names") or ()) == ("planned_session_id",)
        ]
        assert matched or col_level.get("unique"), (
            "checkpoints.planned_session_id must be uniquely "
            "constrained — strict one-to-one with PlannedSession."
        )

    async def test_planned_session_id_is_not_null_in_schema(
        self, db_session: AsyncSession
    ) -> None:
        col = next(
            c for c in _columns(TABLE) if c["name"] == "planned_session_id"
        )
        assert col["nullable"] is False

    async def test_one_checkpoint_per_planned_session_unique(
        self, db_session: AsyncSession
    ) -> None:
        """Two checkpoints for the same PlannedSession must raise an
        ``IntegrityError`` at the DB layer (the unique constraint)."""
        athlete = await _new_athlete(db_session, "cp-dup-1to1@example.com")
        _, _, sess = await _new_active_plan_with_week_and_session(
            db_session, athlete
        )
        cp1 = _checkpoint_factory(planned_session_id=sess.id)
        cp2 = _checkpoint_factory(planned_session_id=sess.id)
        db_session.add_all([cp1, cp2])
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Foreign keys.
# ---------------------------------------------------------------------------


class TestCheckpointForeignKeyCascade:
    def test_planned_session_id_fk_to_planned_sessions_cascade(
        self, db_session: AsyncSession
    ) -> None:
        fks = _foreign_keys(TABLE)
        matches = [
            fk for fk in fks
            if fk.get("referred_table") == "planned_sessions"
            and tuple(fk.get("constrained_columns") or ())
            == ("planned_session_id",)
        ]
        assert matches, (
            "checkpoints.planned_session_id must reference "
            "planned_sessions(id)."
        )

    def test_fk_ondelete_cascade_in_pg_catalog(self) -> None:
        from sqlalchemy import text

        engine = create_engine(_sync_url())
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
                          AND confrelid_table.relname = 'planned_sessions'
                          AND conrelid_table.relname = 'checkpoints'
                        """
                    )
                ).fetchone()
        finally:
            engine.dispose()
        assert row is not None, (
            "checkpoints.planned_session_id FK must exist in pg_constraint."
        )
        assert row[0] == "c", (
            "checkpoints.planned_session_id FK must CASCADE on delete. "
            f"Got confdeltype={row[0]!r}, def={row[1]}"
        )

    async def test_cascade_delete_with_planned_session(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "cp-cascade@example.com")
        _, _, sess = await _new_active_plan_with_week_and_session(
            db_session, athlete
        )
        cp = _checkpoint_factory(planned_session_id=sess.id)
        db_session.add(cp)
        await db_session.flush()
        cp_id = cp.id

        from sqlalchemy import delete as sa_delete, select

        await db_session.execute(
            sa_delete(PlannedSession).where(PlannedSession.id == sess.id)
        )
        await db_session.commit()

        remaining = await db_session.execute(
            select(Checkpoint).where(Checkpoint.id == cp_id)
        )
        assert remaining.scalar_one_or_none() is None


# ---------------------------------------------------------------------------
# CHECK constraints.
# ---------------------------------------------------------------------------


class TestCheckpointCheckConstraints:
    def test_status_inline_union_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "")
            for c in _check_constraints(TABLE)
        ).lower()
        assert "scheduled" in text and "completed" in text and "skipped" in text, (
            "checkpoints.status check must include `scheduled`, "
            "`completed`, and `skipped`."
        )

    def test_trajectory_status_inline_union_check(self) -> None:
        text = " | ".join(
            (c.get("sqltext") or "")
            for c in _check_constraints(TABLE)
        ).lower()
        assert "trajectory_status" in text
        for val in ("ahead", "on_track", "behind", "at_risk"):
            assert val in text, (
                f"checkpoints.trajectory_status check must include "
                f"`{val}`. Got: {text!r}"
            )

    async def test_invalid_status_value_rejected(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _new_athlete(db_session, "cp-status-bad@example.com")
        _, _, sess = await _new_active_plan_with_week_and_session(
            db_session, athlete
        )
        cp = _checkpoint_factory(
            planned_session_id=sess.id, status="bad_status"
        )
        db_session.add(cp)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()


# ---------------------------------------------------------------------------
# Persistence — happy path and completion atomicity.
# ---------------------------------------------------------------------------


class TestCheckpointPersistence:
    async def test_full_checkpoint_persists_and_round_trips(
        self, db_session: AsyncSession
    ) -> None:
        from datetime import datetime, timezone

        athlete = await _new_athlete(db_session, "cp-rt@example.com")
        _, _, sess = await _new_active_plan_with_week_and_session(
            db_session, athlete
        )
        cp = _checkpoint_factory(
            planned_session_id=sess.id,
            type=CheckpointType.BENCHMARK,
            target_metric="5k_time",
            secondary_metrics=["hr_dropout_pct", "laps_consistency"],
        )
        cp.twin_update_expected = True
        cp.replan_trigger = True
        cp.trajectory_status = "on_track"
        cp.proposal = "Continue with the planned VO2max block."
        cp.status = CheckpointStatus.COMPLETED
        cp.metric_updated = True
        cp.confidence_changed = True
        cp.replan_triggered = False
        cp.completed_at = datetime.now(timezone.utc)
        db_session.add(cp)
        await db_session.flush()
        await db_session.refresh(cp)

        assert cp.id is not None
        assert cp.planned_session_id == sess.id
        assert cp.type is CheckpointType.BENCHMARK
        assert cp.target_metric == "5k_time"
        assert cp.secondary_metrics == ["hr_dropout_pct", "laps_consistency"]
        assert cp.twin_update_expected is True
        assert cp.replan_trigger is True
        assert cp.trajectory_status == "on_track"
        assert cp.status is CheckpointStatus.COMPLETED
        assert cp.metric_updated is True
        assert cp.confidence_changed is True
        assert cp.replan_triggered is False
        assert cp.completed_at is not None

    async def test_default_status_is_scheduled(
        self, db_session: AsyncSession
    ) -> None:
        """``status`` server-defaults to scheduled; no completion
        fields populated yet."""
        athlete = await _new_athlete(db_session, "cp-default@example.com")
        _, _, sess = await _new_active_plan_with_week_and_session(
            db_session, athlete
        )
        cp = _checkpoint_factory(planned_session_id=sess.id)
        db_session.add(cp)
        await db_session.flush()
        await db_session.refresh(cp)
        assert cp.status is CheckpointStatus.SCHEDULED
        assert cp.metric_updated is None
        assert cp.confidence_changed is None
        assert cp.replan_triggered is None
        assert cp.completed_at is None

    async def test_secondary_metrics_persist_as_array(
        self, db_session: AsyncSession
    ) -> None:
        """``secondary_metrics`` is an ARRAY(String) and round-trips
        with multiple distinct values."""
        athlete = await _new_athlete(db_session, "cp-array@example.com")
        _, _, sess = await _new_active_plan_with_week_and_session(
            db_session, athlete
        )
        metrics = ["hr_dropout_pct", "gps_loss_m", "elevated_laxity_risk"]
        cp = _checkpoint_factory(
            planned_session_id=sess.id,
            secondary_metrics=metrics,
        )
        db_session.add(cp)
        await db_session.flush()
        await db_session.refresh(cp)
        assert cp.secondary_metrics == metrics


# ---------------------------------------------------------------------------
# Indexes.
# ---------------------------------------------------------------------------


class TestCheckpointIndexes:
    def test_type_status_index_present(self) -> None:
        matched = [
            idx for idx in _indexes(TABLE)
            if set(idx.get("column_names") or []) >= {"type", "status"}
        ]
        assert matched, (
            "Expected an index on (type, status) for the upcoming-"
            "checkpoint query path."
        )
