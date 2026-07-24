"""Integration tests for ``PlanQueryService`` against the test database.

The Phase-2.7 Batch 3 plan-router layer fix (closing G-07) introduces
``PlanQueryService`` in ``app/services/plan_query_service.py`` to own
the three read queries previously executed directly in
``app/api/v1/plan.py``. The service is read-only — it never commits,
never calls ``EventPublisher``, and never mutates state.

These tests exercise the three public methods against a real test
database with a fully-constructed plan graph (TrainingPlan →
WeeklyPlan → PlannedSession → Checkpoint) so the join-through-WeeklyPlan
path is verified end-to-end, not just at the SQL-string level.

Reference plan: ``docs/implementation/phase-2/phase-2-7/batch-3-event-flow-plan-router-fix.md``
Step 5 — Create ``PlanQueryService`` and fix plan-router layer-skip.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.checkpoint import Checkpoint
from app.models.enums import (
    CheckpointStatus,
    CheckpointType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    WeeklyPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan
from app.services.plan_query_service import PlanQueryService


# ---------------------------------------------------------------------------
# Helpers — plan-graph construction.
# ---------------------------------------------------------------------------


async def _make_goal(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
) -> TrainingGoal:
    goal = TrainingGoal(
        athlete_id=athlete_id,
        goal_type="race_event",
        goal_event_type="five_k",
        goal_event_name="Test 5K",
        goal_event_date=date.today() + timedelta(weeks=12),
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()
    return goal


async def _make_plan(
    db_session: AsyncSession,
    *,
    goal_id: uuid.UUID,
    status: TrainingPlanStatus = TrainingPlanStatus.ACTIVE,
) -> TrainingPlan:
    plan = TrainingPlan(
        training_goal_id=goal_id,
        twin_state_id=None,
        status=status,
        phases_summary=[],
        phase_definitions=[],
        weekly_distributions=[],
        checkpoint_schedule=[],
        strategic_rationale=None,
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


async def _make_weekly_plan(
    db_session: AsyncSession,
    *,
    training_plan_id: uuid.UUID,
    week_number: int,
    week_starts_at: date,
) -> WeeklyPlan:
    weekly = WeeklyPlan(
        training_plan_id=training_plan_id,
        week_number=week_number,
        adjusted_intent={},
        status=WeeklyPlanStatus.ACTIVE,
        sessions_completed=0,
        sessions_missed=0,
        sessions_skipped=0,
        week_starts_at=week_starts_at,
        week_ends_at=week_starts_at + timedelta(days=6),
    )
    db_session.add(weekly)
    await db_session.flush()
    return weekly


async def _make_planned_session(
    db_session: AsyncSession,
    *,
    weekly_plan_id: uuid.UUID,
    training_plan_id: uuid.UUID,
    target_date: date,
    session_type: SessionType = SessionType.EASY_RUN,
    slot: SessionSlot | None = None,
    week_number: int = 1,
    phase_label: PhaseLabel = PhaseLabel.AEROBIC_BASE,
    intent_description: str = "Easy aerobic run",
    approximate_duration_minutes: int = 45,
    session_priority: SessionPriority = SessionPriority.PRIMARY,
) -> PlannedSession:
    session = PlannedSession(
        weekly_plan_id=weekly_plan_id,
        training_plan_id=training_plan_id,
        target_date=target_date,
        week_number=week_number,
        session_type=session_type,
        session_slot=slot,
        session_priority=session_priority,
        phase_label=phase_label,
        intent_description=intent_description,
        approximate_duration_minutes=approximate_duration_minutes,
        block_position="middle",
        status=PlannedSessionStatus.SCHEDULED,
    )
    db_session.add(session)
    await db_session.flush()
    return session


async def _make_checkpoint(
    db_session: AsyncSession,
    *,
    planned_session_id: uuid.UUID,
    checkpoint_type: CheckpointType = CheckpointType.CALIBRATION,
) -> Checkpoint:
    checkpoint = Checkpoint(
        planned_session_id=planned_session_id,
        type=checkpoint_type,
        target_metric="lt1_hr_bpm",
        secondary_metrics=[],
        twin_update_expected=True,
        replan_trigger=False,
        status=CheckpointStatus.SCHEDULED,
    )
    db_session.add(checkpoint)
    await db_session.flush()
    return checkpoint


@pytest.fixture
def plan_query_service(db_session: AsyncSession) -> PlanQueryService:
    return PlanQueryService(session=db_session)


# ---------------------------------------------------------------------------
# get_sessions_for_plan
# ---------------------------------------------------------------------------


class TestGetSessionsForPlan:
    """``get_sessions_for_plan`` returns all PlannedSessions for the plan,
    joined through WeeklyPlan (staleness-safe)."""

    async def test_returns_sessions_for_plan(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        s1 = await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today(),
        )
        s2 = await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=2),
        )

        rows = await plan_query_service.get_sessions_for_plan(plan.id)
        returned_ids = {row.id for row in rows}
        assert returned_ids == {s1.id, s2.id}

    async def test_joins_through_weekly_plan_not_denormalized_column(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        """A session whose denormalized training_plan_id points at a
        DIFFERENT plan must NOT be returned when the join goes through
        WeeklyPlan — this proves the staleness-safe join is enforced,
        not the denormalized column."""
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan_a = await _make_plan(db_session, goal_id=goal.id)
        plan_b = await _make_plan(
            db_session,
            goal_id=goal.id,
            status=TrainingPlanStatus.SUPERSEDED,
        )
        week_a = await _make_weekly_plan(
            db_session,
            training_plan_id=plan_a.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        week_b = await _make_weekly_plan(
            db_session,
            training_plan_id=plan_b.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        s_a = await _make_planned_session(
            db_session,
            weekly_plan_id=week_a.id,
            training_plan_id=plan_a.id,
            target_date=date.today(),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week_b.id,
            training_plan_id=plan_b.id,
            target_date=date.today(),
        )

        rows = await plan_query_service.get_sessions_for_plan(plan_a.id)
        returned_ids = {row.id for row in rows}
        assert returned_ids == {s_a.id}

    async def test_returns_empty_list_when_no_sessions(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)

        rows = await plan_query_service.get_sessions_for_plan(plan.id)
        assert rows == []

    async def test_orders_by_target_date_ascending(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=3),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=1),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=2),
        )

        rows = await plan_query_service.get_sessions_for_plan(plan.id)
        dates = [row.target_date for row in rows]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# get_upcoming_sessions
# ---------------------------------------------------------------------------


class TestGetUpcomingSessions:
    """``get_upcoming_sessions`` returns up to ``limit`` sessions with
    ``target_date >= today``, ordered by target_date ascending."""

    async def test_filters_out_sessions_before_today(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today() - timedelta(days=7),
        )
        past = await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() - timedelta(days=1),
        )
        future = await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=1),
        )

        rows = await plan_query_service.get_upcoming_sessions(
            plan_id=plan.id, limit=5
        )
        returned_ids = {row.id for row in rows}
        assert past.id not in returned_ids
        assert future.id in returned_ids

    async def test_respects_limit(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        for offset in range(7):
            await _make_planned_session(
                db_session,
                weekly_plan_id=week.id,
                training_plan_id=plan.id,
                target_date=date.today() + timedelta(days=offset),
            )

        rows = await plan_query_service.get_upcoming_sessions(
            plan_id=plan.id, limit=3
        )
        assert len(rows) == 3

    async def test_default_limit_is_five(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        for offset in range(8):
            await _make_planned_session(
                db_session,
                weekly_plan_id=week.id,
                training_plan_id=plan.id,
                target_date=date.today() + timedelta(days=offset),
            )

        rows = await plan_query_service.get_upcoming_sessions(plan_id=plan.id)
        assert len(rows) == 5

    async def test_orders_by_target_date_ascending(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=5),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=1),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=3),
        )

        rows = await plan_query_service.get_upcoming_sessions(plan_id=plan.id)
        dates = [row.target_date for row in rows]
        assert dates == sorted(dates)


# ---------------------------------------------------------------------------
# get_checkpoints_for_plan
# ---------------------------------------------------------------------------


class TestGetCheckpointsForPlan:
    """``get_checkpoints_for_plan`` returns all Checkpoints for the plan,
    joined through PlannedSession → WeeklyPlan."""

    async def test_returns_checkpoints_for_plan(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        s1 = await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today(),
        )
        s2 = await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today() + timedelta(days=3),
        )
        c1 = await _make_checkpoint(
            db_session,
            planned_session_id=s1.id,
            checkpoint_type=CheckpointType.CALIBRATION,
        )
        c2 = await _make_checkpoint(
            db_session,
            planned_session_id=s2.id,
            checkpoint_type=CheckpointType.BENCHMARK,
        )

        rows = await plan_query_service.get_checkpoints_for_plan(plan.id)
        returned_ids = {row.id for row in rows}
        assert returned_ids == {c1.id, c2.id}

    async def test_joins_through_planned_session(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        """A checkpoint whose parent PlannedSession belongs to a
        different plan's WeeklyPlan must NOT be returned."""
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan_a = await _make_plan(db_session, goal_id=goal.id)
        plan_b = await _make_plan(
            db_session,
            goal_id=goal.id,
            status=TrainingPlanStatus.SUPERSEDED,
        )
        week_a = await _make_weekly_plan(
            db_session,
            training_plan_id=plan_a.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        week_b = await _make_weekly_plan(
            db_session,
            training_plan_id=plan_b.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        s_a = await _make_planned_session(
            db_session,
            weekly_plan_id=week_a.id,
            training_plan_id=plan_a.id,
            target_date=date.today(),
        )
        s_b = await _make_planned_session(
            db_session,
            weekly_plan_id=week_b.id,
            training_plan_id=plan_b.id,
            target_date=date.today(),
        )
        c_a = await _make_checkpoint(
            db_session, planned_session_id=s_a.id
        )
        await _make_checkpoint(
            db_session, planned_session_id=s_b.id
        )

        rows = await plan_query_service.get_checkpoints_for_plan(plan_a.id)
        returned_ids = {row.id for row in rows}
        assert returned_ids == {c_a.id}

    async def test_returns_empty_list_when_no_checkpoints(
        self,
        db_session: AsyncSession,
        plan_query_service: PlanQueryService,
    ) -> None:
        from tests.utils.factories import make_athlete

        athlete = await make_athlete(db_session)
        goal = await _make_goal(db_session, athlete_id=athlete.id)
        plan = await _make_plan(db_session, goal_id=goal.id)
        week = await _make_weekly_plan(
            db_session,
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=date.today(),
        )
        await _make_planned_session(
            db_session,
            weekly_plan_id=week.id,
            training_plan_id=plan.id,
            target_date=date.today(),
        )

        rows = await plan_query_service.get_checkpoints_for_plan(plan.id)
        assert rows == []
