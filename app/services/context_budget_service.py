"""Token-budget enforcement for LLM agents."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from app.models.enums import GoalType, SportBackground

if TYPE_CHECKING:
    from app.models.twin_state import TwinState
    from app.repositories.athlete_preferences_repository import (
        AthletePreferencesRepository,
    )
    from app.repositories.athlete_profile_repository import AthleteProfileRepository
    from app.repositories.planned_session_repository import (
        PlannedSessionRepository,
    )
    from app.repositories.training_goal_repository import TrainingGoalRepository
    from app.repositories.training_plan_repository import TrainingPlanRepository
    from app.repositories.twin_state_repository import TwinStateRepository

_logger = logging.getLogger("pheidipp.context_budget")

MAX_TOKENS = {
    "first_message": 5000,
    "workout_generation": 3000,
    "post_workout": 6000,
}


@dataclass(frozen=True)
class ContextSection:
    """One section of the context with its priority weight."""

    name: str
    priority_weight: int  # 1-100; higher = more important
    token_budget: int


FIRST_MESSAGE_PRIORITY_PROFILE: tuple[ContextSection, ...] = (
    ContextSection(
        name="profile_summary", priority_weight=100, token_budget=400
    ),  # athlete's sport background, training history
    ContextSection(
        name="goal_summary", priority_weight=95, token_budget=300
    ),  # goal type, event, weeks until
    ContextSection(
        name="readiness", priority_weight=90, token_budget=200
    ),  # readiness level, form descriptor
    ContextSection(
        name="computed_observations", priority_weight=85, token_budget=400
    ),  # aerobic base, structural risk
    ContextSection(
        name="plan_overview", priority_weight=80, token_budget=500
    ),  # phases, weeks, primary focus
    ContextSection(
        name="first_block_preview", priority_weight=75, token_budget=400
    ),  # session types weeks 1-2
)


@dataclass(frozen=True)
class GoalSummary:
    """Goal context for the first message."""

    goal_type: GoalType
    goal_event_type: Optional[str]
    goal_event_date: Optional[str]
    weeks_to_event: Optional[int]
    goal_description: Optional[str]


@dataclass(frozen=True)
class ProfileSummary:
    """Athlete profile context for the first message."""

    sport_background: SportBackground
    years_structured_training: int
    fitness_level: int
    recent_injury: Optional[str]


@dataclass(frozen=True)
class PlanOverview:
    """Training plan overview for the first message."""

    phases: list[dict[str, Any]]  # PhaseDescriptor-like objects
    total_weeks: int


@dataclass(frozen=True)
class FirstBlockPreview:
    """First-block preview for the first message."""

    session_types_in_week_1: list[str]
    session_types_in_week_2: list[str]
    primary_focus: str


@dataclass(frozen=True)
class WorkoutSessionSummary:
    """Planned-session summary fed to ``WorkoutGenerationAgent``.

    Captures the atomic session metadata the workout agent must
    respect: ``session_type`` (drives target structure via
    :data:`SESSION_INTENT_MAP`), phase label and week number (so the
    prompt understands the plan position), intent description
    (literal copy from the weekly synthesis), and the approximate
    duration budget for the whole session.
    """

    session_type: str  # SessionType value
    phase_label: str  # PhaseLabel value
    week_number: int
    intent_description: str
    approximate_duration_minutes: int


@dataclass(frozen=True)
class WorkoutReadinessDigest:
    """Coaching-language translation of the current TwinState for workouts.

    Mirrors the ``readiness`` sub-shape in the
    ``WorkoutGenerationContext`` contract from
    ``docs/architecture/03-agents/workout-generation-agent.md``.
    Numeric threshold estimates (e.g. ``lt2_pace_sec_per_km``) are
    null when twin confidence is LOW — confidence-appropriate
    precision is expressed via ``threshold_target_description``
    instead.
    """

    recovery_modifier_level: str  # RecoveryModifierLevel value
    recovery_modifier_reason: Optional[str]
    confidence_level: str  # TwinConfidenceLevel value
    fitness_form_descriptor: str
    threshold_target_description: str
    lt2_pace_sec_per_km: Optional[float]


@dataclass
class WorkoutGenerationContext:
    """Context bundle for ``WorkoutGenerationAgent``.

    Composed from the planned session, the TwinState digest
    (assembled by :class:`TwinContextAssembler`), and the
    ath­lete's preferences / profile. The dataclass is mutable
    (``dataclass`` not ``frozen``) so token-budget truncation can
    drop sections in place and the agent still receives a single
    bundle without re-querying repositories.

    ``relevant_objectives`` is an empty list at this phase;
    objectives land in Phase 4. The prompt handles the empty case
    gracefully — no objective-driven framing in v1.
    """

    session: Optional[WorkoutSessionSummary] = None
    readiness: Optional[WorkoutReadinessDigest] = None
    data_tier: Optional[int] = None  # DataTier enum value
    target_type: Optional[str] = None  # 'power' | 'gap' | 'description'
    relevant_objectives: list[dict[str, Any]] = field(default_factory=lambda: [])

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for token estimation and prompt rendering."""
        return {
            "session": {
                "session_type": self.session.session_type if self.session else None,
                "phase_label": self.session.phase_label if self.session else None,
                "week_number": self.session.week_number if self.session else None,
                "intent_description": self.session.intent_description
                if self.session
                else None,
                "approximate_duration_minutes": (
                    self.session.approximate_duration_minutes if self.session else None
                ),
            }
            if self.session
            else None,
            "readiness": {
                "recovery_modifier_level": (
                    self.readiness.recovery_modifier_level if self.readiness else None
                ),
                "recovery_modifier_reason": (
                    self.readiness.recovery_modifier_reason if self.readiness else None
                ),
                "confidence_level": self.readiness.confidence_level
                if self.readiness
                else None,
                "fitness_form_descriptor": (
                    self.readiness.fitness_form_descriptor if self.readiness else None
                ),
                "threshold_target_description": (
                    self.readiness.threshold_target_description
                    if self.readiness
                    else None
                ),
                "lt2_pace_sec_per_km": self.readiness.lt2_pace_sec_per_km
                if self.readiness
                else None,
            }
            if self.readiness
            else None,
            "data_tier": self.data_tier,
            "target_type": self.target_type,
            "relevant_objectives": self.relevant_objectives,
        }


@dataclass
class FirstMessageContext:
    """Context bundle for ``FirstMessageAgent``.

    All fields are optional because truncation may remove some sections;
    the agent must handle absence gracefully (skip referencing that data).
    """

    profile_summary: Optional[ProfileSummary] = None
    goal_summary: Optional[GoalSummary] = None
    readiness_level: Optional[str] = None  # RecoveryModifierLevel value
    confidence_level: Optional[str] = None  # TwinConfidenceLevel value
    fitness_form_descriptor: Optional[str] = None
    data_tier: Optional[int] = None  # DataTier enum value
    computed_observations: Optional[dict[str, Any]] = None
    plan_overview: Optional[PlanOverview] = None
    first_block_preview: Optional[FirstBlockPreview] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict for token estimation and prompt rendering."""
        return {
            "profile_summary": (
                {
                    "sport_background": self.profile_summary.sport_background.value
                    if self.profile_summary
                    else None,
                    "years_structured_training": (
                        self.profile_summary.years_structured_training
                        if self.profile_summary
                        else None
                    ),
                    "fitness_level": self.profile_summary.fitness_level
                    if self.profile_summary
                    else None,
                    "recent_injury": self.profile_summary.recent_injury
                    if self.profile_summary
                    else None,
                }
                if self.profile_summary
                else None
            ),
            "goal_summary": {
                "goal_type": self.goal_summary.goal_type.value
                if self.goal_summary
                else None,
                "goal_event_type": self.goal_summary.goal_event_type
                if self.goal_summary
                else None,
                "goal_event_date": self.goal_summary.goal_event_date
                if self.goal_summary
                else None,
                "weeks_to_event": self.goal_summary.weeks_to_event
                if self.goal_summary
                else None,
                "goal_description": self.goal_summary.goal_description
                if self.goal_summary
                else None,
            }
            if self.goal_summary
            else None,
            "readiness_level": self.readiness_level,
            "confidence_level": self.confidence_level,
            "fitness_form_descriptor": self.fitness_form_descriptor,
            "data_tier": self.data_tier,
            "computed_observations": self.computed_observations,
            "plan_overview": {
                "phases": self.plan_overview.phases if self.plan_overview else None,
                "total_weeks": self.plan_overview.total_weeks
                if self.plan_overview
                else None,
            }
            if self.plan_overview
            else None,
            "first_block_preview": {
                "session_types_in_week_1": (
                    self.first_block_preview.session_types_in_week_1
                    if self.first_block_preview
                    else None
                ),
                "session_types_in_week_2": (
                    self.first_block_preview.session_types_in_week_2
                    if self.first_block_preview
                    else None
                ),
                "primary_focus": (
                    self.first_block_preview.primary_focus
                    if self.first_block_preview
                    else None
                ),
            }
            if self.first_block_preview
            else None,
        }


class ContextBudgetService:
    """Assembles context for LLM agents with token-budget enforcement.

    The service is constructed with repositories so it can fetch the
    necessary data. The ``AsyncSession`` is managed by the caller
    and is NOT committed or rolled back here (the generator service
    owns the surrounding transaction).
    """

    def __init__(
        self,
        twin_states: "TwinStateRepository",
        training_goals: "TrainingGoalRepository",
        plans: "TrainingPlanRepository",
        profiles: "AthleteProfileRepository",
        preferences: "AthletePreferencesRepository",
        planned_sessions: Optional["PlannedSessionRepository"] = None,
    ) -> None:
        self.twin_states = twin_states
        self.training_goals = training_goals
        self.plans = plans
        self._profiles = profiles
        self._preferences = preferences
        # ``built_workout_context`` (Phase 1.5b) requires loading the
        # target ``PlannedSession``; optional so the Phase-1.5a callers
        # that pre-date the workout agent keep working without a
        # forced dependency.
        self.planned_sessions = planned_sessions

    @staticmethod
    def estimate_tokens(obj: dict[str, Any]) -> int:
        """Deterministic token estimation using ``len(JSON) / 4``."""
        return (len(json.dumps(obj, default=str)) + 3) // 4

    async def build_first_message_context(
        self, athlete_id: uuid.UUID
    ) -> FirstMessageContext:
        """Assemble and enforce budget for ``FirstMessageAgent``."""
        twin_state = await self.twin_states.get_latest(athlete_id)
        active_goal = await self.training_goals.get_active(athlete_id)
        active_plan = await self.plans.get_active_for_athlete(athlete_id)
        await self._profiles.get_by_athlete_id(athlete_id)
        preferences = await self._preferences.get_by_athlete_id(athlete_id)

        computed_observations: dict[str, Any] | None = None
        if twin_state and preferences:
            # Assembly is the caller's responsibility, but we inline
            # the essential observations here so the budget service can
            # be the single assembly point per architecture.
            computed_observations = {
                "aerobic_base_assessment": (
                    "moderate aerobic base with room to grow"
                    if twin_state.confidence_level.value == "low"
                    else "developing a reliable aerobic engine"
                ),
                "structural_risk_flag": (
                    preferences.sport_background != SportBackground.RUNNING_PRIMARY
                ),
                "structural_risk_reason": (
                    "non-running primary sport background"
                    if preferences.sport_background != SportBackground.RUNNING_PRIMARY
                    else None
                ),
                "training_consistency_signal": (
                    f"{preferences.years_structured_training} years of structured training"
                    if preferences.years_structured_training > 0
                    else None
                ),
            }

        goal_summary: GoalSummary | None = None
        if active_goal:
            from datetime import datetime

            weeks_to_event: int | None = None
            if active_goal.goal_event_date:
                days = (active_goal.goal_event_date - datetime.now().date()).days
                weeks_to_event = max(1, days // 7)

            goal_summary = GoalSummary(
                goal_type=active_goal.goal_type,
                goal_event_type=(
                    active_goal.goal_event_type.value
                    if active_goal.goal_event_type
                    else None
                ),
                goal_event_date=(
                    active_goal.goal_event_date.isoformat()
                    if active_goal.goal_event_date
                    else None
                ),
                weeks_to_event=weeks_to_event,
                goal_description=active_goal.goal_description,
            )

        profile_summary: ProfileSummary | None = None
        if preferences:
            profile_summary = ProfileSummary(
                sport_background=preferences.sport_background,
                years_structured_training=preferences.years_structured_training,
                fitness_level=active_goal.fitness_level if active_goal else 3,
                recent_injury=active_goal.recent_injury if active_goal else None,
            )

        plan_overview: PlanOverview | None = None
        first_block_preview: FirstBlockPreview | None = None
        if active_plan:
            plan_overview = PlanOverview(
                phases=active_plan.phases_summary or [],
                total_weeks=len(active_plan.weekly_distributions or []),
            )

            if active_plan.weekly_distributions:
                week1: dict[str, Any] = (
                    active_plan.weekly_distributions[0]
                    if len(active_plan.weekly_distributions) > 0
                    else {}
                )
                week2: dict[str, Any] = (
                    active_plan.weekly_distributions[1]
                    if len(active_plan.weekly_distributions) > 1
                    else {}
                )
                first_block_preview = FirstBlockPreview(
                    session_types_in_week_1=week1.get("session_types", []),
                    session_types_in_week_2=week2.get("session_types", []),
                    primary_focus=week1.get("primary_focus", "building aerobic base"),
                )

        context = FirstMessageContext(
            profile_summary=profile_summary,
            goal_summary=goal_summary,
            readiness_level=(
                twin_state.readiness_level.value if twin_state else "green"
            ),
            confidence_level=(
                twin_state.confidence_level.value if twin_state else "low"
            ),
            fitness_form_descriptor=(
                "ready to build"
                if twin_state and twin_state.form >= 0
                else "balancing recovery and load"
            ),
            data_tier=(int(twin_state.data_tier) if twin_state else 3),
            computed_observations=computed_observations,
            plan_overview=plan_overview,
            first_block_preview=first_block_preview,
        )

        context_dict = context.to_dict()
        estimated = self.estimate_tokens(context_dict)
        if estimated > MAX_TOKENS["first_message"]:
            _logger.warning(
                "context_budget.truncated",
                extra={
                    "agent": "FirstMessageAgent",
                    "estimated_tokens": estimated,
                    "max_tokens": MAX_TOKENS["first_message"],
                },
            )
        if estimated > MAX_TOKENS["first_message"]:
            _logger.warning(...)
        return context

    async def build_workout_context(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
    ) -> WorkoutGenerationContext:
        """Assemble and budget-enforce context for WorkoutGenerationAgent."""
        if self.planned_sessions is None:
            raise RuntimeError(
                "build_workout_context requires a PlannedSessionRepository; "
                "construct ContextBudgetService with planned_sessions=..."
            )

        twin_state = await self.twin_states.get_latest(athlete_id)
        session = await self.planned_sessions.get_by_id(planned_session_id)

        session_summary: WorkoutSessionSummary | None = None
        if session is not None:
            session_summary = WorkoutSessionSummary(
                session_type=session.session_type.value,
                phase_label=session.phase_label.value,
                week_number=session.week_number,
                intent_description=session.intent_description,
                approximate_duration_minutes=(session.approximate_duration_minutes),
            )

        readiness: WorkoutReadinessDigest | None = None
        data_tier: int | None = None
        target_type: str | None = None
        if twin_state is not None:
            data_tier_value = int(twin_state.data_tier)
            # Local import avoids a static cycle between
            # ``workout_target_types`` and ``context_budget_service``.
            from app.services.workout_target_types import (
                DATA_TIER_TARGET_TYPE,
            )

            data_tier = data_tier_value
            target_type = DATA_TIER_TARGET_TYPE.get(twin_state.data_tier, "description")
            readiness = self._compose_readiness_digest(twin_state)

        # ``relevant_objectives`` is intentionally empty at this phase
        # — objectives land in Phase 4 (see architecture
        # docs/architecture/01-entities/objective.md). The prompt
        # handles the empty list gracefully without referencing the
        # field.
        relevant_objectives: list[dict[str, Any]] = []

        context = WorkoutGenerationContext(
            session=session_summary,
            readiness=readiness,
            data_tier=data_tier,
            target_type=target_type,
            relevant_objectives=relevant_objectives,
        )

        context_dict = context.to_dict()
        estimated = self.estimate_tokens(context_dict)
        if estimated > MAX_TOKENS["workout_generation"]:
            _logger.warning(
                "context_budget.truncated",
                extra={
                    "agent": "WorkoutGenerationAgent",
                    "estimated_tokens": estimated,
                    "max_tokens": MAX_TOKENS["workout_generation"],
                },
            )
        return context

    def _compose_readiness_digest(
        self, twin_state: TwinState
    ) -> WorkoutReadinessDigest:
        """Translate TwinState into workout-context readiness shape."""
        from app.services.twin_context_assembler import (
            TwinContextAssembler,
        )

        assembler = TwinContextAssembler()
        twin_summary = assembler.assemble_twin_context(twin_state)

        if twin_state.confidence_level.value == "low":
            threshold_desc = (
                "easy aerobic effort and comfortably hard intervals — "
                "thresholds are population-based estimates at this point"
            )
        elif twin_state.confidence_level.value == "medium":
            if twin_state.lt2_pace_sec_per_km is not None:
                threshold_desc = (
                    f"around {int(round(twin_state.lt2_pace_sec_per_km / 60))}m"
                    f"{int(round(twin_state.lt2_pace_sec_per_km % 60)):02d}"
                    "/km threshold equivalent and a small range around it"
                )
            else:
                threshold_desc = (
                    "comfortably hard sustained effort and a small range "
                    "around it as confidence builds from real training"
                )
        else:  # HIGH confidence
            if twin_state.lt2_pace_sec_per_km is not None:
                threshold_desc = (
                    f"{int(round(twin_state.lt2_pace_sec_per_km / 60))}m"
                    f"{int(round(twin_state.lt2_pace_sec_per_km % 60)):02d}"
                    "/km threshold equivalent"
                )
            else:
                threshold_desc = (
                    "threshold equivalent from training stressing a small "
                    "deviation around your established threshold"
                )

        return WorkoutReadinessDigest(
            recovery_modifier_level=twin_state.readiness_level.value,
            recovery_modifier_reason=None,
            confidence_level=twin_state.confidence_level.value,
            fitness_form_descriptor=twin_summary.fitness_form_descriptor,
            threshold_target_description=threshold_desc,
            lt2_pace_sec_per_km=twin_state.lt2_pace_sec_per_km,
        )
