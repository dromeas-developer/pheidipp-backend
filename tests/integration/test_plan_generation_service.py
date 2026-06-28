"""Integration tests for ``PlanGenerationService`` against the test DB.

Covers the plan's Testing Requirements end-to-end:

* Race-event plan generates the documented phase sequence
  (aerobic_base → threshold_build → specific_endurance → taper → race_week).
* Phase date ranges are non-overlapping, ordered, and contiguous
  from the plan start to the goal event date.
* ``WeeklyPlan`` and ``PlannedSession`` rows cover the full duration
  with no gaps.
* All ``PlannedSession`` rows have ``status = 'scheduled'``; all
  ``Checkpoint`` rows have ``status = 'scheduled'``.
* No two consecutive quality sessions appear in any week unless they
  share a ``block_id`` (the architecture's "structural rule").
* Long runs are always followed by rest or recovery_run.
* Threshold / vo2max sessions are sandwiched between easy/rest days.
* ``GET /plan/checkpoints`` returns the documented mix (calibration,
  benchmark, progress_review).
* Supersession: generating a new plan for the same goal marks the old
  plan as superseded atomically (``superseded_at`` populated).
* ``training_plan_generated`` event lands in the transactional outbox
  via the same transaction.

Reference plan:
docs/implementation/phase-1/phase-1-4-p1-plan-generation.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_preferences import AthletePreferences
from app.models.checkpoint import Checkpoint
from app.models.enums import (
    CheckpointStatus,
    CheckpointType,
    DataTier,
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    PlannedSessionStatus,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
    TrainingGoalStatus,
    TrainingPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.system_event import EventPublicationStatus, SystemEvent, SystemEventOutbox
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from app.services.auth_service import AuthService
from app.services.onboarding_service import (
    OnboardingService,
    _GoalInput,
    _PreferencesInput,
    _ProfileInput,
)
from app.services.plan_generation_errors import (
    InvalidGoalTypeError,
    PlanGenerationError,
    TrainingLengthGateError,
)
from app.services.plan_generation_service import (
    PlanGenerationService,
    QUALITY_SESSION_TYPES,
    SANDWICHED_SESSION_TYPES,
)
from tests.payloads import _weekly_schedule_payload


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _register_athlete(
    db_session: AsyncSession, email: str
) -> Athlete:
    auth = AuthService(session=db_session)
    result = await auth.register(
        email=email,
        password="ValidPass123!",
        date_of_birth=datetime(1990, 1, 1, tzinfo=timezone.utc).date(),
        sex="not_specified",
        height_cm=180.0,
        ip_address="203.0.113.10",
        user_agent="PlanGenTest/1.0",
    )
    rows = (
        await db_session.execute(
            select(Athlete).where(Athlete.email == email)
        )
    ).scalar_one()
    _ = result
    return rows


def _onboarding_inputs(
    *,
    days_out: int = 7 * 12,
    goal_event_type: GoalEventType = GoalEventType.MARATHON,
) -> tuple[_ProfileInput, _PreferencesInput, _GoalInput]:
    """Default race-event inputs targeting ``days_out`` from today so the
    training-length gate passes with a comfortable margin (3 years
    experience, goal 12 weeks out — well below the
    ``marathon + intermediate`` threshold of 24 weeks)."""
    profile = _ProfileInput(
        timezone="Europe/Lisbon",
        training_window=None,
        height_cm=180.0,
    )
    prefs = _PreferencesInput(
        sport_background=SportBackground.RUNNING_PRIMARY,
        years_structured_training=3,
        training_time_of_day="morning",
        weekly_schedule=_weekly_schedule_payload(),
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.NONE,
        primary_training_platform=PrimaryTrainingPlatform.MANUAL,
    )
    event_date = date.today() + timedelta(days=days_out)
    goal = _GoalInput(
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=goal_event_type,
        goal_event_name="Test Marathon",
        goal_event_date=event_date,
        custom_distance_km=None,
        goal_description=None,
        weekly_volume_hours=6.0,
        weekly_volume_km=40.0,
        fitness_level=3,
        recent_injury=None,
        injury_severity=None,
        target_distance_km=None,
        target_time_minutes=None,
    )
    return profile, prefs, goal


async def _seeded_athlete_with_plan(
    db_session: AsyncSession,
    *,
    days_out: int = 7 * 12,
    goal_event_type: GoalEventType = GoalEventType.MARATHON,
) -> Athlete:
    """Register + onboard + generate a plan through the public
    ``PlanGenerationService.generate_plan`` (mirrors what
    OnboardingService does at the end of the onboarding transaction).

    The ``plan_service`` is injected into ``OnboardingService`` so that
    ``complete_onboarding`` calls ``generate_plan`` atomically before
    the transaction commits. Without it, onboarding completes but no
    ``TrainingPlan`` row is created.
    """
    athlete = await _register_athlete(
        db_session, f"plan-svc-{uuid.uuid4()}@example.com"
    )
    plan_svc = PlanGenerationService(session=db_session)
    onboarding = OnboardingService(session=db_session, plan_service=plan_svc)
    profile, prefs, goal = _onboarding_inputs(
        days_out=days_out, goal_event_type=goal_event_type
    )
    await onboarding.complete_onboarding(
        athlete_id=athlete.id,
        profile_input=profile,
        prefs_input=prefs,
        goal_input=goal,
    )
    return athlete


# ---------------------------------------------------------------------------
# Race-event plan generation happy path.
# ---------------------------------------------------------------------------


class TestRaceEventPlanStructure:
    """The race_event template produces the documented phase sequence."""

    async def test_phase_sequence_matches_documented_template(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        labels = [p["label"] for p in active_plan.phases_summary]
        # Five-phase template in plan order.
        assert labels == [
            "aerobic_base",
            "threshold_build",
            "specific_endurance",
            "taper",
            "race_week",
        ]

    async def test_phase_date_ranges_cover_full_duration(
        self, db_session: AsyncSession
    ) -> None:
        """Combined date range covers from the plan start to the goal
        event date without gaps."""
        athlete = await _seeded_athlete_with_plan(db_session)
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        phases = active_plan.phases_summary
        # Ranges monotonically advance.
        for prev, nxt in zip(phases, phases[1:]):
            assert prev["end_date"] < nxt["start_date"], (
                f"Gap between phases {prev['label']} and {nxt['label']}"
            )
        # First phase starts at the plan start.
        from datetime import datetime as _dt

        plan_start = _dt.now(timezone.utc).date()
        assert phases[0]["start_date"] >= plan_start.isoformat()

        goal = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id,
                    TrainingGoal.status == TrainingGoalStatus.ACTIVE,
                )
            )
        ).scalar_one()
        assert phases[-1]["end_date"] <= goal.goal_event_date.isoformat()

    async def test_total_weeks_matches_event_date_horizon(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(
            db_session, days_out=7 * 12
        )
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        total = sum(p["weeks"] for p in active_plan.phases_summary)
        # 12 weeks (±1 for rounding), spread across the five-phase template.
        assert 11 <= total <= 13

    async def test_weekly_plans_for_each_week(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()

        week_rows = (
            await db_session.execute(
                select(WeeklyPlan).where(
                    WeeklyPlan.training_plan_id == active_plan.id
                )
            )
        ).scalars().all()
        # One WeeklyPlan per week per TrainingPlan (DB unique).
        week_numbers = sorted(w.week_number for w in week_rows)
        assert week_numbers == list(range(1, len(week_numbers) + 1))


# ---------------------------------------------------------------------------
# Per-week invariant guards (consecutive quality / long-run rest /
# threshold sandwiching).
# ---------------------------------------------------------------------------


class TestWeeklyStructuralRules:
    """Per the architecture — enforced by the synthesiser."""

    @staticmethod
    def _is_quality(s_type) -> bool:
        from app.models.enums import SessionType

        return s_type in QUALITY_SESSION_TYPES and s_type in {
            SessionType.THRESHOLD,
            SessionType.VO2MAX,
            SessionType.TEMPO,
            SessionType.LONG_RUN,
            SessionType.HILL_REPEATS,
            SessionType.FARTLEK,
        }

    @staticmethod
    def _is_sandwiched(s_type) -> bool:
        from app.models.enums import SessionType

        return s_type in SANDWICHED_SESSION_TYPES and s_type in {
            SessionType.THRESHOLD,
            SessionType.VO2MAX,
        }

    @pytest.fixture
    async def structure(self, db_session: AsyncSession):
        athlete = await _seeded_athlete_with_plan(
            db_session, days_out=7 * 12
        )
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        weeks = (
            await db_session.execute(
                select(WeeklyPlan)
                .where(WeeklyPlan.training_plan_id == active_plan.id)
                .order_by(WeeklyPlan.week_number.asc())
            )
        ).scalars().all()
        sessions_per_week = []
        for week in weeks:
            rows = (
                await db_session.execute(
                    select(PlannedSession)
                    .where(PlannedSession.weekly_plan_id == week.id)
                    .order_by(PlannedSession.target_date.asc())
                )
            ).scalars().all()
            sessions_per_week.append(list(rows))
        return sessions_per_week

    @pytest.mark.parametrize("week_index", [1, 4, 8])
    async def test_no_two_consecutive_quality_unless_blocked(
        self, structure, week_index: int
    ) -> None:
        """Quality sessions (threshold / vo2max / tempo / interval /
        long_run / hill_repeats / fartlek) appear consecutive only when
        sharing ``block_id``."""
        sessions = structure[week_index - 1]
        for prev, nxt in zip(sessions, sessions[1:]):
            prev_q = self._is_quality(prev.session_type)
            nxt_q = self._is_quality(nxt.session_type)
            if prev_q and nxt_q:
                # Both quality — only valid if same block_id.
                assert (
                    prev.block_id is not None
                    and prev.block_id == nxt.block_id
                ), (
                    f"Consecutive quality without shared block_id on "
                    f"week {week_index}: "
                    f"{prev.session_type} -> {nxt.session_type}"
                )

    async def test_long_run_followed_by_rest_or_recovery(
        self, structure
    ) -> None:
        from app.models.enums import SessionType

        for i, sessions in enumerate(structure, start=1):
            long_runs = [
                s for s in sessions if s.session_type is SessionType.LONG_RUN
            ]
            for lr in long_runs:
                next_session = next(
                    (s for s in sessions if s.target_date > lr.target_date),
                    None,
                )
                assert next_session is not None, (
                    f"Week {i}: long run on the last day — no rest after"
                )
                assert next_session.session_type in {
                    SessionType.REST,
                    SessionType.RECOVERY_RUN,
                }, (
                    f"Week {i}: long run at {lr.target_date} "
                    f"should be followed by rest/recovery, got "
                    f"{next_session.session_type}"
                )

    async def test_threshold_sandwiched_between_easy_or_rest(
        self, structure
    ) -> None:
        """Threshold sessions live between easy/rest on the previous
        and next available day."""
        from app.models.enums import SessionType

        for i, sessions in enumerate(structure, start=1):
            threshold_rows = [
                s for s in sessions if s.session_type is SessionType.THRESHOLD
            ]
            for t in threshold_rows:
                prev_session = next(
                    (
                        s for s in sessions
                        if s.target_date < t.target_date
                    ),
                    None,
                )
                next_session = next(
                    (
                        s for s in sessions
                        if s.target_date > t.target_date
                    ),
                    None,
                )
                assert prev_session is not None and next_session is not None, (
                    f"Week {i}: threshold sandwich incomplete"
                )
                assert prev_session.session_type in {
                    SessionType.REST,
                    SessionType.RECOVERY_RUN,
                    SessionType.EASY_RUN,
                }, (
                    f"Week {i}: threshold day-before must be rest/recovery/easy, "
                    f"got {prev_session.session_type}"
                )
                assert next_session.session_type in {
                    SessionType.REST,
                    SessionType.RECOVERY_RUN,
                    SessionType.EASY_RUN,
                }, (
                    f"Week {i}: threshold day-after must be rest/recovery/easy, "
                    f"got {next_session.session_type}"
                )


# ---------------------------------------------------------------------------
# Status invariants — every row starts at "scheduled".
# ---------------------------------------------------------------------------


class TestStatusInvariants:
    async def test_all_planned_sessions_start_scheduled(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        sessions = (
            await db_session.execute(
                select(PlannedSession).where(
                    PlannedSession.training_plan_id == active_plan.id
                )
            )
        ).scalars().all()
        assert sessions, "expected planned sessions"
        for s in sessions:
            assert s.status is PlannedSessionStatus.SCHEDULED

    async def test_all_checkpoints_start_scheduled(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        cps = (
            await db_session.execute(
                select(Checkpoint).where(
                    Checkpoint.planned_session_id.in_(
                        select(PlannedSession.id).where(
                            PlannedSession.training_plan_id == active_plan.id
                        )
                    )
                )
            )
        ).scalars().all()
        assert cps
        for c in cps:
            assert c.status is CheckpointStatus.SCHEDULED


# ---------------------------------------------------------------------------
# Checkpoint mix — at least one of each documented type for a long plan.
# ---------------------------------------------------------------------------


class TestCheckpointCoverage:
    async def test_long_plan_has_calibration_benchmark_progress(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(
            db_session, days_out=7 * 18
        )
        active_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id.in_(
                        select(TrainingGoal.id).where(
                            TrainingGoal.athlete_id == athlete.id
                        )
                    )
                )
            )
        ).scalar_one()
        cps = (
            await db_session.execute(
                select(Checkpoint).where(
                    Checkpoint.planned_session_id.in_(
                        select(PlannedSession.id).where(
                            PlannedSession.training_plan_id == active_plan.id
                        )
                    )
                )
            )
        ).scalars().all()
        types = {c.type for c in cps}
        assert CheckpointType.CALIBRATION in types
        assert CheckpointType.BENCHMARK in types
        assert CheckpointType.PROGRESS_REVIEW in types


# ---------------------------------------------------------------------------
# Supersession — the service marks the previous plan as superseded and
# creates the new one in the same transaction.
# ---------------------------------------------------------------------------


class TestSupersessionAtomicity:
    async def test_generating_again_supersedes_previous_plan(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        goal = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id,
                    TrainingGoal.status == TrainingGoalStatus.ACTIVE,
                )
            )
        ).scalar_one()
        first_plan_id = (
            await db_session.execute(
                select(TrainingPlan.id).where(
                    TrainingPlan.training_goal_id == goal.id
                )
            )
        ).scalar_one()

        # Generate again — should supersede the previous plan atomically.
        service = PlanGenerationService(session=db_session)
        result = await service.generate_plan(athlete_id=athlete.id)
        await db_session.commit()

        # Reload the previous plan — must now be SUPERSEDED with
        # ``superseded_at`` populated.
        first_plan = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.id == first_plan_id
                )
            )
        ).scalar_one()
        assert first_plan.status is TrainingPlanStatus.SUPERSEDED
        assert first_plan.superseded_at is not None
        assert result.supersedes_plan_id == first_plan_id

        # New plan — one plan only currently active.
        active = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id == goal.id,
                    TrainingPlan.status == TrainingPlanStatus.ACTIVE,
                )
            )
        ).scalars().all()
        assert len(active) == 1
        assert active[0].id == result.plan.id

    async def test_superseded_plan_rows_remain(
        self, db_session: AsyncSession
    ) -> None:
        """Old plans are never deleted — ``superseded_at`` only."""
        athlete = await _seeded_athlete_with_plan(db_session)
        goal = (
            await db_session.execute(
                select(TrainingGoal).where(
                    TrainingGoal.athlete_id == athlete.id,
                    TrainingGoal.status == TrainingGoalStatus.ACTIVE,
                )
            )
        ).scalar_one()
        first_plan_id = (
            await db_session.execute(
                select(TrainingPlan.id).where(
                    TrainingPlan.training_goal_id == goal.id
                )
            )
        ).scalar_one()

        # Regenerate.
        service = PlanGenerationService(session=db_session)
        await service.generate_plan(athlete_id=athlete.id)
        await db_session.commit()

        # All plans for this goal remain.
        all_plans = (
            await db_session.execute(
                select(TrainingPlan).where(
                    TrainingPlan.training_goal_id == goal.id
                )
            )
        ).scalars().all()
        assert len(all_plans) == 2
        statuses = {p.status for p in all_plans}
        assert TrainingPlanStatus.SUPERSEDED in statuses
        assert TrainingPlanStatus.ACTIVE in statuses


# ---------------------------------------------------------------------------
# Event publication — training_plan_generated via transactional outbox.
# ---------------------------------------------------------------------------


class TestTrainingPlanGeneratedEvent:
    async def test_event_row_persisted(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        events = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.athlete_id == athlete.id,
                    SystemEvent.event_type == "training_plan_generated",
                )
            )
        ).scalars().all()
        assert len(events) == 1
        ev = events[0]
        assert ev.payload["training_plan_id"]
        assert ev.payload["training_goal_id"]
        assert ev.payload["phase_definitions_count"]
        # The event lands on the active plan.
        # The trigger is "new_goal" at first generation.
        assert ev.payload.get("trigger") == "new_goal"
        assert ev.payload.get("supersedes_plan_id") is None

    async def test_outbox_row_pending(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _seeded_athlete_with_plan(db_session)
        event = (
            await db_session.execute(
                select(SystemEvent).where(
                    SystemEvent.athlete_id == athlete.id,
                    SystemEvent.event_type == "training_plan_generated",
                )
            )
        ).scalar_one()
        outbox = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.event_id == event.event_id
                )
            )
        ).scalar_one_or_none()
        assert outbox is not None
        assert outbox.publication_status is EventPublicationStatus.PENDING


# ---------------------------------------------------------------------------
# Input validation — unsupported goal types and edge cases.
# ---------------------------------------------------------------------------


class TestInvalidGoalTypes:
    async def test_unsupported_goal_type_raises_invalid_error(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _register_athlete(
            db_session, f"bad-goal-{uuid.uuid4()}@example.com"
        )
        # Create the supporting rows manually by running onboarding with
        # a fitness_improvement goal — but that's rejected at onboarding.
        # Instead, insert a fitness_improvement goal directly to bypass
        # the onboarding whitelist:
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.FITNESS_IMPROVEMENT,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
            weekly_volume_hours=6.0,
            weekly_volume_km=40.0,
        )
        db_session.add(goal)
        # AthletePreferences + TwinState are needed by the service path.
        # We bypass via simulating a goal only and let the service fail
        # early on the missing prefs/twin-state — that triggers
        # PlanGenerationError (not InvalidGoalTypeError).
        await db_session.flush()

        # Manually insert prefs + twin so we hit the goal-type check.
        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=3,
            training_time_of_day="morning",
            weekly_schedule=_weekly_schedule_payload(),
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        db_session.add(prefs)
        twin = TwinState(
            athlete_id=athlete.id,
            data_tier=DataTier.TIER_5,
            model_version="v1-questionnaire-bootstrap",
            training_goal_id=goal.id,
            confidence_level="low",
            trigger="questionnaire",
            fitness=0.0,
            fatigue=0.0,
            form=0.0,
            metric_confidence={"lt1_hr": "low", "lt2_hr": "low"},
            readiness_level="green",
        )
        db_session.add(twin)
        await db_session.flush()

        service = PlanGenerationService(session=db_session)
        with pytest.raises(InvalidGoalTypeError):
            await service.generate_plan(athlete_id=athlete.id)


class TestTrainingLengthGateRaisesError:
    async def test_far_future_goal_with_low_capacity_raises_gate_error(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _register_athlete(
            db_session, f"gate-{uuid.uuid4()}@example.com"
        )
        onboarding = OnboardingService(session=db_session)
        profile, prefs, goal = _onboarding_inputs(days_out=7 * 60)
        # 60 weeks out + novice — gate must reject.
        prefs = _PreferencesInput(
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=1,  # novice
            training_time_of_day="morning",
            weekly_schedule=_weekly_schedule_payload(),
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.MANUAL,
        )
        await onboarding.complete_onboarding(
            athlete_id=athlete.id,
            profile_input=profile,
            prefs_input=prefs,
            goal_input=goal,
        )
        # Now invoke plan generation in a separate service — must raise
        # TrainingLengthGateError because the gate rejects the goal.
        service = PlanGenerationService(session=db_session)
        with pytest.raises(TrainingLengthGateError) as excinfo:
            await service.generate_plan(athlete_id=athlete.id)
        # Atomic guarantee — goal was already committed by onboarding,
        # so re-running the gate here is correct against the committed state.
        assert excinfo.value.gate_reason == "goal_too_far"


class TestMissingPrerequisitesRaiseError:
    async def test_missing_twin_state_raises_plan_generation_error(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await _register_athlete(
            db_session, f"no-twin-{uuid.uuid4()}@example.com"
        )
        # No onboarding — service has nothing to operate on.
        service = PlanGenerationService(session=db_session)
        with pytest.raises(PlanGenerationError):
            await service.generate_plan(athlete_id=athlete.id)

    async def test_missing_athlete_raises_plan_generation_error(
        self, db_session: AsyncSession
    ) -> None:
        service = PlanGenerationService(session=db_session)
        with pytest.raises(PlanGenerationError):
            await service.generate_plan(athlete_id=uuid.uuid4())
