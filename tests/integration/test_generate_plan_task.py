"""Integration tests for the ``generate_plan`` procrastinate worker task.

The Phase-2.7 Batch 3 plan wires ``generate_plan`` as a procrastinate
task deferred by ``OnboardingService.complete_onboarding()`` after
the TwinState insert fires ``twin_model_ready`` (Step 2). The task:

1. Opens its own ``AsyncSessionLocal``.
2. Constructs ``PlanGenerationService`` and calls
   ``generate_plan(athlete_id=...)``.
3. Defers ``generate_first_message`` after the plan is committed.

The task is idempotent: a second invocation for the same athlete
supersedes the first plan (the existing ``PlanGenerationService``
supersession logic handles re-generation).

These tests invoke the task function directly — the procrastinate
wrapper is not involved. ``AsyncSessionLocal`` is monkey-patched to
the test's ``test_session_local`` so the task's session shares the
test engine and event loop, mirroring the
``test_outbox_publisher_task_integration.py`` pattern.

Reference plan: ``docs/implementation/phase-2/phase-2-7/batch-3-event-flow-plan-router-fix.md``
Steps 2, 4.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.worker.app as worker_module
from app.models.athlete import Athlete
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    DataTier,
    GpsSource,
    GoalEventType,
    GoalType,
    HrSource,
    PlannedSessionStatus,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    Sex,
    SportBackground,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.athlete_fitness import AthleteFitness
from app.models.planned_session import PlannedSession
from app.models.system_event import SystemEvent
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from app.worker.app import generate_plan


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


@dataclass
class _RecordingDispatcher:
    """A fake that records every ``task.defer(**kwargs)`` call.

    Mirrors the procrastinate task ``.defer`` contract: a sync
    callable that takes ``**kwargs`` and returns a job-id-like
    value. ``call_log`` is a list of kwargs dicts in the order they
    were called.
    """

    call_log: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, **kwargs: Any) -> int:
        self.call_log.append(kwargs)
        return len(self.call_log)

    def defer(self, **kwargs: Any) -> int:
        return self(**kwargs)


async def _seed_onboarded_athlete_without_plan(
    db_session: AsyncSession,
) -> Athlete:
    """Insert the minimum state required for PlanGenerationService.generate()
    to succeed, without going through complete_onboarding (which would
    itself try to defer generate_plan)."""
    athlete = Athlete(email=f"plan-task-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()

    profile = AthleteProfile(
        athlete_id=athlete.id,
        timezone="Europe/Lisbon",
        training_window=None,
        height_cm=180.0,
        date_of_birth=date(1990, 1, 1),
        sex=Sex.NOT_SPECIFIED,
        structural_risk_flag=False,
    )
    db_session.add(profile)

    preferences = AthletePreferences(
        athlete_id=athlete.id,
        sport_background=SportBackground.RUNNING_PRIMARY,
        years_structured_training=3,
        training_time_of_day="morning",
        weekly_schedule={},
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.NONE,
        primary_training_platform=PrimaryTrainingPlatform.MANUAL,
    )
    db_session.add(preferences)

    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=GoalEventType.HALF_MARATHON,
        goal_event_name="Test Half Marathon",
        goal_event_date=date.today() + timedelta(weeks=16),
        weekly_volume_hours=6.0,
        weekly_volume_km=40.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    physiology = AthletePhysiology(
        athlete_id=athlete.id,
        max_hr={"value": 184.0, "dominant_source": "questionnaire_estimate"},
        lt1={"hr": {"value": 138.0, "dominant_source": "questionnaire_estimate"}},
        lt2={"hr": {"value": 161.0, "dominant_source": "questionnaire_estimate"}},
    )
    db_session.add(physiology)

    fitness = AthleteFitness(
        athlete_id=athlete.id,
        aggregate={"fitness": 0.0, "fatigue": 0.0, "form": 0.0},
        time_constants={
            "source": "population_default",
            "aerobic": {"fitness_tau_days": 42, "fatigue_tau_days": 7},
            "neuromuscular": {"fitness_tau_days": 7, "fatigue_tau_days": 3},
            "structural": {"fitness_tau_days": 56, "fatigue_tau_days": 14},
        },
    )
    db_session.add(fitness)

    twin = TwinState(
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        data_tier=DataTier.TIER_3,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1-questionnaire-bootstrap",
        fitness=0.0,
        fatigue=0.0,
        form=0.0,
        readiness_level=RecoveryModifierLevel.GREEN,
        metric_confidence={},
    )
    db_session.add(twin)
    await db_session.flush()

    return athlete


async def _run_generate_plan_task(
    test_session_local: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    athlete_id: uuid.UUID,
) -> dict[str, Any]:
    monkeypatch.setattr(worker_module, "AsyncSessionLocal", test_session_local)
    return await generate_plan(athlete_id=str(athlete_id))


# ---------------------------------------------------------------------------
# generate_plan task body.
# ---------------------------------------------------------------------------


class TestGeneratePlanTaskCreatesTrainingPlan:
    """The task creates a TrainingPlan with status=active and
    writes a training_plan_generated outbox row."""

    async def test_creates_active_training_plan(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await _seed_onboarded_athlete_without_plan(db_session)
        await db_session.commit()

        result = await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )

        assert result["athlete_id"] == str(athlete.id)
        assert result["training_plan_id"] is not None

        plans = (
            await db_session.execute(
                select(TrainingPlan)
                .join(TrainingGoal, TrainingPlan.training_goal_id == TrainingGoal.id)
                .where(TrainingGoal.athlete_id == athlete.id)
            )
        ).scalars().all()
        assert len(plans) == 1
        assert plans[0].status is TrainingPlanStatus.ACTIVE

    async def test_writes_training_plan_generated_outbox_row(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await _seed_onboarded_athlete_without_plan(db_session)
        await db_session.commit()

        await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )

        events = (
            await db_session.execute(
                select(SystemEvent)
                .where(SystemEvent.athlete_id == athlete.id)
                .where(SystemEvent.event_type == "training_plan_generated")
            )
        ).scalars().all()
        assert len(events) == 1


class TestGeneratePlanTaskCreatesWeeklyPlansAndPlannedSessions:
    """The task creates WeeklyPlans and PlannedSessions covering
    the full duration from plan start to the goal event date."""

    async def test_creates_weekly_plans_for_plan(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await _seed_onboarded_athlete_without_plan(db_session)
        await db_session.commit()

        await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )

        weeks = (
            await db_session.execute(
                select(WeeklyPlan)
                .join(TrainingPlan, WeeklyPlan.training_plan_id == TrainingPlan.id)
                .join(TrainingGoal, TrainingPlan.training_goal_id == TrainingGoal.id)
                .where(TrainingGoal.athlete_id == athlete.id)
            )
        ).scalars().all()
        assert len(weeks) >= 1

    async def test_creates_planned_sessions_for_plan(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await _seed_onboarded_athlete_without_plan(db_session)
        await db_session.commit()

        await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )

        sessions = (
            await db_session.execute(
                select(PlannedSession)
                .join(WeeklyPlan, PlannedSession.weekly_plan_id == WeeklyPlan.id)
                .join(TrainingPlan, WeeklyPlan.training_plan_id == TrainingPlan.id)
                .join(TrainingGoal, TrainingPlan.training_goal_id == TrainingGoal.id)
                .where(TrainingGoal.athlete_id == athlete.id)
            )
        ).scalars().all()
        assert len(sessions) >= 1
        for s in sessions:
            assert s.status is PlannedSessionStatus.SCHEDULED


class TestGeneratePlanTaskDefersFirstMessage:
    """After the plan is generated and committed, the task defers a
    ``generate_first_message`` procrastinate task with the athlete_id."""

    async def test_defers_generate_first_message_with_athlete_id(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await _seed_onboarded_athlete_without_plan(db_session)
        await db_session.commit()

        dispatcher = _RecordingDispatcher()
        monkeypatch.setattr(worker_module, "generate_first_message", dispatcher)

        await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )

        assert len(dispatcher.call_log) == 1
        assert dispatcher.call_log[0] == {"athlete_id": str(athlete.id)}


class TestGeneratePlanTaskIsIdempotentViaSupersession:
    """Running the task twice for the same athlete supersedes the
    first plan and creates a new active plan."""

    async def test_second_run_supersedes_first_plan(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await _seed_onboarded_athlete_without_plan(db_session)
        await db_session.commit()

        first = await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )
        first_plan_id = uuid.UUID(first["training_plan_id"])

        second = await _run_generate_plan_task(
            test_session_local, monkeypatch, athlete_id=athlete.id
        )
        second_plan_id = uuid.UUID(second["training_plan_id"])

        assert first_plan_id != second_plan_id

        first_plan = await db_session.get(TrainingPlan, first_plan_id)
        assert first_plan is not None
        assert first_plan.status is TrainingPlanStatus.SUPERSEDED
        assert first_plan.superseded_at is not None

        second_plan = await db_session.get(TrainingPlan, second_plan_id)
        assert second_plan is not None
        assert second_plan.status is TrainingPlanStatus.ACTIVE
