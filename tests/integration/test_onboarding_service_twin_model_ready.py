"""Integration tests for ``OnboardingService`` event-flow changes (Phase 2.7 Batch 3).

The Phase-2.7 Batch 3 plan (closing G-03) changes ``complete_onboarding``:

* The method no longer calls ``PlanGenerationService.generate_plan()``
  directly — plan generation is now triggered by a deferred
  ``generate_plan`` procrastinate task, fired after the onboarding
  transaction commits.
* The method fires the ``twin_model_ready`` event via the transactional
  outbox, in addition to the existing ``onboarding_completed`` event.
  The payload is ``{twin_state_id, data_tier, confidence_level}``.
* The method no longer accepts ``PlanGenerationService`` as a
  constructor dependency — the dependency is removed.

These tests assert all three changes end-to-end against the real
test database, plus the negative path (duplicate active goal
surfaces as ``TrainingGoalConflictError`` rather than a raw
``IntegrityError``).

Reference plan: ``docs/implementation/phase-2/phase-2-7/batch-3-event-flow-plan-router-fix.md``
Steps 1–2, 8.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.checkpoint import Checkpoint
from app.models.enums import (
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    Sex,
    SportBackground,
    TrainingGoalStatus,
    TwinConfidenceLevel,
)
from app.models.planned_session import PlannedSession
from app.models.system_event import EventPublicationStatus, SystemEvent
from app.models.system_event import SystemEventOutbox
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan
from app.services.auth_service import AuthService
from app.services.onboarding_errors import TrainingGoalConflictError
from app.services.onboarding_service import OnboardingService
from app.services.onboarding_service import (
    GoalInput,
    PreferencesInput,
    ProfileInput,
)
from tests.payloads import weekly_schedule_payload


# ---------------------------------------------------------------------------
# Fixtures and helpers.
# ---------------------------------------------------------------------------


@pytest.fixture
def onboarding_service(db_session: AsyncSession) -> OnboardingService:
    return OnboardingService(session=db_session)


def _profile_input(**overrides: Any) -> ProfileInput:
    defaults: dict[str, Any] = {
        "timezone": "Europe/Lisbon",
        "training_window": None,
        "height_cm": 180.0,
    }
    defaults.update(overrides)
    return ProfileInput(**defaults)


def _preferences_input(**overrides: Any) -> PreferencesInput:
    defaults: dict[str, Any] = {
        "sport_background": SportBackground.RUNNING_PRIMARY,
        "years_structured_training": 3,
        "training_time_of_day": "morning",
        "weekly_schedule": weekly_schedule_payload(),
        "gps_source": GpsSource.GARMIN_WATCH,
        "hr_source": HrSource.CHEST_STRAP_RR,
        "power_source": PowerSource.NONE,
        "primary_training_platform": PrimaryTrainingPlatform.MANUAL,
    }
    defaults.update(overrides)
    return PreferencesInput(**defaults)


def _goal_input_race_event(**overrides: Any) -> GoalInput:
    defaults: dict[str, Any] = {
        "goal_type": GoalType.RACE_EVENT,
        "goal_event_type": GoalEventType.HALF_MARATHON,
        "goal_event_name": "Lisbon Half Marathon",
        "goal_event_date": date.today() + timedelta(days=120),
        "custom_distance_km": None,
        "goal_description": None,
        "weekly_volume_hours": 6.0,
        "weekly_volume_km": 40.0,
        "fitness_level": 3,
        "recent_injury": None,
        "injury_severity": None,
        "target_distance_km": None,
        "target_time_minutes": None,
    }
    defaults.update(overrides)
    return GoalInput(**defaults)


async def _register_athlete(db_session: AsyncSession, email: str) -> Athlete:
    auth_service = AuthService(session=db_session)
    await auth_service.register(
        email=email,
        password="ValidPass123!",
        date_of_birth=datetime(1990, 1, 1, tzinfo=timezone.utc).date(),
        sex=Sex.NOT_SPECIFIED,
        height_cm=180.0,
        ip_address="203.0.113.10",
        user_agent="OnboardingTwinModelReadyTest/1.0",
    )
    row = (
        await db_session.execute(
            select(Athlete).where(Athlete.email == email)
        )
    ).scalar_one()
    return row


# ---------------------------------------------------------------------------
# twin_model_ready event production.
# ---------------------------------------------------------------------------


class TestTwinModelReadyEventProduction:
    """``complete_onboarding`` fires ``twin_model_ready`` via the
    transactional outbox with payload ``{twin_state_id, data_tier,
    confidence_level}``."""

    async def test_twin_model_ready_outbox_row_exists(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(db_session, "twin-ready@example.com")

        await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        rows = (
            await db_session.execute(
                select(SystemEvent)
                .where(SystemEvent.athlete_id == athlete.id)
                .where(SystemEvent.event_type == "twin_model_ready")
            )
        ).scalars().all()
        assert len(rows) == 1
        event = rows[0]
        assert event.payload["twin_state_id"] is not None
        assert event.payload["data_tier"] is not None
        assert event.payload["confidence_level"] == TwinConfidenceLevel.LOW.value

    async def test_twin_model_ready_paired_with_outbox_row_in_pending(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(db_session, "twin-ready-pending@example.com")

        await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        result = await db_session.execute(
            select(SystemEvent, SystemEventOutbox)
            .join(SystemEventOutbox, SystemEventOutbox.event_id == SystemEvent.event_id)
            .where(SystemEvent.event_type == "twin_model_ready")
            .where(SystemEvent.athlete_id == athlete.id)
        )
        row = result.one()
        event, outbox = row
        assert outbox.status is EventPublicationStatus.PENDING
        assert event.payload["twin_state_id"] is not None


# ---------------------------------------------------------------------------
# twin_model_ready fires in the onboarding transaction.
# ---------------------------------------------------------------------------


class TestTwinModelReadyTransactionalAtomicity:
    """A failure after the ``twin_model_ready`` outbox write but
    before the commit must roll the event back with the rest of the
    transaction — the event is part of the onboarding transaction."""

    async def test_twin_model_ready_rolled_back_on_mid_transaction_failure(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(db_session, "twin-rollback@example.com")
        athlete_id = athlete.id

        original_publish = onboarding_service.events.publish

        async def failing_publish(*args: Any, **kwargs: Any) -> Any:
            result = await original_publish(*args, **kwargs)
            if kwargs.get("event_type") == "twin_model_ready":
                raise RuntimeError("simulated failure after twin_model_ready publish")
            return result

        with patch.object(
            onboarding_service.events, "publish", side_effect=failing_publish
        ):
            with pytest.raises(RuntimeError, match="simulated failure"):
                await onboarding_service.complete_onboarding(
                    athlete_id=athlete_id,
                    profile_input=_profile_input(),
                    prefs_input=_preferences_input(),
                    goal_input=_goal_input_race_event(),
                )

        await db_session.rollback()

        rows = (
            await db_session.execute(
                select(SystemEvent)
                .where(SystemEvent.athlete_id == athlete_id)
                .where(SystemEvent.event_type == "twin_model_ready")
            )
        ).scalars().all()
        assert rows == []

        refreshed = await db_session.get(Athlete, athlete_id)
        assert refreshed is not None
        assert refreshed.onboarding_complete is False


# ---------------------------------------------------------------------------
# Onboarding no longer calls PlanGenerationService directly.
# ---------------------------------------------------------------------------


class TestOnboardingNoLongerCallsPlanGenerationService:
    """The onboarding transaction no longer creates TrainingPlan /
    WeeklyPlan / PlannedSession / Checkpoint rows. Plan generation
    is dispatched via the deferred ``generate_plan`` worker task
    after the onboarding commit."""

    async def test_onboarding_creates_no_plan_rows(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(db_session, "no-plan@example.com")

        await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        for model, label in [
            (TrainingPlan, "training_plans"),
            (WeeklyPlan, "weekly_plans"),
            (PlannedSession, "planned_sessions"),
            (Checkpoint, "checkpoints"),
        ]:
            count = (
                await db_session.execute(
                    select(func.count()).select_from(model)
                )
            ).scalar_one()
            assert count == 0, (
                f"onboarding should not have created {label} rows, "
                f"found {count}"
            )

    async def test_onboarding_service_constructor_does_not_accept_plan_service(
        self,
    ) -> None:
        """The constructor signature must not include a plan_service
        parameter — plan generation is now event-driven via the
        deferred task, not a direct service injection."""
        import inspect

        sig = inspect.signature(OnboardingService.__init__)
        assert "plan_service" not in sig.parameters
        assert "plan_generation_service" not in sig.parameters

    async def test_generate_plan_task_is_deferred_after_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """After the onboarding commit, a ``generate_plan`` task is
        deferred. The defer is post-commit — failures are swallowed
        and the onboarding is still complete."""
        from app.worker import app as worker_module

        athlete = await _register_athlete(db_session, "defer-gen-plan@example.com")

        with patch.object(worker_module, "generate_plan") as mock_task:
            mock_task.defer = MagicMock()

            await onboarding_service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=_goal_input_race_event(),
            )

            mock_task.defer.assert_called_once_with(athlete_id=str(athlete.id))


# ---------------------------------------------------------------------------
# Onboarding duplicate goal.
# ---------------------------------------------------------------------------


class TestOnboardingDuplicateGoalConflict:
    """``complete_onboarding`` raises ``TrainingGoalConflictError``
    when the athlete already has an active TrainingGoal — the
    unique violation is caught and translated correctly."""

    async def test_complete_onboarding_raises_conflict_on_duplicate_active_goal(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(db_session, "goal-conflict@example.com")

        existing_id = uuid.uuid4()
        existing = TrainingGoal(
            id=existing_id,
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            target_distance_km=5.0,
            target_time_minutes=22,
            weekly_volume_hours=5.0,
            weekly_volume_km=30.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(existing)
        await db_session.commit()

        with pytest.raises(TrainingGoalConflictError):
            await onboarding_service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=_goal_input_race_event(),
            )

        await db_session.rollback()

        remaining = (
            await db_session.execute(
                select(TrainingGoal).where(TrainingGoal.id == existing_id)
            )
        ).scalar_one()
        assert remaining.status is TrainingGoalStatus.ACTIVE
        assert remaining.goal_type is GoalType.TARGET_PERFORMANCE
