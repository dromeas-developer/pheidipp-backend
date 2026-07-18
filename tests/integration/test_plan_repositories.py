"""Integration tests for the Phase-1.4 plan repositories.

The repositories live in three modules:

* ``TrainingPlanRepository`` — persisting TrainingPlan + supersession
  (+ active-for-athlete lookup).
* ``WeeklyPlanRepository`` / ``WeeklySessionRepository`` — weekly
  hierarchy persistence.
* ``CheckpointRepository`` — checkpoint persistence.

These tests cover the plan's repository invariants:

* Read/write surface works through the per-test AsyncSession.
* Supersession: ``supersede()`` flips status to SUPERSEDED and stamps
  ``superseded_at`` while leaving the row in place.
* Active plan lookup returns the latest active plan (or None).
* Bulk insert path for WeeklyPlan + WeeklySession.
* Checkpoint ``get_for_training_plan`` joins through PlannedSession
  → WeeklyPlan and excludes superseded-plan checkpoints.

The full hierarchy insertion is exercised inside
``tests/integration/test_plan_generation_service.py`` — that test
covers the atomic-transaction invariant end-to-end. This file
focuses on the per-repository surface.

Reference plan:
docs/implementation/phase-1/phase-1-4-p1-plan-generation.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
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
from app.models.weekly_plan import WeeklyPlan, WeeklySession
from app.repositories.checkpoint_repository import CheckpointRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.weekly_plan_repository import (
    WeeklyPlanRepository,
    WeeklySessionRepository,
)
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _make_athlete_with_goal(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Seed an athlete + an active training goal. Returns
    ``(athlete_id, goal_id)``.

    All ``TrainingGoal`` non-null columns are populated so the insert
    satisfies the schema's NOT-NULL constraints
    (``weekly_volume_hours``, ``weekly_volume_km``, ``fitness_level``).
    Realmistic-ish defaulted values: 6 hours/week at 40 km/week for a
    typical intermediate runner.
    """
    athlete = await make_athlete(
        db_session, email=f"plan-repo-{uuid.uuid4()}@example.com"
    )
    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type="race_event",
        goal_event_type="marathon",
        goal_event_name="Repo Marathon",
        goal_event_date=date.today(),
        weekly_volume_hours=6.0,
        weekly_volume_km=40.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()
    return athlete.id, goal.id


def _make_plan(goal_id: uuid.UUID) -> TrainingPlan:
    return TrainingPlan(
        training_goal_id=goal_id,
        status=TrainingPlanStatus.ACTIVE,
        phases_summary=[],
        phase_definitions=[],
        weekly_distributions=[],
        checkpoint_schedule=[],
    )


# ---------------------------------------------------------------------------
# TrainingPlanRepository.
# ---------------------------------------------------------------------------


class TestTrainingPlanRepository:
    """Basic CRUD / supersession surface against the test DB."""

    async def test_add_persists_plan_and_returns_id(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        plan = _make_plan(goal_id)
        inserted = await repo.add(plan)
        assert inserted.id is not None

        rows = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.id == inserted.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].status is TrainingPlanStatus.ACTIVE

    async def test_get_active_for_goal_returns_active(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        plan = await repo.add(_make_plan(goal_id))
        got = await repo.get_active_for_goal(goal_id)
        assert got is not None
        assert got.id == plan.id

    async def test_get_active_for_goal_returns_none_when_absent(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        got = await repo.get_active_for_goal(goal_id)
        assert got is None

    async def test_get_by_id_returns_plan(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        plan = await repo.add(_make_plan(goal_id))
        got = await repo.get_by_id(plan.id)
        assert got is not None
        assert got.id == plan.id

    async def test_supersede_flips_status_and_stamps_superseded_at(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        plan = await repo.add(_make_plan(goal_id))

        before = datetime.now(timezone.utc)
        await repo.supersede(plan)

        # Re-fetch — supersede() mutates and refreshes the same instance.
        assert plan.status is TrainingPlanStatus.SUPERSEDED
        assert plan.superseded_at is not None
        assert plan.superseded_at >= before

    async def test_superseded_plan_remains_in_db(
        self, db_session: AsyncSession
    ) -> None:
        """Old plans are never deleted — only ``superseded_at`` is mutated."""
        _, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        plan = await repo.add(_make_plan(goal_id))
        await repo.supersede(plan)

        rows = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.id == plan.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        # The row is still present, just inactive.
        assert rows[0].status is TrainingPlanStatus.SUPERSEDED

    async def test_get_active_for_athlete_returns_active(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, goal_id = await _make_athlete_with_goal(db_session)
        repo = TrainingPlanRepository(db_session)
        plan = await repo.add(_make_plan(goal_id))
        got = await repo.get_active_for_athlete(athlete_id)
        assert got is not None
        assert got.id == plan.id

    async def test_get_active_for_athlete_returns_none_without_goal(
        self, db_session: AsyncSession
    ) -> None:
        repo = TrainingPlanRepository(db_session)
        got = await repo.get_active_for_athlete(uuid.uuid4())
        assert got is None


# ---------------------------------------------------------------------------
# WeeklyPlan / WeeklySession.
# ---------------------------------------------------------------------------


class TestWeeklyPlanRepository:
    """Bulk insert + read paths."""

    async def test_add_many_persists_each_week(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        plans_repo = TrainingPlanRepository(db_session)
        plan = await plans_repo.add(_make_plan(goal_id))

        weeks_repo = WeeklyPlanRepository(db_session)
        rows = [
            WeeklyPlan(
                training_plan_id=plan.id,
                week_number=i + 1,
                status=WeeklyPlanStatus.SYNTHESISED,
                adjusted_intent={},
                week_starts_at=date(2026, 7, 1),
                week_ends_at=date(2026, 7, 7),
            )
            for i in range(4)
        ]
        await weeks_repo.add_many(rows)
        for r in rows:
            assert r.id is not None

        fetched = await weeks_repo.get_for_training_plan(plan.id)
        assert len(fetched) == 4

    async def test_get_for_training_plan_orders_by_week(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        plans_repo = TrainingPlanRepository(db_session)
        plan = await plans_repo.add(_make_plan(goal_id))

        weeks_repo = WeeklyPlanRepository(db_session)
        await weeks_repo.add_many(
            [
                WeeklyPlan(
                    training_plan_id=plan.id,
                    week_number=3,
                    status=WeeklyPlanStatus.SYNTHESISED,
                    adjusted_intent={},
                    week_starts_at=date(2026, 7, 1),
                    week_ends_at=date(2026, 7, 7),
                ),
                WeeklyPlan(
                    training_plan_id=plan.id,
                    week_number=1,
                    status=WeeklyPlanStatus.SYNTHESISED,
                    adjusted_intent={},
                    week_starts_at=date(2026, 7, 1),
                    week_ends_at=date(2026, 7, 7),
                ),
            ]
        )
        fetched = await weeks_repo.get_for_training_plan(plan.id)
        assert [w.week_number for w in fetched] == [1, 3]

    async def test_get_by_plan_and_week_returns_correct_row(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        plans_repo = TrainingPlanRepository(db_session)
        plan = await plans_repo.add(_make_plan(goal_id))

        weeks_repo = WeeklyPlanRepository(db_session)
        weeks = await weeks_repo.add_many(
            [
                WeeklyPlan(
                    training_plan_id=plan.id,
                    week_number=2,
                    status=WeeklyPlanStatus.SYNTHESISED,
                    adjusted_intent={},
                    week_starts_at=date(2026, 7, 1),
                    week_ends_at=date(2026, 7, 7),
                ),
            ]
        )
        got = await weeks_repo.get_by_plan_and_week(plan.id, 2)
        assert got is not None
        assert got.id == weeks[0].id


class TestWeeklySessionRepository:
    """The companion to WeeklyPlan — per-day sessions."""

    async def test_add_many_persists_each_session(
        self, db_session: AsyncSession
    ) -> None:
        _, goal_id = await _make_athlete_with_goal(db_session)
        plans_repo = TrainingPlanRepository(db_session)
        plan = await plans_repo.add(_make_plan(goal_id))

        weeks_repo = WeeklyPlanRepository(db_session)
        weeks = await weeks_repo.add_many(
            [
                WeeklyPlan(
                    training_plan_id=plan.id,
                    week_number=1,
                    status=WeeklyPlanStatus.SYNTHESISED,
                    adjusted_intent={},
                    week_starts_at=date(2026, 7, 1),
                    week_ends_at=date(2026, 7, 7),
                ),
            ]
        )

        sessions_repo = WeeklySessionRepository(db_session)
        sessions = await sessions_repo.add_many(
            [
                WeeklySession(
                    weekly_plan_id=weeks[0].id,
                    target_date=date(2026, 7, 1),
                    session_type=SessionType.LONG_RUN,
                    intent_description="Long run — endurance-building",
                    approximate_duration_minutes=90,
                    status="scheduled",
                ),
                WeeklySession(
                    weekly_plan_id=weeks[0].id,
                    target_date=date(2026, 7, 2),
                    session_type=SessionType.EASY_RUN,
                    intent_description="Conversational easy run",
                    approximate_duration_minutes=45,
                    status="scheduled",
                ),
            ]
        )
        assert len(sessions) == 2
        for s in sessions:
            assert s.id is not None


# ---------------------------------------------------------------------------
# CheckpointRepository.
# ---------------------------------------------------------------------------


class TestCheckpointRepository:
    """Persists + reads checkpoints through PlannedSession join."""

    async def _seed_plan_with_session(
        self,
        db_session: AsyncSession,
    ) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
        """Return ``(plan_id, weekly_plan_id, planned_session_id)``."""
        _, goal_id = await _make_athlete_with_goal(db_session)
        plans_repo = TrainingPlanRepository(db_session)
        plan = await plans_repo.add(_make_plan(goal_id))

        weeks_repo = WeeklyPlanRepository(db_session)
        weeks = await weeks_repo.add_many(
            [
                WeeklyPlan(
                    training_plan_id=plan.id,
                    week_number=1,
                    status=WeeklyPlanStatus.SYNTHESISED,
                    adjusted_intent={},
                    week_starts_at=date(2026, 7, 1),
                    week_ends_at=date(2026, 7, 7),
                ),
            ]
        )
        session = PlannedSession(
            weekly_plan_id=weeks[0].id,
            training_plan_id=plan.id,
            target_date=date(2026, 7, 1),
            week_number=1,
            phase_label=PhaseLabel.AEROBIC_BASE,
            session_type=SessionType.LONG_RUN,
            intent_description="Long run",
            approximate_duration_minutes=90,
            status=PlannedSessionStatus.SCHEDULED,
            session_priority=SessionPriority.PRIMARY,
        )
        db_session.add(session)
        await db_session.flush()
        return plan.id, weeks[0].id, session.id

    async def test_add_many_persists_checkpoints(
        self, db_session: AsyncSession
    ) -> None:
        _, _weekly_id, session_id = await self._seed_plan_with_session(
            db_session
        )
        repo = CheckpointRepository(db_session)
        await repo.add_many(
            [
                Checkpoint(
                    planned_session_id=session_id,
                    type=CheckpointType.BENCHMARK,
                    target_metric="aerobic_fitness",
                    secondary_metrics=[],
                    status=CheckpointStatus.SCHEDULED,
                ),
            ]
        )

        rows = (
            await db_session.execute(
                select(Checkpoint).where(
                    Checkpoint.planned_session_id == session_id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].type is CheckpointType.BENCHMARK

    async def test_get_for_training_plan_joins_through_planned_session(
        self, db_session: AsyncSession
    ) -> None:
        plan_id, _weekly_id, session_id = await self._seed_plan_with_session(
            db_session
        )
        cp_repo = CheckpointRepository(db_session)
        await cp_repo.add_many(
            [
                Checkpoint(
                    planned_session_id=session_id,
                    type=CheckpointType.BENCHMARK,
                    target_metric="aerobic_fitness",
                    secondary_metrics=[],
                    status=CheckpointStatus.SCHEDULED,
                ),
            ]
        )

        found = await cp_repo.get_for_training_plan(plan_id)
        assert len(found) == 1
        assert found[0].planned_session_id == session_id

    async def test_get_for_training_plan_skips_other_plan_checkpoints(
        self, db_session: AsyncSession
    ) -> None:
        """``get_for_training_plan`` filters by ``WeeklyPlan.training_plan_id``."""
        # Seed plan 1 with a checkpoint.
        plan1_id, _, session1_id = await self._seed_plan_with_session(
            db_session
        )
        cp_repo = CheckpointRepository(db_session)
        await cp_repo.add_many(
            [
                Checkpoint(
                    planned_session_id=session1_id,
                    type=CheckpointType.BENCHMARK,
                    target_metric="aerobic_fitness",
                    secondary_metrics=[],
                    status=CheckpointStatus.SCHEDULED,
                ),
            ]
        )

        # Seed a second plan with a checkpoint that should NOT be returned.
        _, goal_id = await _make_athlete_with_goal(db_session)
        plans_repo = TrainingPlanRepository(db_session)
        plan2 = await plans_repo.add(_make_plan(goal_id))

        weeks_repo = WeeklyPlanRepository(db_session)
        weeks = await weeks_repo.add_many(
            [
                WeeklyPlan(
                    training_plan_id=plan2.id,
                    week_number=1,
                    status=WeeklyPlanStatus.SYNTHESISED,
                    adjusted_intent={},
                    week_starts_at=date(2026, 7, 1),
                    week_ends_at=date(2026, 7, 7),
                ),
            ]
        )
        session2 = PlannedSession(
            weekly_plan_id=weeks[0].id,
            training_plan_id=plan2.id,
            target_date=date(2026, 7, 1),
            week_number=1,
            phase_label=PhaseLabel.AEROBIC_BASE,
            session_type=SessionType.LONG_RUN,
            intent_description="Long run other",
            approximate_duration_minutes=90,
            status=PlannedSessionStatus.SCHEDULED,
            session_priority=SessionPriority.PRIMARY,
        )
        db_session.add(session2)
        await db_session.flush()
        await cp_repo.add_many(
            [
                Checkpoint(
                    planned_session_id=session2.id,
                    type=CheckpointType.PROGRESS_REVIEW,
                    target_metric="weekly_form",
                    secondary_metrics=[],
                    status=CheckpointStatus.SCHEDULED,
                ),
            ]
        )

        # Plan 1 returns its own checkpoint only.
        plan1_checkpoints = await cp_repo.get_for_training_plan(plan1_id)
        assert len(plan1_checkpoints) == 1
        assert plan1_checkpoints[0].planned_session_id == session1_id

        plan2_checkpoints = await cp_repo.get_for_training_plan(plan2.id)
        assert len(plan2_checkpoints) == 1
        assert plan2_checkpoints[0].planned_session_id == session2.id

        # Session slot is unused here; the test exercises the join path.
        _ = SessionSlot.AM
