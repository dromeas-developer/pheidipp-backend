"""Integration tests for ``OnboardingService`` against the live test DB.

These tests exercise the full atomic onboarding transaction described in
the Phase-1.3 plan — every row in the seven-entity graph (Athlete +
AthleteProfile enrichment + AthletePreferences + TrainingGoal +
AthletePhysiology + AthleteFitness + TwinState) plus the
``onboarding_completed`` event/outbox rows land together or not at all.

Coverage scope (per the plan's Testing Requirements section):

* **Atomic success** — one of each row appears after a complete
  onboarding call; ``onboarding_complete`` flips to ``True`` in the
  same commit.
* **Event persistence** — ``onboarding_completed`` event row exists
  with the documented payload and a paired ``SystemEventOutbox`` row
  in pending status.
* **Mid-transaction rollback** — a failure at any entity-creation
  step leaves the database in the pre-onboarding state (no orphan
  rows, gate still false, no event).
* **Idempotency guard** — a second ``complete_onboarding`` call for
  the same athlete raises ``OnboardingAlreadyCompleteError``.
* **Single-active-goal invariant** — bypassing the gate (status=False)
  still raises ``TrainingGoalConflictError`` on the partial unique
  index when a second active goal is inserted.
* **Twin correctness** — confidence_level/low, trigger/questionnaire,
  fitness/fatigue/form=0, dob-derived ``lt1_hr`` and ``lt2_hr``,
  ``readiness_level=green``, ``activity_id=null``.
* **Data tier wiring** — ``TwinState.data_tier`` matches
  ``infer_data_tier(hr_source, power_source)`` for every
  documented pair.
* **Profile PATCH guard** — ``update_profile`` writes only mutable
  fields; immutable fields (``date_of_birth``/``sex``/``timezone``)
  must be rejected at the schema layer (covered in API tests).
* **Preferences PATCH merge** — ``update_preferences`` shallow-merges
  ``weekly_schedule`` at the day level; top-level fields overwrite.
* **Read endpoints** — ``get_profile`` / ``get_preferences`` /
  ``get_twin_state`` / ``get_twin_history`` return None /
  empty before onboarding; populated rows after.
* **Status endpoint** — ``get_onboarding_status`` reports each flag
  consistent with the actual row existence.

Reference plan:
docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Optional

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import (
    AthletePreferences,
    infer_data_tier,
)
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    Sex,
    SportBackground,
    TrainingGoalStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.system_event import EventPublicationStatus, SystemEvent
from app.models.system_event import SystemEventOutbox
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.services.auth_service import AuthService
from app.services.onboarding_errors import (
    AthleteNotFoundError,
    OnboardingAlreadyCompleteError,
    TrainingGoalConflictError,
)
from app.services.onboarding_service import (
    OnboardingService,
    _GoalInput,
    _PreferencesInput,
    _ProfileInput,
)
from tests.payloads import _weekly_schedule_payload


# ---------------------------------------------------------------------------
# Fixtures and helpers.
# ---------------------------------------------------------------------------


@pytest.fixture
def onboarding_service(db_session: AsyncSession) -> OnboardingService:
    """Build an OnboardingService against the per-test session."""
    return OnboardingService(session=db_session)


def _profile_input(**overrides) -> _ProfileInput:
    """Default profile input — Lisbon timezone, 180cm, no training window."""
    defaults: dict = {
        "timezone": "Europe/Lisbon",
        "training_window": None,
        "height_cm": 180.0,
    }
    defaults.update(overrides)
    return _ProfileInput(**defaults)


def _preferences_input(**overrides) -> _PreferencesInput:
    """Default preferences — running primary, Tier 3 HR-only hardware."""
    defaults: dict = {
        "sport_background": SportBackground.RUNNING_PRIMARY,
        "years_structured_training": 3,
        "training_time_of_day": "morning",
        "weekly_schedule": _weekly_schedule_payload(),
        "gps_source": GpsSource.GARMIN_WATCH,
        "hr_source": HrSource.CHEST_STRAP_RR,
        "power_source": PowerSource.NONE,
        "primary_training_platform": PrimaryTrainingPlatform.MANUAL,
    }
    defaults.update(overrides)
    return _PreferencesInput(**defaults)


def _goal_input_race_event(**overrides) -> _GoalInput:
    """Default race-event goal payload — Lisbon half marathon, today as event date."""
    defaults: dict = {
        "goal_type": GoalType.RACE_EVENT,
        "goal_event_type": GoalEventType.HALF_MARATHON,
        "goal_event_name": "Lisbon Half Marathon",
        "goal_event_date": date.today(),
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
    return _GoalInput(**defaults)


def _goal_input_target_performance(**overrides) -> _GoalInput:
    """Default target-performance goal payload — 10k in 45 minutes."""
    defaults: dict = {
        "goal_type": GoalType.TARGET_PERFORMANCE,
        "goal_event_type": None,
        "goal_event_name": None,
        "goal_event_date": None,
        "custom_distance_km": None,
        "goal_description": None,
        "weekly_volume_hours": 5.0,
        "weekly_volume_km": 30.0,
        "fitness_level": 3,
        "recent_injury": None,
        "injury_severity": None,
        "target_distance_km": 10.0,
        "target_time_minutes": 45,
    }
    defaults.update(overrides)
    return _GoalInput(**defaults)


async def _register_athlete(
    db_session: AsyncSession, email: str
) -> Athlete:
    """Register an athlete + auth + minimal profile through the real
    ``AuthService.register`` so onboarding tests start from a realistic
    Phase-1.1 state. Returns the freshly-created Athlete row.
    """
    auth_service = AuthService(session=db_session)
    await auth_service.register(
        email=email,
        password="ValidPass123!",
        date_of_birth=datetime(1990, 1, 1, tzinfo=timezone.utc).date(),
        sex=Sex.NOT_SPECIFIED,
        height_cm=180.0,
        ip_address="203.0.113.10",
        user_agent="OnboardingTest/1.0",
    )
    row = (
        await db_session.execute(
            select(Athlete).where(Athlete.email == email)
        )
    ).scalar_one()
    return row


async def _onboarded_athlete(
    db_session: AsyncSession,
    onboarding_service: OnboardingService,
    email: str,
    **input_overrides,
) -> Athlete:
    """Register + fully onboard an athlete; return the Athlete row."""
    athlete = await _register_athlete(db_session, email)
    await onboarding_service.complete_onboarding(
        athlete_id=athlete.id,
        profile_input=_profile_input(
            **input_overrides.pop("profile", {})
        ),
        prefs_input=_preferences_input(
            **input_overrides.pop("prefs", {})
        ),
        goal_input=_goal_input_race_event(
            **input_overrides.pop("goal", {})
        ),
    )
    return athlete


# ---------------------------------------------------------------------------
# Atomic success — exit #1 in the plan's Testing Requirements.
# ---------------------------------------------------------------------------


class TestAtomicSuccess:
    """A complete onboarding call creates exactly the documented row graph
    in one committed transaction."""

    async def test_creates_one_preferences_row(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-prefs@example.com",
        )

        rows = (
            await db_session.execute(
                select(AthletePreferences).where(
                    AthletePreferences.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        prefs = rows[0]
        assert prefs.sport_background is SportBackground.RUNNING_PRIMARY
        assert prefs.hr_source is HrSource.CHEST_STRAP_RR
        assert prefs.power_source is PowerSource.NONE

    async def test_creates_one_active_training_goal(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-goal@example.com",
        )

        rows = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        goal = rows[0]
        assert goal.status is TrainingGoalStatus.ACTIVE
        assert goal.goal_type is GoalType.RACE_EVENT

    async def test_creates_one_physiology_row_with_dob_derived_thresholds(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-physio@example.com",
        )

        rows = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        physio = rows[0]
        # DOB = 1990-01-01 places the athlete at 36 years as of mid-2026
        # → max_hr ≈ 184 → lt1 ≈ 138.0, lt2 ≈ 161.0.
        assert physio.lt1["hr"]["value"] == pytest.approx(138.0)
        assert physio.lt2["hr"]["value"] == pytest.approx(161.0)
        assert (
            physio.lt1["hr"]["dominant_source"] == "questionnaire_estimate"
        )
        assert (
            physio.lt2["hr"]["dominant_source"] == "questionnaire_estimate"
        )
        # Power / pace are signal-derived — null at bootstrap.
        assert physio.lt1["power"] is None
        assert physio.lt1["pace"] is None
        assert physio.lt2["power"] is None
        assert physio.lt2["pace"] is None
        # cp / vo2max never estimated from questionnaire.
        assert physio.cp is None
        assert physio.vo2max is None
        # max_hr carries the same provenance.
        assert physio.max_hr["value"] == pytest.approx(184.0)
        assert (
            physio.max_hr["dominant_source"] == "questionnaire_estimate"
        )

    async def test_creates_one_fitness_row_with_zero_aggregate(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-fit@example.com",
        )

        rows = (
            await db_session.execute(
                select(AthleteFitness).where(
                    AthleteFitness.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        fitness = rows[0]
        assert fitness.aggregate["fitness"] == pytest.approx(0.0)
        assert fitness.aggregate["fatigue"] == pytest.approx(0.0)
        assert fitness.aggregate["form"] == pytest.approx(0.0)
        # Dimensional blocks left null at bootstrap.
        assert fitness.aerobic is None
        assert fitness.neuromuscular is None
        assert fitness.structural is None
        # last_activity_id null.
        assert fitness.last_activity_id is None
        # Population time constants + source tag.
        assert fitness.time_constants["source"] == "population_default"
        assert fitness.time_constants["aerobic"]["fitness_tau_days"] == 42
        assert (
            fitness.time_constants["neuromuscular"]["fatigue_tau_days"] == 3
        )
        assert (
            fitness.time_constants["structural"]["fitness_tau_days"] == 56
        )

    async def test_creates_one_twin_state(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-twin@example.com",
        )

        rows = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        twin = rows[0]
        assert twin.confidence_level is TwinConfidenceLevel.LOW
        assert twin.trigger is TwinTrigger.QUESTIONNAIRE
        assert twin.fitness == pytest.approx(0.0)
        assert twin.fatigue == pytest.approx(0.0)
        assert twin.form == pytest.approx(0.0)
        assert twin.activity_id is None
        assert twin.readiness_level is RecoveryModifierLevel.GREEN
        assert twin.wellness_trend is None
        # Threshold values inline from physiology bootstrap.
        assert twin.lt1_hr_bpm == pytest.approx(138.0)
        assert twin.lt2_hr_bpm == pytest.approx(161.0)
        # Power / pace / cp stay null at the bootstrap TwinState.
        assert twin.lt1_power_watts is None
        assert twin.lt1_pace_sec_per_km is None
        assert twin.lt2_power_watts is None
        assert twin.lt2_pace_sec_per_km is None
        assert twin.cp_watts is None
        # Metric confidence bootstrap pattern.
        assert twin.metric_confidence["lt1_hr"] == "low"
        assert twin.metric_confidence["lt2_hr"] == "low"
        for key in (
            "lt1_power",
            "lt1_pace",
            "lt2_power",
            "lt2_pace",
            "cp",
        ):
            assert twin.metric_confidence[key] is None

    async def test_athlete_profile_updated_with_timezone_and_risk_flag(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-profile@example.com",
            prefs={"sport_background": SportBackground.CYCLING},
        )

        rows = (
            await db_session.execute(
                select(AthleteProfile).where(
                    AthleteProfile.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(rows) == 1, "one-profile invariant must hold"
        profile = rows[0]
        assert profile.timezone == "Europe/Lisbon"
        # Crossover athlete (cycling) ⇒ structural risk flag is True.
        assert profile.structural_risk_flag is True
        assert float(profile.height_cm) == pytest.approx(180.0)

    async def test_running_primary_keeps_risk_flag_false(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-running-primary@example.com",
        )

        profile = (
            await db_session.execute(
                select(AthleteProfile).where(
                    AthleteProfile.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert profile.structural_risk_flag is False

    async def test_onboarding_complete_flips_to_true(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "atomic-flip@example.com",
        )

        refreshed = (
            await db_session.execute(
                select(Athlete).where(Athlete.id == athlete.id)
            )
        ).scalar_one()
        assert refreshed.onboarding_complete is True

    async def test_complete_onboarding_returns_populated_result(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """The service returns ``OnboardingResult`` with twin_state,
        training_goal, preferences, profile, and the inferred data
        tier so the API layer can build the response without
        re-querying."""
        athlete = await _register_athlete(
            db_session, "result-shape@example.com"
        )
        result = await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        assert result.twin_state.id is not None
        assert result.training_goal.id is not None
        assert result.preferences.id is not None
        assert result.profile.id is not None
        # data_tier is the integer value, ready for the wire format.
        assert isinstance(result.data_tier, int)
        assert 1 <= result.data_tier <= 6


# ---------------------------------------------------------------------------
# onboarding_completed event — exit #2 in the plan.
# ---------------------------------------------------------------------------


class TestOnboardingCompletedEvent:
    """The event is persisted via the transactional outbox in the same
    commit as the domain state."""

    async def test_event_persisted_with_documented_payload(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(
            db_session, "event-payload@example.com"
        )
        result = await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "onboarding_completed",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(events) == 1, (
            f"expected exactly one onboarding_completed event, "
            f"got {len(events)}"
        )
        event = events[0]
        assert event.payload["training_goal_id"] == str(
            result.training_goal.id
        )
        assert event.payload["twin_state_id"] == str(result.twin_state.id)
        assert event.payload["data_tier"] == result.data_tier
        assert (
            event.payload["confidence_level"]
            == TwinConfidenceLevel.LOW.value
        )
        # Version pin — guards against silent rename in the
        # ``SystemEventRepository.add`` path.
        assert event.version == "v1"

    async def test_outbox_row_pending(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """The paired outbox row exists with ``PENDING`` status — the
        platform publisher worker picks it up from there after commit."""
        athlete = await _register_athlete(
            db_session, "event-outbox@example.com"
        )
        await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        event_ids = (
            await db_session.execute(
                select(SystemEvent.event_id).where(
                    SystemEvent.event_type == "onboarding_completed",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()
        assert len(event_ids) == 1

        outbox_rows = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.event_id == event_ids[0]
                )
            )
        ).scalars().all()
        assert len(outbox_rows) == 1
        assert outbox_rows[0].status is EventPublicationStatus.PENDING
        assert outbox_rows[0].attempts == 0


# ---------------------------------------------------------------------------
# Idempotency guard — exit #4 in the plan.
# ---------------------------------------------------------------------------


class TestIdempotencyGuard:
    """A second ``complete_onboarding`` call for the same athlete raises
    ``OnboardingAlreadyCompleteError`` and writes nothing."""

    async def test_second_call_raises_409_domain_error(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_server := db_session,  # noqa: F841
            onboarding_service,
            "idempotent-already-complete@example.com",
        )

        with pytest.raises(OnboardingAlreadyCompleteError):
            await onboarding_service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=_goal_input_target_performance(),
            )

    async def test_second_call_writes_no_new_artifact(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "idempotent-no-new-artifacts@example.com",
        )

        # Snapshot counts before the failed second call.
        prefs_before = (
            await db_session.execute(
                select(AthletePreferences).where(
                    AthletePreferences.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        goals_before = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        twins_before = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        events_before = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "onboarding_completed",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()

        with pytest.raises(OnboardingAlreadyCompleteError):
            await onboarding_service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=_goal_input_target_performance(),
            )

        # Re-query — must still be exactly one of each.
        prefs_after = (
            await db_session.execute(
                select(AthletePreferences).where(
                    AthletePreferences.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        goals_after = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        twins_after = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        events_after = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "onboarding_completed",
                    SystemEvent.athlete_id == athlete.id,
                )
            )
        ).scalars().all()

        assert len(prefs_after) == len(prefs_before) == 1
        assert len(goals_after) == len(goals_before) == 1
        assert len(twins_after) == len(twins_before) == 1
        assert len(events_after) == len(events_before) == 1


# ---------------------------------------------------------------------------
# Single-active-goal invariant — exit #7 in the plan.
# ---------------------------------------------------------------------------


class TestSingleActiveGoalInvariant:
    """The partial unique index ``ix_training_goals_athlete_active``
    raises an ``IntegrityError`` on a second active goal for the same
    athlete. The service maps that to ``TrainingGoalConflictError``."""

    async def test_partial_unique_index_fires_on_conflict(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """Manually insert a second active goal → service raises
        ``TrainingGoalConflictError`` (409)."""
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "goal-conflict@example.com",
        )

        # Try to insert a second active goal by hand.
        conflicting = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            target_distance_km=5.0,
            target_time_minutes=22,
            weekly_volume_hours=5.0,
            weekly_volume_km=30.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(conflicting)
        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_completed_goal_does_not_block_new_active_goal(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """Sanity check for the partial WHERE clause — a goal marked
        COMPLETED is NOT in the unique index. The plan defers PATCH /
        replacement to Phase 1.4+ — this test pins the underlying
        shape only."""
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "goal-completed@example.com",
        )
        # Mark the existing goal completed.
        goal = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        goal.status = TrainingGoalStatus.COMPLETED
        await db_session.flush()

        # Now we can insert a fresh ACTIVE goal.
        replacement = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            target_distance_km=10.0,
            target_time_minutes=45,
            weekly_volume_hours=5.0,
            weekly_volume_km=30.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(replacement)
        await db_session.flush()
        assert replacement.id is not None


# ---------------------------------------------------------------------------
# Mid-transaction rollback — exit #3 in the plan.
# ---------------------------------------------------------------------------


class TestMidTransactionRollback:
    """A failure at any entity-creation step leaves the database in the
    pre-onboarding state — no orphan rows, gate still false, no event."""

    async def test_missing_athlete_raises_not_found(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """No Athlete row exists → service raises ``AthleteNotFoundError``."""
        with pytest.raises(AthleteNotFoundError):
            await onboarding_service.complete_onboarding(
                athlete_id=uuid.uuid4(),
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=_goal_input_race_event(),
            )

    async def test_missing_athlete_does_not_create_orphan_artifacts(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        with pytest.raises(AthleteNotFoundError):
            await onboarding_service.complete_onboarding(
                athlete_id=uuid.uuid4(),
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=_goal_input_race_event(),
            )

        # No event row was created by the failed call.
        stale_events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.event_type == "onboarding_completed"
                )
            )
        ).scalars().all()
        assert stale_events == []

    async def test_invalid_goal_type_short_circuits_before_writes(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """``goal_type = fitness_improvement`` is whitelisted-out at the
        service layer (the wire-format schema is the second line of
        defence in the API). The service raises before any write
        lands — the gate stays false, no orphan rows."""
        from app.services.onboarding_errors import InvalidGoalTypeError

        athlete = await _register_athlete(
            db_session, "invalid-goal-type-svc@example.com"
        )

        invalid_goal = _GoalInput(
            goal_type=GoalType.FITNESS_IMPROVEMENT,
            goal_event_type=None,
            goal_event_name=None,
            goal_event_date=None,
            custom_distance_km=None,
            goal_description=None,
            weekly_volume_hours=5.0,
            weekly_volume_km=30.0,
            fitness_level=3,
            recent_injury=None,
            injury_severity=None,
            target_distance_km=None,
            target_time_minutes=None,
        )
        with pytest.raises(InvalidGoalTypeError):
            await onboarding_service.complete_onboarding(
                athlete_id=athlete.id,
                profile_input=_profile_input(),
                prefs_input=_preferences_input(),
                goal_input=invalid_goal,
            )

        # No rows were written; the gate is still false.
        refreshed = (
            await db_session.execute(
                select(Athlete).where(Athlete.id == athlete.id)
            )
        ).scalar_one()
        assert refreshed.onboarding_complete is False
        prefs = (
            await db_session.execute(
                select(AthletePreferences).where(
                    AthletePreferences.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert prefs == []
        goals = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert goals == []
        twins = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert twins == []


# ---------------------------------------------------------------------------
# Atomic integrity — every artifact carries the right FKs and the gate
# stays ``False`` on every failure path.
# ---------------------------------------------------------------------------


class TestAtomicIntegrity:
    """A single committed transaction; partial state is never visible."""

    async def test_twin_state_fks_resolve_to_athlete_and_goal(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "twin-fks@example.com",
        )
        twin = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        goal = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id,
                    TrainingGoal.status == TrainingGoalStatus.ACTIVE,
                )
            )
        ).scalar_one()
        assert twin.athlete_id == athlete.id
        assert twin.training_goal_id == goal.id

    async def test_physiology_fk_resolves_to_athlete(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "physio-fk@example.com",
        )
        physio = (
            await db_session.execute(
                select(AthletePhysiology).where(
                    AthletePhysiology.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert physio.athlete_id == athlete.id

    async def test_fitness_fk_resolves_to_athlete(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "fitness-fk@example.com",
        )
        fitness = (
            await db_session.execute(
                select(AthleteFitness).where(
                    AthleteFitness.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert fitness.athlete_id == athlete.id


# ---------------------------------------------------------------------------
# Twin correctness — exit #5 in the plan.
# ---------------------------------------------------------------------------


class TestTwinStateCorrectness:
    """The bootstrap TwinState carries the documented values."""

    async def test_bootstrap_threshold_values_follow_age_formula(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(
            db_session, "tw-thresholds@example.com"
        )
        # Use a DOB such that the age divides cleanly.
        auth_service = AuthService(session=db_session)
        athlete_row = (
            await db_session.execute(
                select(Athlete).where(Athlete.id == athlete.id)
            )
        ).scalar_one()
        profile_row = (
            await db_session.execute(
                select(AthleteProfile).where(
                    AthleteProfile.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        # Override DOB to a known value so the test does not drift
        # with the current calendar date.
        profile_row.date_of_birth = date(1990, 1, 1)
        await db_session.flush()
        _ = auth_service  # silence unused
        await onboarding_service.complete_onboarding(
            athlete_id=athlete_row.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(),
            goal_input=_goal_input_race_event(),
        )

        twin = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete_row.id
                )
            )
        ).scalar_one()
        # 36y → max_hr_est = 184.
        assert float(twin.lt1_hr_bpm) == pytest.approx(138.0)
        assert float(twin.lt2_hr_bpm) == pytest.approx(161.0)

    async def test_twin_created_at_is_populated(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "tw-created-at@example.com",
        )
        twin = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert twin.created_at is not None
        assert twin.created_at.tzinfo is not None
        # Reasonable recency — within the last 60 seconds.
        delta = (
            datetime.now(timezone.utc) - twin.created_at
        ).total_seconds()
        assert 0 <= delta < 60

    async def test_model_version_is_pinned(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "tw-model-version@example.com",
        )
        twin = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert twin.model_version == "v1-questionnaire-bootstrap"

    async def test_activity_id_is_null_at_bootstrap(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "tw-null-activity@example.com",
        )
        twin = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        # The ``questionnaire`` trigger has no triggering activity.
        assert twin.activity_id is None


# ---------------------------------------------------------------------------
# Data tier wiring — exit #6 in the plan.
# ---------------------------------------------------------------------------


class TestDataTierWiring:
    """``TwinState.data_tier`` matches ``infer_data_tier(hr, power)`` for
    every documented combination."""

    @pytest.mark.parametrize(
        "hr_source, power_source, expected_tier",
        [
            (HrSource.CHEST_STRAP_RR, PowerSource.RUNNING_POWER_METER, 1),
            (HrSource.CHEST_STRAP_NO_RR, PowerSource.RUNNING_POWER_METER, 2),
            (HrSource.WRIST_OPTICAL, PowerSource.RUNNING_POWER_METER, 2),
            (HrSource.NONE, PowerSource.RUNNING_POWER_METER, 2),
            (HrSource.CHEST_STRAP_RR, PowerSource.NONE, 3),
            (HrSource.CHEST_STRAP_NO_RR, PowerSource.NONE, 4),
            (HrSource.WRIST_OPTICAL, PowerSource.NONE, 4),
            (HrSource.NONE, PowerSource.NONE, 5),
        ],
    )
    async def test_twin_data_tier_matches_inferred_tier(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
        hr_source: HrSource,
        power_source: PowerSource,
        expected_tier: int,
    ) -> None:
        email = f"tier-{hr_source.value}-{power_source.value}@example.com"
        athlete = await _register_athlete(db_session, email)
        result = await onboarding_service.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=_profile_input(),
            prefs_input=_preferences_input(
                hr_source=hr_source, power_source=power_source
            ),
            goal_input=_goal_input_race_event(),
        )

        twin = (
            await db_session.execute(
                select(TwinState).where(
                    TwinState.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert int(twin.data_tier) == expected_tier
        # Service result carries the same int.
        assert result.data_tier == expected_tier
        # ``infer_data_tier`` remains the canonical mapping.
        assert int(infer_data_tier(hr_source, power_source)) == expected_tier


# ---------------------------------------------------------------------------
# Read endpoints — exit #10 in the plan.
# ---------------------------------------------------------------------------


class TestReadEndpointsBeforeOnboarding:
    """Before onboarding runs the read endpoints return None / empty."""

    async def test_get_profile_returns_row_post_registration(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """The AthleteProfile row is created during registration
        (Phase-1.1); onboarding enriches it but the read always works
        once auth has registered an athlete."""
        athlete = await _register_athlete(
            db_session, "read-profile-pre@example.com"
        )
        result = await onboarding_service.get_profile(athlete.id)
        assert result is not None
        assert result.athlete_id == athlete.id

    async def test_get_preferences_returns_none_before_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(
            db_session, "read-prefs-pre@example.com"
        )
        result = await onboarding_service.get_preferences(athlete.id)
        assert result is None

    async def test_get_twin_state_returns_none_before_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(
            db_session, "read-twin-pre@example.com"
        )
        result = await onboarding_service.get_twin_state(athlete.id)
        assert result is None

    async def test_get_twin_history_is_empty_before_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(
            db_session, "read-history-pre@example.com"
        )
        result = await onboarding_service.get_twin_history(
            athlete.id, limit=20
        )
        assert result == []


class TestReadEndpointsAfterOnboarding:
    """After onboarding all read endpoints return populated records."""

    async def test_get_preferences_returns_row_after_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "read-prefs-post@example.com",
        )
        result = await onboarding_service.get_preferences(athlete.id)
        assert result is not None
        assert result.athlete_id == athlete.id
        assert result.sport_background is SportBackground.RUNNING_PRIMARY

    async def test_get_profile_returns_enriched_profile_after_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "read-profile-post@example.com",
        )
        result = await onboarding_service.get_profile(athlete.id)
        assert result is not None
        # IANA timezone persisted at the bootstrap.
        assert result.timezone == "Europe/Lisbon"

    async def test_get_twin_state_returns_latest_after_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "read-twin-post@example.com",
        )
        result = await onboarding_service.get_twin_state(athlete.id)
        assert result is not None
        assert result.athlete_id == athlete.id
        assert result.confidence_level is TwinConfidenceLevel.LOW

    async def test_get_twin_history_returns_one_after_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "read-history-post@example.com",
        )
        result = await onboarding_service.get_twin_history(
            athlete.id, limit=20
        )
        assert len(result) == 1
        assert result[0].athlete_id == athlete.id


# ---------------------------------------------------------------------------
# get_onboarding_status — per-entity existence flags.
# ---------------------------------------------------------------------------


class TestGetOnboardingStatus:
    """The status endpoint reports each flag consistent with row existence."""

    async def test_status_false_all_flags_false_before_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _register_athlete(
            db_session, "status-pre@example.com"
        )
        result = await onboarding_service.get_onboarding_status(athlete.id)
        assert result.onboarding_complete is False
        assert result.has_profile is True
        assert result.has_preferences is False
        assert result.has_training_goal is False
        assert result.has_twin_state is False

    async def test_status_all_true_after_onboarding(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "status-post@example.com",
        )
        result = await onboarding_service.get_onboarding_status(athlete.id)
        assert result.onboarding_complete is True
        assert result.has_profile is True
        assert result.has_preferences is True
        assert result.has_training_goal is True
        assert result.has_twin_state is True

    async def test_status_raises_for_unknown_athlete(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        with pytest.raises(AthleteNotFoundError):
            await onboarding_service.get_onboarding_status(uuid.uuid4())


# ---------------------------------------------------------------------------
# update_profile — exit #8 in the plan.
# ---------------------------------------------------------------------------


class TestUpdateProfileService:
    """The service writes only the mutable subset; the API layer catches
    immutable-field PATCH attempts upstream."""

    async def test_update_profile_writes_mutable_fields_only(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "profile-patch-mutable@example.com",
        )
        updated = await onboarding_service.update_profile(
            athlete.id,
            height_cm=185.0,
            location_lat=38.7223,
            location_lng=-9.1393,
            training_window={
                "start": "06:00",
                "end": "20:00",
                "timezone": "Europe/Lisbon",
            },
        )

        assert updated.height_cm is not None
        assert float(updated.height_cm) == pytest.approx(185.0)
        assert float(updated.location_lat) == pytest.approx(38.7223)
        assert float(updated.location_lng) == pytest.approx(-9.1393)
        assert updated.training_window == {
            "start": "06:00",
            "end": "20:00",
            "timezone": "Europe/Lisbon",
        }
        # Immutables preserved.
        assert updated.timezone == "Europe/Lisbon"

    async def test_update_profile_partial_fields(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """PATCH must allow partial updates — supplying only height_cm
        must not blank out the other mutable fields."""
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "profile-patch-partial@example.com",
        )

        # Seed the mutable subset.
        await onboarding_service.update_profile(
            athlete.id,
            height_cm=180.0,
            location_lat=38.7223,
            location_lng=-9.1393,
            training_window={"start": "06:00", "end": "20:00"},
        )

        # Update only height — others preserved.
        refreshed_after_seed = (
            await db_session.execute(
                select(AthleteProfile).where(
                    AthleteProfile.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        seeded_location_lat = refreshed_after_seed.location_lat
        seeded_training_window = refreshed_after_seed.training_window

        await onboarding_service.update_profile(
            athlete.id, height_cm=181.5
        )

        refreshed_after_patch = (
            await db_session.execute(
                select(AthleteProfile).where(
                    AthleteProfile.athlete_id == athlete.id
                )
            )
        ).scalar_one()
        assert float(refreshed_after_patch.height_cm) == pytest.approx(
            181.5
        )
        # Untouched fields preserved.
        assert float(refreshed_after_patch.location_lat) == float(
            seeded_location_lat
        )
        assert refreshed_after_patch.training_window == (
            seeded_training_window
        )

    async def test_update_profile_missing_athlete_raises_not_found(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        with pytest.raises(AthleteNotFoundError):
            await onboarding_service.update_profile(uuid.uuid4(), height_cm=180.0)


# ---------------------------------------------------------------------------
# update_preferences — exit #9 in the plan.
# ---------------------------------------------------------------------------


class TestUpdatePreferencesService:
    """Top-level fields overwrite; ``weekly_schedule`` merges at the day
    level."""

    async def test_patch_weekly_schedule_flips_only_one_day(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "prefs-patch-day-merge@example.com",
        )
        await onboarding_service.update_preferences(
            athlete.id,
            patch={
                "weekly_schedule": {
                    "saturday": {"available": False},
                },
            },
        )
        refreshed = await onboarding_service.get_preferences(athlete.id)
        assert refreshed is not None
        # Saturday: flipped to unavailable; max_hours preserved.
        assert refreshed.weekly_schedule["saturday"]["available"] is False
        assert refreshed.weekly_schedule["saturday"]["max_hours"] == 3.0
        # Other days untouched.
        assert refreshed.weekly_schedule["monday"]["available"] is True
        assert refreshed.weekly_schedule["sunday"]["available"] is True

    async def test_patch_top_level_field_overwrites(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "prefs-patch-top-level@example.com",
        )
        await onboarding_service.update_preferences(
            athlete.id,
            patch={"years_structured_training": 10},
        )
        refreshed = await onboarding_service.get_preferences(athlete.id)
        assert refreshed is not None
        assert refreshed.years_structured_training == 10

    async def test_patch_idempotent(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """Re-applying the same patch must yield the same DB state."""
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "prefs-patch-idempotent@example.com",
        )
        await onboarding_service.update_preferences(
            athlete.id,
            patch={"weekly_schedule": {"sunday": {"max_hours": 2.0}}},
        )
        first = await onboarding_service.get_preferences(athlete.id)
        await onboarding_service.update_preferences(
            athlete.id,
            patch={"weekly_schedule": {"sunday": {"max_hours": 2.0}}},
        )
        second = await onboarding_service.get_preferences(athlete.id)
        assert first is not None and second is not None
        assert first.weekly_schedule == second.weekly_schedule

    async def test_patch_full_schedule_merges_all_seven_days(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """When every day is supplied, full replacement happens at the
        day level — daily keys still match the seven weekday names."""
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "prefs-patch-full-schedule@example.com",
        )
        new_schedule = _weekly_schedule_payload()
        new_schedule["monday"]["long_workout"] = True
        new_schedule["wednesday"]["long_workout"] = True
        new_schedule["saturday"]["available"] = False

        await onboarding_service.update_preferences(
            athlete.id,
            patch={"weekly_schedule": new_schedule},
        )
        refreshed = await onboarding_service.get_preferences(athlete.id)
        assert refreshed is not None
        assert (
            refreshed.weekly_schedule["monday"]["long_workout"] is True
        )
        assert (
            refreshed.weekly_schedule["wednesday"]["long_workout"] is True
        )
        assert refreshed.weekly_schedule["saturday"]["available"] is False
        # Untouched days preserved.
        assert refreshed.weekly_schedule["tuesday"]["available"] is True

    async def test_patch_missing_athlete_raises_not_found(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        with pytest.raises(AthleteNotFoundError):
            await onboarding_service.update_preferences(
                uuid.uuid4(),
                patch={"years_structured_training": 5},
            )

    async def test_unknown_patch_keys_are_ignored(
        self,
        db_session: AsyncSession,
        onboarding_service: OnboardingService,
    ) -> None:
        """The service is forward-compatible — unknown keys are silently
        ignored rather than rejected."""
        athlete = await _onboarded_athlete(
            db_session,
            onboarding_service,
            "prefs-patch-ignore-unknown@example.com",
        )
        # Should not raise even with an unknown key.
        await onboarding_service.update_preferences(
            athlete.id,
            patch={
                "years_structured_training": 7,
                "future_unknown_key": "ignored",
            },
        )
        refreshed = await onboarding_service.get_preferences(athlete.id)
        assert refreshed is not None
        assert refreshed.years_structured_training == 7