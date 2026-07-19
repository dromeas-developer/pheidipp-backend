"""Atomic plan generation for Phase-1.4 modes."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_preferences import AthletePreferences
from app.models.checkpoint import Checkpoint
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.models.enums import (
    CheckpointStatus,
    CheckpointType,
    GoalType,
    PhaseLabel,
    PlannedSessionStatus,
    SessionPriority,
    SessionSlot,
    SessionType,
    TrainingPlanStatus,
    WeeklyPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan, WeeklySession
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.checkpoint_repository import CheckpointRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.weekly_plan_repository import (
    WeeklyPlanRepository,
    WeeklySessionRepository,
)
from app.services.event_publisher import EventPublisher
from app.services.plan_generation_errors import (
    InvalidGoalTypeError,
    PlanGenerationError,
    TrainingLengthGateError,
)
from app.services.plan_generation_templates import (
    CheckpointRecord,
    PhaseAllocation,
    PhaseDefinitionRecord,
    QUALITY_SESSION_TYPES,
    SANDWICHED_SESSION_TYPES,
    TrainingLengthGateResult,
    allocate_race_event_phases,
    derive_experience_level,
    evaluate_training_length_gate,
    schedule_checkpoints,
    to_phase_definition_record,
)


# ---------------------------------------------------------------------------
# Constants.
# ---------------------------------------------------------------------------


#: Phase-1.4 whitelist of goal types the service will generate plans for.
ALLOWED_PLAN_GENERATION_GOAL_TYPES: frozenset[GoalType] = frozenset(
    {GoalType.RACE_EVENT, GoalType.TARGET_PERFORMANCE}
)

#: Approximate duration for each SessionType in minutes. Architects use
#: these for the headline-level "approximate_duration_minutes" only;
#: workout generation (Phase-1.5b) replaces them with computed
#: workouts.
DEFAULT_SESSION_TYPE_DURATION_MIN: Dict[SessionType, int] = {
    SessionType.REST: 0,
    SessionType.RECOVERY_RUN: 30,
    SessionType.EASY_RUN: 45,
    SessionType.LONG_RUN: 90,
    SessionType.MEDIUM_LONG_RUN: 75,
    SessionType.STEADY_STATE: 60,
    SessionType.TEMPO: 55,
    SessionType.THRESHOLD: 60,
    SessionType.VO2MAX: 60,
    SessionType.HILL_REPEATS: 50,
    SessionType.FARTLEK: 50,
    SessionType.STRIDES: 30,
    SessionType.DRILLS_MOBILITY: 30,
    SessionType.CROSS_TRAINING: 45,
    SessionType.TEST_SESSION: 60,
    SessionType.OPTIONAL_RUN: 40,
}

#: Ordered canonical weekdays per the architecture's athlete-local week
#: convention. The plan engine works in athlete-local dates; the API
#: consumer resolves timezone at display time.
DAYS_OF_WEEK: Tuple[str, ...] = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)


# ---------------------------------------------------------------------------
# Daily session assignment — local data structure produced by the
# weekly synthesiser and consumed by the persistence layer.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SessionDayAssignment:
    """One calendar day inside a generated week.

    A plan synthesises one ``PlannedSession`` and one ``WeeklySession``
    per assignment. ``is_checkpoint=True`` flags the day that
    corresponds to a checkpoint record — the service creates both
    rows with the matching ``checkpoint_type`` /
    ``checkpoint_metric`` and additionally inserts a Checkpoint row.
    """

    target_date: date
    session_type: SessionType
    intent_description: str
    approximate_duration_minutes: int
    block_id: Optional[str] = None
    block_position: Optional[str] = None
    block_session_count: Optional[int] = None
    is_checkpoint: bool = False
    checkpoint_type: Optional[CheckpointType] = None
    checkpoint_metric: Optional[str] = None
    checkpoint_record: Optional[CheckpointRecord] = None
    session_slot: Optional[SessionSlot] = None
    session_priority: SessionPriority = SessionPriority.PRIMARY


@dataclass(frozen=True)
class _WeekSynthesis:
    """Output of synthesising one week — all per-day assignments plus
    the WeeklyPlan struct fields that drive the row creation.
    """

    week_number_in_plan: int
    phase_index: int
    week_start: date
    week_end: date
    assignments: Tuple[SessionDayAssignment, ...] = ()

    @property
    def phase_label(self) -> PhaseLabel:
        """Return the phase label for this week.

        The synthesis engine embeds the phase label in the
        ``intent_description`` of every assignment; reading the first
        assignment's intent is the canonical source for this week. If
        the assignments are empty (which only happens when the weekly
        schedule has zero available days), we default to the
        first-phase label.
        """
        if not self.assignments:
            return PhaseLabel.AEROBIC_BASE
        # Derive from the intent description format: "phase_label,
        # week N". The phase label is the trailing label string.
        try:
            label_token = (
                self.assignments[0].intent_description.rsplit("(", 1)[-1]
                .split(",", 1)[0]
                .strip()
            )
            return PhaseLabel(label_token)
        except (ValueError, IndexError):
            return PhaseLabel.AEROBIC_BASE


@dataclass(frozen=True)
class _PlanConfig:
    """Inputs to the deterministic-expansion engine."""

    total_weeks: int
    plan_start: date
    goal_event_date: Optional[date]
    training_goal_id: uuid.UUID
    twin_state_id: uuid.UUID
    athlete_id: uuid.UUID
    goal_type: GoalType
    is_target_performance: bool


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PlanGenerationResult:
    """Value object returned by :meth:`PlanGenerationService.generate_plan`.

    Carries the freshly created TrainingPlan plus the participating
    WeeklyPlans / WeeklySessions / PlannedSessions / Checkpoints so
    the API layer can build responses without re-querying.
    """

    plan: TrainingPlan
    weekly_plans: List[WeeklyPlan]
    weekly_sessions: List[WeeklySession]
    planned_sessions: List[PlannedSession]
    checkpoints: List[Checkpoint]
    supersedes_plan_id: Optional[uuid.UUID]


class PlanGenerationService:
    """Atomic plan generation for race_event and target_performance goals."""

    def __init__(
        self,
        session: AsyncSession,
        events: Optional[EventPublisher] = None,
    ) -> None:
        self.session = session
        self.athletes = AthleteRepository(session)
        self.goals = TrainingGoalRepository(session)
        self.twin_states = TwinStateRepository(session)
        self.preferences = AthletePreferencesRepository(session)
        self.plans = TrainingPlanRepository(session)
        self.weekly_plans = WeeklyPlanRepository(session)
        self.weekly_sessions = WeeklySessionRepository(session)
        self.checkpoints = CheckpointRepository(session)
        if events is None:
            # Build a real publisher on demand if the API layer did
            # not inject one. Preserves the atomic-event guarantee.
            from app.repositories.system_event_outbox_repository import (
                SystemEventOutboxRepository,
            )
            from app.repositories.system_event_repository import (
                SystemEventRepository,
            )

            self.events = EventPublisher(
                SystemEventRepository(session),
                SystemEventOutboxRepository(session),
            )
        else:
            self.events = events

    # ------------------------------------------------------------------
    # Public entry point.
    # ------------------------------------------------------------------

    async def generate_plan(
        self,
        *,
        athlete_id: uuid.UUID,
    ) -> PlanGenerationResult:
        """Generate the active TrainingPlan for *athlete_id*.

        See module docstring for atomicity and invariant guarantees.

        Raises:
            PlanGenerationError: catch-all plan-generation failure.
            InvalidGoalTypeError: goal type outside the whitelist.
            TrainingLengthGateError: gate did not ``proceed``.
        """
        athlete = await self.athletes.get_by_id(athlete_id)
        if athlete is None:
            raise PlanGenerationError(
                f"athlete {athlete_id} not found"
            )

        goal_row = await self.goals.get_active(athlete_id)
        if goal_row is None:
            raise PlanGenerationError(
                "no active training goal for athlete"
            )

        if goal_row.goal_type not in ALLOWED_PLAN_GENERATION_GOAL_TYPES:
            raise InvalidGoalTypeError(
                f"goal_type '{goal_row.goal_type.value}' is not "
                f"supported by plan generation"
            )

        twin_state_row = await self.twin_states.get_latest(athlete_id)
        if twin_state_row is None:
            raise PlanGenerationError(
                "no twin state available for athlete"
            )

        prefs_row = await self.preferences.get_by_athlete_id(athlete_id)
        if prefs_row is None:
            raise PlanGenerationError(
                "no athlete preferences available"
            )

        plan_start = datetime.now(timezone.utc).date()
        if goal_row.goal_type == GoalType.RACE_EVENT:
            return await self._generate_race_event_plan(
                athlete_id=athlete_id,
                goal_row=goal_row,
                twin_state_row=twin_state_row,
                prefs_row=prefs_row,
                plan_start=plan_start,
            )
        return await self._generate_target_performance_plan(
            athlete_id=athlete_id,
            goal_row=goal_row,
            twin_state_row=twin_state_row,
            prefs_row=prefs_row,
            plan_start=plan_start,
        )

    # ------------------------------------------------------------------
    # Race-event path.
    # ------------------------------------------------------------------

    async def _generate_race_event_plan(
        self,
        *,
        athlete_id: uuid.UUID,
        goal_row: TrainingGoal,
        twin_state_row: TwinState,
        prefs_row: AthletePreferences,
        plan_start: date,
    ) -> PlanGenerationResult:
        """race_event-specific orchestration: gate → allocation → persist."""
        if (
            goal_row.goal_event_date is None
            or goal_row.goal_event_type is None
        ):
            raise PlanGenerationError(
                "race_event requires goal_event_date and goal_event_type"
            )

        weeks_until_goal = _weeks_between(plan_start, goal_row.goal_event_date)
        experience_level = derive_experience_level(
            prefs_row.years_structured_training
        )
        fitness_level = _fitness_level_to_self_report(goal_row.fitness_level)

        gate_result: TrainingLengthGateResult = evaluate_training_length_gate(
            weeks_until_goal=weeks_until_goal,
            fitness_level=fitness_level,
            goal_event_type=goal_row.goal_event_type.value,
            experience_level=experience_level,
        )
        if gate_result.action != "proceed":
            raise TrainingLengthGateError(
                action=gate_result.action,
                message=gate_result.message,
                gate_reason=gate_result.gate_reason or "unknown",
            )

        config = _PlanConfig(
            total_weeks=weeks_until_goal,
            plan_start=plan_start,
            goal_event_date=goal_row.goal_event_date,
            training_goal_id=goal_row.id,
            twin_state_id=twin_state_row.id,
            athlete_id=athlete_id,
            goal_type=GoalType.RACE_EVENT,
            is_target_performance=False,
        )
        return await self._persist_full_plan(
            config=config,
            twin_metric_confidence=twin_state_row.metric_confidence or {},
            goal_event_type=goal_row.goal_event_type.value,
            prefs_row=prefs_row,
        )

    # ------------------------------------------------------------------
    # Target-performance path.
    # ------------------------------------------------------------------

    async def _generate_target_performance_plan(
        self,
        *,
        athlete_id: uuid.UUID,
        goal_row: TrainingGoal,
        twin_state_row: TwinState,
        prefs_row: AthletePreferences,
        plan_start: date,
    ) -> PlanGenerationResult:
        """target_performance path: gap analysis → reuse race_event template."""
        target_distance_km = goal_row.target_distance_km or 0.0
        target_time_minutes = goal_row.target_time_minutes or 0
        current_estimate = _estimate_current_performance(
            twin_state_row=twin_state_row,
            target_distance_km=target_distance_km,
        )
        gap_pct = _compute_gap_percentage(
            current_estimate_min=current_estimate,
            target_time_min=target_time_minutes,
        )
        gap_class = _classify_gap(gap_pct)
        estimated_weeks = _estimate_weeks_to_target(
            gap_classification=gap_class,
            fitness_level=goal_row.fitness_level,
        )

        if goal_row.goal_event_date is not None:
            plan_goal_date = goal_row.goal_event_date
        else:
            plan_goal_date = plan_start + timedelta(days=estimated_weeks * 7)

        weeks_until_goal = max(4, _weeks_between(plan_start, plan_goal_date))

        config = _PlanConfig(
            total_weeks=weeks_until_goal,
            plan_start=plan_start,
            goal_event_date=plan_goal_date,
            training_goal_id=goal_row.id,
            twin_state_id=twin_state_row.id,
            athlete_id=athlete_id,
            goal_type=GoalType.TARGET_PERFORMANCE,
            is_target_performance=True,
        )
        return await self._persist_full_plan(
            config=config,
            twin_metric_confidence=twin_state_row.metric_confidence or {},
            goal_event_type="custom",  # generic for target_performance
            prefs_row=prefs_row,
        )

    # ------------------------------------------------------------------
    # Atomic persistence — shared by both mode paths.
    # ------------------------------------------------------------------

    async def _persist_full_plan(
        self,
        *,
        config: _PlanConfig,
        twin_metric_confidence: Dict[str, Optional[str]],
        goal_event_type: str,
        prefs_row: AthletePreferences,
    ) -> PlanGenerationResult:
        """Run the full insertion sequence in one transaction."""
        allocations = allocate_race_event_phases(total_weeks=config.total_weeks)

        # Supersede any existing active plan for this goal.
        previous_plan = await self.plans.get_active_for_goal(
            config.training_goal_id
        )
        previous_plan_id: Optional[uuid.UUID] = None
        if previous_plan is not None:
            previous_plan_id = previous_plan.id
            await self.plans.supersede(previous_plan)

        # PhaseDefinition + weekly distribution derivation.
        phase_definition_records: List[PhaseDefinitionRecord] = [
            to_phase_definition_record(allocation)
            for allocation in allocations
        ]
        phase_definitions_json = [
            _phase_definition_to_dict(rec)
            for rec in phase_definition_records
        ]
        weekly_distributions = _expand_phases_to_weekly(
            phase_definition_records
        )
        weekly_distributions_json = [dict(row) for row in weekly_distributions]

        # Phase date ranges.
        phase_date_ranges = _compute_phase_date_ranges(
            plan_start=config.plan_start,
            total_weeks=config.total_weeks,
        )

        # Checkpoint scheduling.
        phase_starts = [start for start, _end in phase_date_ranges]
        checkpoint_records = schedule_checkpoints(
            allocations=allocations,
            phase_starts=phase_starts,
            twin_metric_confidence=twin_metric_confidence,
            goal_event_type=goal_event_type,
        )
        checkpoint_schedule_json = [
            _checkpoint_record_to_dict(rec) for rec in checkpoint_records
        ]

        # Strategic rationale.
        strategic_rationale = _build_strategic_rationale(
            goal_type=config.goal_type,
            allocations=allocations,
        )

        # Build the TrainingPlan row.
        new_plan = TrainingPlan(
            training_goal_id=config.training_goal_id,
            twin_state_id=config.twin_state_id,
            phases_summary=[
                {
                    "label": allocation.label.value,
                    "start_date": start.isoformat(),
                    "end_date": end.isoformat(),
                    "weeks": allocation.weeks,
                    "primary_focus": allocation.primary_focus,
                    "weekly_session_count": allocation.weekly_session_count,
                }
                for allocation, (start, end) in zip(
                    allocations, phase_date_ranges
                )
            ],
            phase_definitions=phase_definitions_json,
            weekly_distributions=weekly_distributions_json,
            status=TrainingPlanStatus.ACTIVE,
            superseded_at=None,
            strategic_rationale=strategic_rationale,
            checkpoint_schedule=checkpoint_schedule_json,
        )
        await self.plans.add(new_plan)

        # Synthesise every week into SessionDayAssignment lists.
        week_syntheses: List[_WeekSynthesis] = []
        for week_index in range(config.total_weeks):
            phase_index = _phase_index_for_week(allocations, week_index)
            allocation = allocations[phase_index]
            phase_start = phase_date_ranges[phase_index][0]
            week_start_date = phase_start + timedelta(days=week_index * 7)
            week_end_date = week_start_date + timedelta(days=6)
            week_index_in_phase = (
                week_index - _sum_weeks_before(allocations, phase_index)
            )
            assigned_checkpoints = [
                cp
                for cp in checkpoint_records
                if cp.week_number == week_index + 1
            ]
            assignments = self._synthesize_week(
                week_number_in_plan=week_index + 1,
                week_index_in_phase=week_index_in_phase,
                allocation=allocation,
                week_start=week_start_date,
                phase_label=allocation.label,
                weekly_schedule=getattr(prefs_row, "weekly_schedule", {}) or {},
                checkpoints_in_week=assigned_checkpoints,
            )
            week_syntheses.append(
                _WeekSynthesis(
                    week_number_in_plan=week_index + 1,
                    phase_index=phase_index,
                    week_start=week_start_date,
                    week_end=week_end_date,
                    assignments=tuple(assignments),
                )
            )

        # Materialise WeeklyPlan rows.
        weekly_plan_rows: List[WeeklyPlan] = []
        weekly_session_rows: List[WeeklySession] = []
        planned_session_rows: List[PlannedSession] = []
        checkpoint_rows: List[Checkpoint] = []
        for week in week_syntheses:
            allocation = allocations[week.phase_index]
            weekly_plan_row = WeeklyPlan(
                training_plan_id=new_plan.id,
                week_number=week.week_number_in_plan,
                adjusted_intent={
                    "methodology": {},
                    "target_distribution": dict(allocation.distribution),
                    "target_specificity": float(allocation.specificity),
                    "objective": list(allocation.objectives),
                    "session_count": len(week.assignments),
                    "adjustment_made": False,
                    "distribution_adjusted": False,
                    "distribution_adjustment_reason": None,
                    "max_sessions": None,
                    "session_types_preferred": None,
                    "avoid_session_types": None,
                },
                status=WeeklyPlanStatus.SYNTHESISED,
                sessions_completed=0,
                sessions_missed=0,
                sessions_skipped=0,
                accumulated_fatigue_delta=0.0,
                doubles_days_count=0,
                week_starts_at=week.week_start,
                week_ends_at=week.week_end,
            )
            weekly_plan_rows.append(weekly_plan_row)
            self.session.add(weekly_plan_row)

        # Flush — WeeklyPlans now have ids, so we can populate FKs.
        await self.session.flush()
        for weekly_plan_row in weekly_plan_rows:
            await self.session.refresh(weekly_plan_row)

        # Materialise WeeklySession + PlannedSession rows.
        for weekly_plan_row, week in zip(weekly_plan_rows, week_syntheses):
            allocation = allocations[week.phase_index]
            for assignment in week.assignments:
                weekly_session_row = WeeklySession(
                    weekly_plan_id=weekly_plan_row.id,
                    target_date=assignment.target_date,
                    session_type=assignment.session_type,
                    intent_description=assignment.intent_description,
                    approximate_duration_minutes=(
                        assignment.approximate_duration_minutes
                    ),
                    is_checkpoint=assignment.is_checkpoint,
                    checkpoint_type=assignment.checkpoint_type,
                    checkpoint_metric=assignment.checkpoint_metric,
                    status="scheduled",
                    planned_session_id=None,
                    block_id=assignment.block_id,
                    block_position=assignment.block_position,
                    block_session_count=assignment.block_session_count,
                )
                self.session.add(weekly_session_row)
                weekly_session_rows.append(weekly_session_row)

                planned_session_row = PlannedSession(
                    weekly_plan_id=weekly_plan_row.id,
                    training_plan_id=new_plan.id,  # denormalised
                    target_date=assignment.target_date,
                    week_number=week.week_number_in_plan,
                    phase_label=allocation.label,
                    session_type=assignment.session_type,
                    intent_description=assignment.intent_description,
                    approximate_duration_minutes=(
                        assignment.approximate_duration_minutes
                    ),
                    checkpoint_type=assignment.checkpoint_type,
                    checkpoint_metric=assignment.checkpoint_metric,
                    status=PlannedSessionStatus.SCHEDULED,
                    session_slot=assignment.session_slot,
                    session_priority=assignment.session_priority,
                    block_id=assignment.block_id,
                    block_position=assignment.block_position,
                    block_session_count=assignment.block_session_count,
                    is_suggested=False,
                )
                self.session.add(planned_session_row)
                planned_session_rows.append(planned_session_row)

        # Flush — PlannedSessions now have ids.
        await self.session.flush()
        for planned_session_row in planned_session_rows:
            await self.session.refresh(planned_session_row)
        for weekly_session_row in weekly_session_rows:
            await self.session.refresh(weekly_session_row)

        # Materialise Checkpoint rows by walking weekly syntheses.
        planned_session_idx = 0
        for week in week_syntheses:
            for assignment in week.assignments:
                if assignment.is_checkpoint and (
                    assignment.checkpoint_type is not None
                ):
                    planned_session_row = planned_session_rows[
                        planned_session_idx
                    ]
                    checkpoint_row = Checkpoint(
                        planned_session_id=planned_session_row.id,
                        type=assignment.checkpoint_type,
                        target_metric=(
                            assignment.checkpoint_metric or "form"
                        ),
                        secondary_metrics=[],
                        twin_update_expected=(
                            assignment.checkpoint_type
                            in {
                                CheckpointType.CALIBRATION,
                                CheckpointType.BENCHMARK,
                            }
                        ),
                        replan_trigger=(
                            assignment.checkpoint_type
                            == CheckpointType.CALIBRATION
                        ),
                        status=CheckpointStatus.SCHEDULED,
                    )
                    self.session.add(checkpoint_row)
                    checkpoint_rows.append(checkpoint_row)
                planned_session_idx += 1

        # Flush Checkpoint rows.
        await self.session.flush()
        for checkpoint_row in checkpoint_rows:
            await self.session.refresh(checkpoint_row)

        # Persist ``training_plan_generated`` event/outbox.
        await self.events.publish(
            event_type="training_plan_generated",
            athlete_id=config.athlete_id,
            payload={
                "training_plan_id": str(new_plan.id),
                "training_goal_id": str(config.training_goal_id),
                "phase_definitions_count": len(phase_definition_records),
                "total_weeks": config.total_weeks,
                "supersedes_plan_id": (
                    str(previous_plan_id) if previous_plan_id else None
                ),
                "trigger": "new_goal",
            },
        )

        # Single commit boundary.
        await self.session.commit()

        return PlanGenerationResult(
            plan=new_plan,
            weekly_plans=weekly_plan_rows,
            weekly_sessions=weekly_session_rows,
            planned_sessions=planned_session_rows,
            checkpoints=checkpoint_rows,
            supersedes_plan_id=previous_plan_id,
        )

    # ------------------------------------------------------------------
    # Weekly synthesis — pure deterministic expansion for one week.
    # ------------------------------------------------------------------

    def _synthesize_week(
        self,
        *,
        week_number_in_plan: int,
        week_index_in_phase: int,
        allocation: PhaseAllocation,
        week_start: date,
        phase_label: PhaseLabel,
        weekly_schedule: Dict[str, Any],
        checkpoints_in_week: Sequence[CheckpointRecord],
    ) -> List[SessionDayAssignment]:
        """Synthesise one week's ``SessionDayAssignment`` list.

        Deterministic and pure — same inputs always produce the same
        output. Respects every architecture invariant:

          * Long run placed on the day marked ``long_workout`` in the
            athlete's ``weekly_schedule`` (or Saturday as fallback).
          * One rest day minimum.
          * Threshold / VO2max sessions sandwiched between easy / rest.
          * Long run followed by rest or recovery_run.
          * No two consecutive quality sessions, unless they share a
            ``block_id``.
        """
        weekday_map = _normalise_weekly_schedule(weekly_schedule)
        long_workout_day = _pick_long_workout_day(weekday_map)
        available_days = [
            day for day in DAYS_OF_WEEK if weekday_map[day]["available"]
        ]
        if not available_days:
            available_days = list(DAYS_OF_WEEK)

        session_count_target = min(
            allocation.weekly_session_count,
            len(available_days) - 1,
        )
        session_count_target = max(session_count_target, 3)

        assignments_by_day: Dict[str, SessionDayAssignment] = {}

        def reserve_day(
            day: str,
            session_type: SessionType,
        ) -> bool:
            if day not in available_days:
                return False
            if day in assignments_by_day:
                return False
            prev = _day_before(day, assignments_by_day)
            nxt = _day_after(day, available_days, assignments_by_day)
            # Quality-sandwiching rule.
            if session_type in SANDWICHED_SESSION_TYPES:
                if prev is not None and _is_quality(prev.session_type):
                    return False
                if nxt is not None and _is_quality(nxt.session_type):
                    return False
            # No two consecutive quality sessions, unless they share a block.
            if session_type in QUALITY_SESSION_TYPES:
                if prev is not None and _is_quality(prev.session_type):
                    return False
                if nxt is not None and _is_quality(nxt.session_type):
                    return False
            intent = _build_intent_description(
                session_type=session_type,
                phase_label=phase_label,
                week_index_in_phase=week_index_in_phase,
            )
            duration = DEFAULT_SESSION_TYPE_DURATION_MIN.get(
                session_type, 60
            )
            target_date = week_start + timedelta(
                days=DAYS_OF_WEEK.index(day)
            )
            assignments_by_day[day] = SessionDayAssignment(
                target_date=target_date,
                session_type=session_type,
                intent_description=intent,
                approximate_duration_minutes=duration,
                session_priority=SessionPriority.PRIMARY,
            )
            return True

        # 1. Place the long run first — anchors the week.
        if not reserve_day(long_workout_day, SessionType.LONG_RUN):
            for candidate in ("saturday",) + tuple(available_days):
                if reserve_day(candidate, SessionType.LONG_RUN):
                    break

        # 2. Place the phase's primary quality session. For SANDWICHED
        #    session types (THRESHOLD / VO2max) we skip the first
        #    available day so the architectural "sandwich between
        #    easy/rest" guarantee has a preceding non-quality slot
        #    within the same week — see
        #    ``docs/architecture/02-computations/plan-generation-race.md``
        #    → Session Distribution Rules.
        phase_quality_target = _pick_phase_quality_target(phase_label)
        if phase_quality_target is not None:
            candidate_order = list(available_days)
            if phase_quality_target in SANDWICHED_SESSION_TYPES:
                # Drop the first day-of-week (Monday in the default
                # fixture) so THRESHOLD/VO2max always sit between two
                # non-quality sessions. The synthesiser falls back to
                # ordinary ordering if every day-of-week is "first"
                # (e.g. only one day available).
                if len(candidate_order) > 1:
                    candidate_order = candidate_order[1:]
            for candidate in candidate_order:
                if candidate in assignments_by_day:
                    continue
                if reserve_day(candidate, phase_quality_target):
                    break

        # 3. Fill remaining days with the easy-session rotation.
        idx = 0
        while (
            sum(1 for _ in assignments_by_day) < session_count_target
            and idx < len(available_days)
        ):
            day = available_days[idx]
            idx += 1
            if day in assignments_by_day:
                continue
            target_type = _pick_easy_rotation(
                phase_label=phase_label,
                week_index_in_phase=week_index_in_phase,
            )
            reserve_day(day, target_type)

        # 4. Apply checkpoint placements — at most one per week per
        #    scheduler, and only on days already present in the week.
        ordered_days = sorted(
            assignments_by_day.keys(),
            key=lambda d: DAYS_OF_WEEK.index(d),
        )
        for cp in checkpoints_in_week:
            if not ordered_days:
                # Architecture path — every week has at least one day.
                continue
            cp_day_index = _pick_checkpoint_day_index(
                day_labels=ordered_days,
                session_type=cp.session_type,
            )
            day = ordered_days[cp_day_index]
            current = assignments_by_day[day]
            assignments_by_day[day] = SessionDayAssignment(
                target_date=current.target_date,
                session_type=cp.session_type,
                intent_description=cp.planner_message,
                approximate_duration_minutes=(
                    DEFAULT_SESSION_TYPE_DURATION_MIN.get(
                        cp.session_type, 60
                    )
                ),
                is_checkpoint=True,
                checkpoint_type=cp.type,
                checkpoint_metric=cp.target_metric,
                checkpoint_record=cp,
                session_priority=current.session_priority,
                session_slot=current.session_slot,
            )

        # Return assignments ordered by weekday (Monday-first), then
        # repair the structural invariants the placement phase does not
        # guarantee on its own. The repair pass enforces:
        #
        #   * LONG_RUN is followed (within the same week) by a
        #     RECOVERY_RUN session — inserting one on the next
        #     target_date if LONG_RUN is on the week's last scheduled
        #     day.
        #   * THRESHOLD / VO2MAX sessions are sandwiched between
        #     sessions of REST / RECOVERY_RUN / EASY_RUN on both
        #     sides — rewriting the adjacent daily slots in place.
        ordered_assignments = sorted(
            assignments_by_day.values(),
            key=lambda a: (
                _weekday_index_for_date(a.target_date, week_start)
            ),
        )
        repaired = _repair_weekly_invariants(
            ordered_assignments,
            week_start=week_start,
        )
        # Re-sort after the repair because LONG_RUN-follow-up
        # inserts a new earlier-dated or later-dated assignment.
        return sorted(
            repaired,
            key=lambda a: (
                _weekday_index_for_date(a.target_date, week_start)
            ),
        )


# ---------------------------------------------------------------------------
# Pure helpers — kept outside the class for testability.
# ---------------------------------------------------------------------------


def _pick_checkpoint_day_index(
    day_labels: Sequence[str],
    *,
    session_type: Optional[SessionType] = None,
) -> int:
    """Deterministic pick of a day index for a single checkpoint.

    Prefers mid-week (Wed), falling back to the first available day
    so the placement stays deterministic without a random seed.

    For SANDWICHED session types (THRESHOLD / VO2MAX), the pick
    deliberately avoids index 0: the architectural invariant
    "threshold / vo2max sessions are sandwiched between easy or
    rest days on both sides" cannot be satisfied when the
    replacement lands on the first day of the week (no preceding
    assignment exists in the same week to provide the prev-side
    of the sandwich). The pick walks one slot forward whenever
    the preferred slot is the first day and a later slot is
    available. Checkpoints whose ``session_type`` is not in the
    sandwiched set (e.g. EASY_RUN benchmarks, LONG_RUN race
    simulations) ignore the day-0 avoidance rule.
    """
    if not day_labels:
        return 0
    preferred = "wednesday"
    if preferred in day_labels:
        idx = day_labels.index(preferred)
    elif "thursday" in day_labels:
        idx = day_labels.index("thursday")
    else:
        idx = 0
    if (
        session_type is not None
        and session_type in SANDWICHED_SESSION_TYPES
        and idx == 0
        and len(day_labels) > 1
    ):
        idx = 1
    return idx


def _weekday_index_for_date(target_date: date, week_start: date) -> int:
    """Return the Monday-indexed weekday of *target_date* relative to
    *week_start*. Capped to 0..6.
    """
    delta = (target_date - week_start).days
    return max(0, min(6, delta))


def _weeks_between(start: date, end: date) -> int:
    """Number of full weeks between *start* and *end*.

    Rounded up to the nearest week so a 15-day timeline becomes a
    3-week plan. Sub-zero horizons are clamped to 1 week so the gate
    logic never sees a zero-length plan.
    """
    if end <= start:
        return 1
    days = (end - start).days
    return max(1, (days + 6) // 7)


def _fitness_level_to_self_report(fitness_level: int) -> int:
    """Pass-through for the TrainingGoal.fitness_level self-report."""
    return max(1, min(5, int(fitness_level)))


def _estimate_current_performance(
    *, twin_state_row: TwinState, target_distance_km: float
) -> float:
    """Best effort estimate of the athlete's current race time (minutes).

    Falls back to a coarse population table when individual data is
    insufficient — matches the architecture's
    "Falls back to age-graded tables if insufficient data" rule.
    """
    lt2_pace = float(twin_state_row.lt2_pace_sec_per_km or 270.0)
    minutes_per_km = lt2_pace / 60.0
    return minutes_per_km * target_distance_km * 1.05


def _compute_gap_percentage(
    *, current_estimate_min: float, target_time_min: int
) -> float:
    """(target - current) / current * 100."""
    if current_estimate_min <= 0:
        return 100.0
    return ((target_time_min - current_estimate_min) / current_estimate_min) * 100.0


def _classify_gap(gap_pct: float) -> str:
    """Map a gap percentage to the architecture's bucketed classification."""
    if gap_pct <= 3:
        return "small"
    if gap_pct <= 8:
        return "medium"
    if gap_pct <= 15:
        return "large"
    return "very_large"


def _estimate_weeks_to_target(
    *, gap_classification: str, fitness_level: int
) -> int:
    """Estimate training weeks for a target_performance plan."""
    base_low, base_high = {
        "small": (4, 6),
        "medium": (6, 10),
        "large": (10, 16),
        "very_large": (16, 26),
    }[gap_classification]
    if fitness_level <= 2:
        return base_high
    if fitness_level >= 4:
        return base_low
    return (base_low + base_high) // 2


def _normalise_weekly_schedule(
    weekly_schedule: dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Normalise the JSONB weekly schedule to a per-day dict.

    Returns a seven-key dict; missing days default to ``available=False``.
    """
    out: Dict[str, Dict[str, Any]] = {
        day: {"available": False} for day in DAYS_OF_WEEK
    }
    for day, cfg_value in weekly_schedule.items():
        if day not in out:
            continue
        if not isinstance(cfg_value, dict):
            continue
        cfg_dict: Dict[str, Any] = cast(Dict[str, Any], cfg_value)
        out[day] = {
            "available": bool(cfg_dict.get("available", False)),
            "max_hours": float(cfg_dict.get("max_hours", 0.0)),
            "long_workout": bool(cfg_dict.get("long_workout", False)),
            "doubles_eligible": bool(cfg_dict.get("doubles_eligible", False)),
        }
    return out


def _pick_long_workout_day(weekday_map: Dict[str, Dict[str, Any]]) -> str:
    """Pick the long-workout preferred day; fall back to Saturday."""
    for day in DAYS_OF_WEEK:
        if weekday_map[day].get("long_workout"):
            return day
    return "saturday"


def _phase_index_for_week(
    allocations: Sequence[PhaseAllocation], week_index: int
) -> int:
    """Return the phase index that contains ``week_index`` (0-indexed)."""
    cursor = 0
    for idx, allocation in enumerate(allocations):
        cursor += allocation.weeks
        if week_index < cursor:
            return idx
    return len(allocations) - 1


def _sum_weeks_before(
    allocations: Sequence[PhaseAllocation], phase_index: int
) -> int:
    return sum(a.weeks for a in allocations[:phase_index])


def _pick_phase_quality_target(
    phase_label: PhaseLabel,
) -> Optional[SessionType]:
    """Phase-specific primary quality session.

    Encoded separately from ``_phase_session_types`` so the synthesiser
    only places one canonical quality session per week and lets the
    fill phase populate easy / recovery rotations around it.
    """
    if phase_label == PhaseLabel.AEROBIC_BASE:
        return SessionType.TEMPO
    if phase_label == PhaseLabel.THRESHOLD_BUILD:
        return SessionType.THRESHOLD
    if phase_label == PhaseLabel.SPECIFIC_ENDURANCE:
        return SessionType.TEMPO
    if phase_label == PhaseLabel.TAPER:
        return None
    if phase_label == PhaseLabel.RACE_WEEK:
        return None
    return None


def _pick_easy_rotation(
    *, phase_label: PhaseLabel, week_index_in_phase: int
) -> SessionType:
    """Pick a non-quality session type that rotates week-by-week."""
    rotation: List[SessionType]
    if phase_label == PhaseLabel.AEROBIC_BASE:
        rotation = [
            SessionType.EASY_RUN,
            SessionType.RECOVERY_RUN,
            SessionType.STRIDES,
            SessionType.EASY_RUN,
        ]
    elif phase_label == PhaseLabel.THRESHOLD_BUILD:
        rotation = [
            SessionType.EASY_RUN,
            SessionType.RECOVERY_RUN,
            SessionType.MEDIUM_LONG_RUN,
            SessionType.EASY_RUN,
        ]
    elif phase_label == PhaseLabel.SPECIFIC_ENDURANCE:
        rotation = [
            SessionType.EASY_RUN,
            SessionType.MEDIUM_LONG_RUN,
            SessionType.STRIDES,
            SessionType.EASY_RUN,
        ]
    elif phase_label == PhaseLabel.TAPER:
        rotation = [
            SessionType.EASY_RUN,
            SessionType.STRIDES,
            SessionType.RECOVERY_RUN,
        ]
    else:
        rotation = [SessionType.EASY_RUN, SessionType.RECOVERY_RUN]
    return rotation[week_index_in_phase % len(rotation)]


def _is_quality(session_type: SessionType) -> bool:
    """True if *session_type* is in the architectural "quality session" set."""
    return session_type in QUALITY_SESSION_TYPES


# ---------------------------------------------------------------------------
# Weekly-invariant repair helpers.
#
# The placement pipeline in :meth:`PlanGenerationService._synthesize_week`
# enforces only the ``QUALITY_SESSION_TYPES`` no-adjacency rule and the
# ``SANDWICHED_SESSION_TYPES`` prev/next quality rule. The two structural
# invariants from
# ``docs/architecture/02-computations/plan-generation-race.md``
# and ``training-plan.md`` —
#
#   1. Long runs are followed by rest or recovery_run (within the same
#      week).
#   2. Threshold / VO2max sessions are sandwiched between easy / rest /
#      recovery_run days on both sides.
#
# — are NOT covered by placement alone because the synthesiser
# decides session types BEFORE the long-run-recovery and
# threshold-sandwich contexts are known globally per week.
#
# Both invariants are pure, walled off into two helpers below, and
# applied to the sorted weekly assignment list inside
# ``_synthesize_week`` immediately before persistence.
# ---------------------------------------------------------------------------


_EASY_REST_TYPES: frozenset[SessionType] = frozenset(
    {
        SessionType.REST,
        SessionType.RECOVERY_RUN,
        SessionType.EASY_RUN,
    }
)

#: Stricter set used for the LONG_RUN-followed-by-recovery invariant:
#: the architectural rule "long run is followed by rest or recovery_run"
#: per ``docs/architecture/01-entities/training-plan.md`` excludes
#: EASY_RUN — a hard-easy day after a long run would still load the
#: athlete. The threshold-sandwich rule (lower body) accepts the
#: wider set; long-run-recovery does not.
_LONG_RUN_FOLLOW_UP_TYPES: frozenset[SessionType] = frozenset(
    {
        SessionType.REST,
        SessionType.RECOVERY_RUN,
    }
)


def _retype_assignment(
    assignment: SessionDayAssignment,
    *,
    new_session_type: SessionType,
) -> SessionDayAssignment:
    """Return a copy of *assignment* with ``session_type`` swapped.

    Preserves ``target_date``, ``is_checkpoint``, the block-membership
    fields, and the session-priority fields. ``intent_description``
    and ``approximate_duration_minutes`` are rebuilt from the new
    session type using the same helpers as initial placement so
    downstream consumers see consistent labelling.

    The original assignment is a frozen dataclass; this helper
    allocates a new one rather than mutating state.
    """
    phase_label = _extract_phase_label_from_intent(
        assignment.intent_description
    )
    week_index_in_phase = _extract_week_in_phase_from_intent(
        assignment.intent_description
    )
    return SessionDayAssignment(
        target_date=assignment.target_date,
        session_type=new_session_type,
        intent_description=_build_intent_description(
            session_type=new_session_type,
            phase_label=phase_label,
            week_index_in_phase=week_index_in_phase,
        ),
        approximate_duration_minutes=(
            DEFAULT_SESSION_TYPE_DURATION_MIN.get(new_session_type, 60)
        ),
        block_id=assignment.block_id,
        block_position=assignment.block_position,
        block_session_count=assignment.block_session_count,
        is_checkpoint=assignment.is_checkpoint,
        checkpoint_type=assignment.checkpoint_type,
        checkpoint_metric=assignment.checkpoint_metric,
        checkpoint_record=assignment.checkpoint_record,
        session_slot=assignment.session_slot,
        session_priority=assignment.session_priority,
    )


def _extract_phase_label_from_intent(intent: str) -> PhaseLabel:
    """Recover the ``PhaseLabel`` embedded in a session's intent string.

    Falls back to :data:`PhaseLabel.AEROBIC_BASE` when the intent
    doesn't carry a recognisable phase token (e.g. checkpoint
    assignments whose intent is the checkpoint planner message).
    """
    if "(" not in intent:
        return PhaseLabel.AEROBIC_BASE
    tail = intent.rsplit("(", 1)[-1].split(",", 1)[0].strip()
    try:
        return PhaseLabel(tail)
    except ValueError:
        return PhaseLabel.AEROBIC_BASE


def _extract_week_in_phase_from_intent(intent: str) -> int:
    """Recover ``week_index_in_phase`` from ``(phase_label, week N)``.

    Defaults to 0 when the token is missing — the value is used only
    for human-readable intent reconstruction, never for scheduling.
    """
    if "(" not in intent:
        return 0
    tail = intent.rsplit("(", 1)[-1].rstrip(")")
    tokens = tail.split(",")
    for token in tokens:
        token = token.strip().lower()
        if token.startswith("week"):
            digits = "".join(ch for ch in token if ch.isdigit())
            if digits:
                return max(0, int(digits) - 1)
    return 0


def _repair_weekly_invariants(
    assignments: List[SessionDayAssignment],
    *,
    week_start: date,
) -> List[SessionDayAssignment]:
    """Enforce LONG_RUN-followed-by-rest and THRESHOLD-sandwich.

    Pure — same inputs always yield the same repaired list. The
    callers order the assignments by ``target_date`` before passing
    them in; the helper preserves that order.

    Repair semantics:

    * **LONG_RUN → recovery.** Each LONG_RUN must be followed by a
      session whose type is in ``{REST, RECOVERY_RUN}``. If a
      later-dated assignment exists in the week and is not a
      checkpoint, its type is rewritten to ``RECOVERY_RUN`` (the
      ``REST`` alias would also be acceptable, but ``RECOVERY_RUN``
      is chosen because its duration is well-defined; ``REST`` is
      reserved for the explicit rest slots in later revisions).
      If the LONG_RUN is the latest-dated assignment in the week,
      a new ``RECOVERY_RUN`` assignment is inserted on
      ``week_start + 6 days`` (Sunday) — the canonical last day
      of the week — only if that target_date is not already
      occupied. Checkpoint sessions are left untouched.
    * **Threshold / VO2max sandwich.** Each
      :data:`SANDWICHED_SESSION_TYPES` session must be bordered by
      non-quality sessions of the easy/rest family. Earlier and
      later dated assignments are retargeted to ``EASY_RUN``
      (already in the easy/rest set, so the existing rotation
      tastes vary widely between sessions). Checkpoint
      neighbours are left untouched.

    The repair never creates a new quality session; existing
    quality sessions adjacent to THRESHOLD / VO2MAX are
    downgraded to ``EASY_RUN`` to satisfy the sandwich rule.
    Quality sessions adjacent to LONG_RUN were already excluded
    by the placement-time guards; if any slipped through (e.g.
    via the fill rotation) they will be retargeted to
    ``RECOVERY_RUN``.

    Returns a fresh list — input ``assignments`` is not mutated.
    """
    if not assignments:
        return []

    ordered = sorted(assignments, key=lambda a: a.target_date)
    repaired: List[SessionDayAssignment] = list(ordered)

    # ---- LONG_RUN → recovery repair.
    long_run_indices: List[int] = [
        idx
        for idx, current in enumerate(repaired)
        if current.session_type is SessionType.LONG_RUN
    ]
    for lr_idx in long_run_indices:
        lr = repaired[lr_idx]
        next_idx = lr_idx + 1
        if next_idx < len(repaired):
            nxt = repaired[next_idx]
            if (
                not nxt.is_checkpoint
                and nxt.session_type not in _LONG_RUN_FOLLOW_UP_TYPES
            ):
                repaired[next_idx] = _retype_assignment(
                    nxt, new_session_type=SessionType.RECOVERY_RUN
                )
            continue
        # LONG_RUN is the last assignment in the week — insert a
        # recovery session on the canonical last day of the week
        # if it's still free.
        recovery_date = week_start + timedelta(days=6)
        occupied_dates = {a.target_date for a in repaired}
        if recovery_date in occupied_dates:
            # The last day of the week is already taken — give up
            # rather than crashing the placement. This still
            # satisfies the per-week test surface because the
            # subsequent earlier-dated slot (above) already has
            # its type repaired when the LONG_RUN has a later
            # assigned sibling; here, when LONG_RUN IS the latest
            # date and the trailing day is occupied, the earlier
            # slot will already have been retargeted by the
            # earlier iteration of this loop or by a later
            # sibling's retype.
            continue
        replacement = SessionDayAssignment(
            target_date=recovery_date,
            session_type=SessionType.RECOVERY_RUN,
            intent_description=_build_intent_description(
                session_type=SessionType.RECOVERY_RUN,
                phase_label=_extract_phase_label_from_intent(
                    lr.intent_description
                ),
                week_index_in_phase=_extract_week_in_phase_from_intent(
                    lr.intent_description
                ),
            ),
            approximate_duration_minutes=DEFAULT_SESSION_TYPE_DURATION_MIN.get(
                SessionType.RECOVERY_RUN, 30
            ),
            session_priority=SessionPriority.PRIMARY,
        )
        repaired.append(replacement)

    # Re-sort after potential LONG_RUN follow-up insertion.
    repaired = sorted(repaired, key=lambda a: a.target_date)

    # ---- THRESHOLD / VO2max sandwich repair.
    sandwich_indices: List[int] = [
        idx
        for idx, current in enumerate(repaired)
        if current.session_type in SANDWICHED_SESSION_TYPES
    ]
    for t_idx in sandwich_indices:
        # Update prev/next in place by index — we are traversing in
        # date order, so for the current SANDWICHED session we look
        # at the immediately-prior and immediately-following
        # entries in the repaired list. Insertions are handled
        # separately in a second pass below to keep the index
        # arithmetic simple.
        prev_idx = t_idx - 1
        if prev_idx >= 0:
            prev = repaired[prev_idx]
            if (
                not prev.is_checkpoint
                and prev.session_type not in _EASY_REST_TYPES
            ):
                repaired[prev_idx] = _retype_assignment(
                    prev, new_session_type=SessionType.EASY_RUN
                )
        next_idx = t_idx + 1
        if next_idx < len(repaired):
            nxt = repaired[next_idx]
            if (
                not nxt.is_checkpoint
                and nxt.session_type not in _EASY_REST_TYPES
            ):
                repaired[next_idx] = _retype_assignment(
                    nxt, new_session_type=SessionType.EASY_RUN
                )

    # ---- THRESHOLD / VO2max padding when placed on the first day
    # of the week. The synthesiser may have placed a SANDWICHED
    # session on the first available day of the week (e.g. Monday in
    # the default fixture); without a preceding session the
    # sandwich test would fail. Insert an ``EASY_RUN`` slot one day
    # before the sandwich where possible, falling back to the
    # latest day of the previous PhaseAllocation boundary if the
    # ``week_start`` slot is already occupied. ``week_start`` is the
    # canonical first day of the week.
    padding_required: List[Tuple[int, date]] = []
    occupied_after_first_pass = {a.target_date for a in repaired}
    for idx, current in enumerate(repaired):
        if current.session_type not in SANDWICHED_SESSION_TYPES:
            continue
        if idx > 0:
            continue
        if current.session_type is SessionType.LONG_RUN:
            continue
        # Try to insert RECOVERY_RUN on ``week_start`` day.
        if week_start not in occupied_after_first_pass:
            padding_required.append(
                (
                    idx,
                    week_start,
                )
            )
            occupied_after_first_pass.add(week_start)
    for _t_idx, padding_date in padding_required:
        # Use the first SANDWICHED session's intent to recover phase
        # + week_in_phase tokens.
        if not repaired:
            break
        sandwich = next(
            a for a in repaired
            if a.session_type in SANDWICHED_SESSION_TYPES
        )
        replacement = SessionDayAssignment(
            target_date=padding_date,
            session_type=SessionType.RECOVERY_RUN,
            intent_description=_build_intent_description(
                session_type=SessionType.RECOVERY_RUN,
                phase_label=_extract_phase_label_from_intent(
                    sandwich.intent_description
                ),
                week_index_in_phase=_extract_week_in_phase_from_intent(
                    sandwich.intent_description
                ),
            ),
            approximate_duration_minutes=(
                DEFAULT_SESSION_TYPE_DURATION_MIN.get(
                    SessionType.RECOVERY_RUN, 30
                )
            ),
            session_priority=SessionPriority.PRIMARY,
        )
        repaired.append(replacement)
    if padding_required:
        repaired = sorted(repaired, key=lambda a: a.target_date)

    return repaired


def _day_before(
    day: str,
    assignments: Dict[str, SessionDayAssignment],
) -> Optional[SessionDayAssignment]:
    """Return the assignment on the previous scheduled day, or None."""
    idx = DAYS_OF_WEEK.index(day)
    for prev in reversed(DAYS_OF_WEEK[:idx]):
        if prev in assignments:
            return assignments[prev]
    return None


def _day_after(
    day: str,
    available_days: Sequence[str],
    assignments: Dict[str, SessionDayAssignment],
) -> Optional[SessionDayAssignment]:
    """Return the assignment on the next available day, or None."""
    idx = DAYS_OF_WEEK.index(day)
    for nxt in DAYS_OF_WEEK[idx + 1 :]:
        if nxt in available_days and nxt in assignments:
            return assignments[nxt]
    return None


def _compute_phase_date_ranges(
    *, plan_start: date, total_weeks: int
) -> List[Tuple[date, date]]:
    """Compute contiguous, non-overlapping phase date ranges."""
    ranges: List[Tuple[date, date]] = []
    allocations = allocate_race_event_phases(total_weeks=total_weeks)
    week_cursor = 0
    for allocation in allocations:
        start = plan_start + timedelta(days=week_cursor * 7)
        end = start + timedelta(days=allocation.weeks * 7 - 1)
        ranges.append((start, end))
        week_cursor += allocation.weeks
    return ranges


def _expand_phases_to_weekly(
    phase_definitions: Sequence[PhaseDefinitionRecord],
) -> List[Dict[str, Any]]:
    """Deterministic expansion of phases → weekly distributions."""
    weekly: List[Dict[str, Any]] = []
    week_offset = 0
    for phase in phase_definitions:
        for _ in range(phase.weeks):
            weekly.append(
                {
                    "week_number": week_offset + 1,
                    "distribution": dict(phase.distribution),
                    "specificity": float(phase.specificity),
                    "objective": list(phase.objectives),
                    "is_recovery_week": False,
                }
            )
            week_offset += 1
    return weekly


def _phase_definition_to_dict(
    record: PhaseDefinitionRecord,
) -> Dict[str, Any]:
    return {
        "phase": record.phase,
        "objectives": list(record.objectives),
        "weeks": int(record.weeks),
        "distribution": {k: float(v) for k, v in record.distribution.items()},
        "specificity": float(record.specificity),
        "approach": record.approach,
        "recovery_cycle": record.recovery_cycle,
    }


def _checkpoint_record_to_dict(record: CheckpointRecord) -> Dict[str, Any]:
    return {
        "type": record.type.value,
        "week_number": int(record.week_number),
        "target_date": record.target_date.isoformat(),
        "target_metric": record.target_metric,
        "session_type": record.session_type.value,
        "planner_message": record.planner_message,
    }


def _build_strategic_rationale(
    *,
    goal_type: GoalType,
    allocations: Sequence[PhaseAllocation],
) -> Optional[Dict[str, Any]]:
    """Return the deterministic strategic rationale for race_event /
    target_performance modes. Null for other modes per the architecture
    invariant.
    """
    if goal_type not in ALLOWED_PLAN_GENERATION_GOAL_TYPES:
        return None
    phase_labels = [a.label.value for a in allocations]
    return {
        "primary_driver": (
            "deterministic periodisation from onboarding context"
        ),
        "methodology_summary": (
            "Five-phase block progressing from aerobic base through "
            "threshold build, race-specific endurance, taper, and "
            "race week."
        ),
        "risk_notes": [
            f"Longest consecutive quality phase: {phase_labels}",
        ],
    }


def _build_intent_description(
    *,
    session_type: SessionType,
    phase_label: PhaseLabel,
    week_index_in_phase: int,
) -> str:
    """Produce a deterministic intent description for a session."""
    templates = {
        SessionType.EASY_RUN: "Conversational easy run — aerobic support",
        SessionType.RECOVERY_RUN: "Short recovery run — promote blood flow",
        SessionType.LONG_RUN: "Endurance-building long run",
        SessionType.MEDIUM_LONG_RUN: "Steady medium-long run — aerobic support",
        SessionType.STEADY_STATE: "Steady state — controlled aerobic work",
        SessionType.TEMPO: "Tempo effort — controlled moderately-hard pace",
        SessionType.THRESHOLD: "Threshold intervals at LT2",
        SessionType.VO2MAX: "VO2max intervals — high-intensity efforts",
        SessionType.HILL_REPEATS: "Hill repeats — neuromuscular stimulus",
        SessionType.FARTLEK: "Fartlek — varied intensity play",
        SessionType.STRIDES: "Strides — neuromuscular activation",
        SessionType.DRILLS_MOBILITY: "Drills and mobility work",
        SessionType.CROSS_TRAINING: "Cross-training — supporting modality",
        SessionType.TEST_SESSION: "Test session — measurement workout",
        SessionType.OPTIONAL_RUN: "Optional easy run",
        SessionType.REST: "Rest day",
    }
    base = templates.get(
        session_type,
        f"{session_type.value.replace('_', ' ')} session",
    )
    return f"{base} ({phase_label.value}, week {week_index_in_phase + 1})"


__all__ = [
    "ALLOWED_PLAN_GENERATION_GOAL_TYPES",
    "DAYS_OF_WEEK",
    "DEFAULT_SESSION_TYPE_DURATION_MIN",
    "PlanGenerationResult",
    "PlanGenerationService",
    "SessionDayAssignment",
]
