import uuid
from typing import Any
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    DataTier,
    GoalType,
    HrSource,
    PowerSource,
    RecoveryModifierLevel,
    SportBackground,
    TrainingGoalStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.system_event import EventPublicationStatus
from app.models.system_event import SystemEvent, SystemEventOutbox
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.services.onboarding_errors import (
    AthleteNotFoundError,
    OnboardingAlreadyCompleteError,
    TrainingGoalConflictError,
)
from app.services.onboarding_service import OnboardingService
from tests.utils.factories import make_athlete_with_profile
from tests.utils.onboarding_builders import (
    make_goal_input,
    make_preferences_input,
    make_profile_input,
)


async def _run_full_onboarding(
    db_session: AsyncSession,
    *,
    profile_kwargs: dict[str, Any] | None = None,
    prefs_kwargs: dict[str, Any] | None = None,
    goal_kwargs: dict[str, Any] | None = None,
):
    athlete, _ = await make_athlete_with_profile(db_session)
    service = OnboardingService(db_session)
    result = await service.complete_onboarding(
        athlete_id=athlete.id,
        profile_input=make_profile_input(**(profile_kwargs or {})),
        prefs_input=make_preferences_input(**(prefs_kwargs or {})),
        goal_input=make_goal_input(**(goal_kwargs or {})),
    )
    return athlete, result


class TestOnboardingAtomicCreate:
    async def test_complete_onboarding_creates_all_entities(self, db_session: AsyncSession):
        athlete, result = await _run_full_onboarding(
            db_session,
            prefs_kwargs={
                "hr_source": HrSource.CHEST_STRAP_RR,
                "power_source": PowerSource.RUNNING_POWER_METER,
            },
        )

        profile = await db_session.get(AthleteProfile, result.profile.id)
        prefs = await db_session.get(AthletePreferences, result.preferences.id)
        goal = await db_session.get(TrainingGoal, result.training_goal.id)
        twin = await db_session.get(TwinState, result.twin_state.id)
        physiology = await db_session.execute(
            select(AthletePhysiology).where(AthletePhysiology.athlete_id == athlete.id)
        )
        fitness = await db_session.execute(
            select(AthleteFitness).where(AthleteFitness.athlete_id == athlete.id)
        )

        assert profile is not None
        assert prefs is not None
        assert goal is not None
        assert twin is not None
        physiology_row = physiology.scalar_one()
        fitness_row = fitness.scalar_one()
        assert physiology_row.athlete_id == athlete.id
        assert fitness_row.athlete_id == athlete.id

    async def test_onboarding_complete_flag_flipped(self, db_session: AsyncSession):
        athlete, _ = await _run_full_onboarding(db_session)
        refreshed = await db_session.get(Athlete, athlete.id)
        assert refreshed is not None
        assert refreshed.onboarding_complete is True

    async def test_data_tier_persisted_on_twin_state(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(
            db_session,
            prefs_kwargs={
                "hr_source": HrSource.CHEST_STRAP_RR,
                "power_source": PowerSource.RUNNING_POWER_METER,
            },
        )
        assert result.data_tier == DataTier.TIER_1.value

    async def test_profile_enriched_with_timezone_and_height(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(
            db_session,
            profile_kwargs={"timezone": "America/New_York", "height_cm": 180.0},
            prefs_kwargs={
                "hr_source": HrSource.CHEST_STRAP_RR,
                "power_source": PowerSource.NONE,
            },
        )
        profile = await db_session.get(AthleteProfile, result.profile.id)
        assert profile is not None
        assert profile.height_cm is not None
        assert profile.timezone == "America/New_York"
        assert float(profile.height_cm) == 180.0

    async def test_structural_risk_flag_set_from_sport_background_running(
        self, db_session: AsyncSession
    ):
        _, result = await _run_full_onboarding(
            db_session,
            prefs_kwargs={"sport_background": SportBackground.RUNNING_PRIMARY},
        )
        profile = await db_session.get(AthleteProfile, result.profile.id)
        assert profile is not None
        assert profile.structural_risk_flag is False

    async def test_structural_risk_flag_set_from_sport_background_triathlon(
        self, db_session: AsyncSession
    ):
        _, result = await _run_full_onboarding(
            db_session,
            prefs_kwargs={"sport_background": SportBackground.TRIATHLON},
        )
        profile = await db_session.get(AthleteProfile, result.profile.id)
        assert profile is not None
        assert profile.structural_risk_flag is True

    async def test_training_goal_persisted_active(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        goal = await db_session.get(TrainingGoal, result.training_goal.id)
        assert goal is not None
        assert goal.status == TrainingGoalStatus.ACTIVE


class TestOnboardingTwinBootstrapValues:
    async def test_twin_state_bootstrap_trigger_and_confidence(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        twin = await db_session.get(TwinState, result.twin_state.id)
        assert twin is not None
        assert twin.trigger == TwinTrigger.QUESTIONNAIRE
        assert twin.confidence_level == TwinConfidenceLevel.LOW
        assert twin.model_version == "v1-questionnaire-bootstrap"
        assert twin.fitness == 0.0
        assert twin.fatigue == 0.0
        assert twin.form == 0.0
        assert twin.activity_id is None
        assert twin.readiness_level == RecoveryModifierLevel.GREEN

    async def test_twin_state_lt1_lt2_positive_and_lt1_lt_lt2_lt_max_hr(
        self, db_session: AsyncSession
    ):
        _, result = await _run_full_onboarding(db_session)
        twin = await db_session.get(TwinState, result.twin_state.id)
        assert twin is not None
        assert twin.lt1_hr_bpm is not None
        assert twin.lt2_hr_bpm is not None
        assert twin.lt1_hr_bpm > 0
        assert twin.lt2_hr_bpm > 0
        assert twin.lt1_hr_bpm < twin.lt2_hr_bpm
        max_hr = 220 - 36
        assert twin.lt2_hr_bpm < max_hr

    async def test_twin_metric_confidence_only_lt1_lt2_hr_low(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        twin = await db_session.get(TwinState, result.twin_state.id)
        assert twin is not None
        mc = twin.metric_confidence
        assert mc["lt1_hr"] == TwinConfidenceLevel.LOW.value
        assert mc["lt2_hr"] == TwinConfidenceLevel.LOW.value
        assert mc["lt1_power"] is None
        assert mc["lt1_pace"] is None
        assert mc["lt2_power"] is None
        assert mc["lt2_pace"] is None
        assert mc["cp"] is None

    async def test_physiology_max_hr_bootstrapped_from_age(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        physiology = await db_session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.athlete_id == result.twin_state.athlete_id
            )
        )
        row = physiology.scalar_one()
        assert row.max_hr is not None
        max_hr_value = row.max_hr["value"]
        assert max_hr_value == pytest.approx(184.0, abs=0.1)

    async def test_physiology_lt1_lt2_questionnaire_source(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        physiology = await db_session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.athlete_id == result.twin_state.athlete_id
            )
        )
        row = physiology.scalar_one()
        assert row.lt1["hr"]["dominant_source"] == "questionnaire_estimate"
        assert row.lt2["hr"]["dominant_source"] == "questionnaire_estimate"
        assert row.lt1["hr"]["prior_weight"] == pytest.approx(0.5, abs=1e-9)
        assert row.lt2["hr"]["prior_weight"] == pytest.approx(0.5, abs=1e-9)

    async def test_physiology_cp_and_vo2max_null(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        physiology = await db_session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.athlete_id == result.twin_state.athlete_id
            )
        )
        row = physiology.scalar_one()
        assert row.cp is None
        assert row.vo2max is None

    async def test_fitness_bootstrap_zeroed(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        fitness = await db_session.execute(
            select(AthleteFitness).where(
                AthleteFitness.athlete_id == result.twin_state.athlete_id
            )
        )
        row = fitness.scalar_one()
        assert row.aggregate == {"fitness": 0.0, "fatigue": 0.0, "form": 0.0}
        assert row.aerobic is None
        assert row.neuromuscular is None
        assert row.structural is None

    async def test_fitness_time_constants_population_default(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        fitness = await db_session.execute(
            select(AthleteFitness).where(
                AthleteFitness.athlete_id == result.twin_state.athlete_id
            )
        )
        row = fitness.scalar_one()
        tc = row.time_constants
        assert tc["source"] == "population_default"
        assert tc["aerobic"]["fitness_tau_days"] == 42
        assert tc["aerobic"]["fatigue_tau_days"] == 7
        assert tc["neuromuscular"]["fitness_tau_days"] == 21
        assert tc["neuromuscular"]["fatigue_tau_days"] == 3
        assert tc["structural"]["fitness_tau_days"] == 56
        assert tc["structural"]["fatigue_tau_days"] == 14


class TestOnboardingFailurePaths:
    async def test_re_onboarding_raises_409(self, db_session: AsyncSession):
        athlete, _ = await _run_full_onboarding(db_session)
        service = OnboardingService(db_session)
        with pytest.raises(OnboardingAlreadyCompleteError) as exc_info:
            await service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=make_profile_input(),
                prefs_input=make_preferences_input(),
                goal_input=make_goal_input(),
            )
        assert "onboarding has already been completed" in str(exc_info.value)

    async def test_athlete_not_found_raises_404(self, db_session: AsyncSession):
        service = OnboardingService(db_session)
        with pytest.raises(AthleteNotFoundError):
            await service.complete_onboarding(
                athlete_id=uuid.uuid4(),
                profile_input=make_profile_input(),
                prefs_input=make_preferences_input(),
                goal_input=make_goal_input(),
            )

    async def test_second_active_goal_raises_conflict(self, db_session: AsyncSession):
        athlete, _ = await make_athlete_with_profile(db_session)
        existing_goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            weekly_volume_hours=8.0,
            weekly_volume_km=60.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(existing_goal)
        await db_session.commit()

        service = OnboardingService(db_session)
        with pytest.raises(TrainingGoalConflictError) as exc_info:
            await service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=make_profile_input(),
                prefs_input=make_preferences_input(),
                goal_input=make_goal_input(),
            )
        assert "athlete already has an active training goal" in str(exc_info.value)


class TestOnboardingEventsPublished:
    async def test_onboarding_completed_event_published(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        events = (
            (
                await db_session.execute(
                    select(SystemEvent).where(
                        SystemEvent.event_type == "onboarding_completed"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        payload = events[0].payload
        assert payload["training_goal_id"] == str(result.training_goal.id)
        assert payload["twin_state_id"] == str(result.twin_state.id)
        assert payload["data_tier"] == result.data_tier
        assert payload["confidence_level"] == TwinConfidenceLevel.LOW.value

    async def test_onboarding_completed_outbox_row_pending(self, db_session: AsyncSession):
        await _run_full_onboarding(db_session)
        outbox = (
            (
                await db_session.execute(
                    select(SystemEventOutbox)
                    .join(
                        SystemEvent, SystemEventOutbox.event_id == SystemEvent.event_id
                    )
                    .where(SystemEvent.event_type == "onboarding_completed")
                )
            )
            .scalars()
            .all()
        )
        assert len(outbox) == 1
        assert outbox[0].status == EventPublicationStatus.PENDING

    async def test_twin_model_ready_event_published(self, db_session: AsyncSession):
        _, result = await _run_full_onboarding(db_session)
        events = (
            (
                await db_session.execute(
                    select(SystemEvent).where(
                        SystemEvent.event_type == "twin_model_ready"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(events) == 1
        payload = events[0].payload
        assert payload["twin_state_id"] == str(result.twin_state.id)
        assert payload["data_tier"] == result.data_tier
        assert payload["confidence_level"] == TwinConfidenceLevel.LOW.value

    async def test_both_events_persisted_in_same_transaction(self, db_session: AsyncSession):
        await _run_full_onboarding(db_session)
        outbox_count = (
            (await db_session.execute(select(SystemEventOutbox))).scalars().all()
        )
        assert len(outbox_count) == 2

    async def test_generate_plan_defer_failure_does_not_break_onboarding(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        from app.services import onboarding_service as onboarding_module

        async def failing_defer(self: OnboardingService, athlete_id: uuid.UUID) -> None:
            raise RuntimeError("procrastinate defer failed")

        monkeypatch.setattr(
            onboarding_module.OnboardingService,
            "_defer_generate_plan",
            failing_defer,
        )

        athlete, _ = await _run_full_onboarding(db_session)
        refreshed = await db_session.get(Athlete, athlete.id)
        assert refreshed is not None
        assert refreshed.onboarding_complete is True


class TestDeferGeneratePlan:
    async def test_defer_generate_plan_uses_async_defer_async(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ):
        from app.worker import app as worker_app
        from app.services.onboarding_service import OnboardingService

        defer_mock = AsyncMock(return_value=42)
        monkeypatch.setattr(worker_app.generate_plan, "defer_async", defer_mock)

        athlete, _ = await make_athlete_with_profile(db_session)
        service = OnboardingService(db_session)

        await service._defer_generate_plan(athlete.id)

        defer_mock.assert_awaited_once_with(athlete_id=str(athlete.id))

    async def test_defer_generate_plan_swallows_defer_failure_with_log_event(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ):
        from app.services import onboarding_service as onboarding_module

        log_event_calls: list[dict[str, Any]] = []

        def _mock_log_event(**kwargs: Any) -> None:
            log_event_calls.append(kwargs)

        monkeypatch.setattr(onboarding_module, "log_event", _mock_log_event)

        async def failing_defer(
            self: OnboardingService, athlete_id: uuid.UUID
        ) -> None:
            raise RuntimeError("procrastinate defer failed")

        monkeypatch.setattr(
            onboarding_module.OnboardingService,
            "_defer_generate_plan",
            failing_defer,
        )

        athlete, _ = await _run_full_onboarding(db_session)

        refreshed = await db_session.get(Athlete, athlete.id)
        assert refreshed is not None
        assert refreshed.onboarding_complete is True

        failure_logs = [
            call
            for call in log_event_calls
            if call.get("event") == "generate_plan.defer.failure"
        ]
        assert len(failure_logs) == 1
        assert failure_logs[0].get("outcome") == "failed"
        assert "procrastinate defer failed" in str(failure_logs[0].get("error"))

        outbox_rows = (
            (
                await db_session.execute(
                    select(SystemEventOutbox)
                    .join(
                        SystemEvent, SystemEventOutbox.event_id == SystemEvent.event_id
                    )
                    .where(SystemEvent.event_type == "twin_model_ready")
                )
            )
            .scalars()
            .all()
        )
        assert len(outbox_rows) == 1
        assert outbox_rows[0].status == EventPublicationStatus.PENDING
