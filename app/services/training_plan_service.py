import logging
import uuid
from datetime import date, timedelta
from typing import Optional

from pydantic import ValidationError

from app.core.unit_of_work import UnitOfWork
from app.models.enums import (
    SessionType,
    PhysiologicalIntent,
    TrainingPhase,
    TrainingPlanStatus,
    ConfidenceLevel,
)
from app.models.training_plan import TrainingPlan
from app.models.planned_session import PlannedSession
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.planned_session_repository import PlannedSessionRepository
from app.schemas.plan_generation import (
    PhaseArc,
    PlanBlueprint,
    MethodologyProfile,
    ValidationResult,
)
from app.schemas.training_plan import TrainingPlanResponse, TrainingPlanBase, PlannedSessionBase
from app.services.phase_arc_computer import PhaseArcComputer, PHASE_ARC_VERSION
from app.services.plan_constraint_validator import PlanConstraintValidator, VALIDATOR_VERSION
from app.services.plan_generation_brief_builder import PlanGenerationBriefBuilder
from app.services.methodology_profile_builder import MethodologyProfileBuilder
from app.services.plan_constraint_validator import PlanConstraintValidator
from app.services.plan_repair_engine import PlanRepairEngine

logger = logging.getLogger(__name__)

SESSION_TYPE_TO_DOMINANT_INTENT: dict[SessionType, PhysiologicalIntent] = {
    SessionType.REST: PhysiologicalIntent.RECOVERY_SUPPORT,
    SessionType.RECOVERY_RUN: PhysiologicalIntent.RECOVERY_SUPPORT,
    SessionType.EASY_RUN: PhysiologicalIntent.LOW_AEROBIC,
    SessionType.LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.MEDIUM_LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.STEADY_STATE: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.TEMPO: PhysiologicalIntent.THRESHOLD,
    SessionType.THRESHOLD: PhysiologicalIntent.THRESHOLD,
    SessionType.VO2MAX: PhysiologicalIntent.VO2MAX,
    SessionType.HILL_REPEATS: PhysiologicalIntent.VO2MAX,
    SessionType.FARTLEK: PhysiologicalIntent.VO2MAX,
    SessionType.RACE_SPECIFIC: PhysiologicalIntent.RACE_SPECIFIC,
    SessionType.STRIDES: PhysiologicalIntent.NEUROMUSCULAR,
    SessionType.DRILLS_MOBILITY: PhysiologicalIntent.NEUROMUSCULAR,
    SessionType.CROSS_TRAINING: PhysiologicalIntent.LOW_AEROBIC,
    SessionType.TEST_SESSION: PhysiologicalIntent.CALIBRATION,
    SessionType.OPTIONAL_RUN: PhysiologicalIntent.RECOVERY_SUPPORT,
}

# Validate that all session types are mapped
for st in SessionType:
    if st not in SESSION_TYPE_TO_DOMINANT_INTENT:
        raise KeyError(f"SessionType '{st}' is not mapped to a PhysiologicalIntent")


class TrainingPlanService:
    def __init__(
        self,
        training_plan_repo: TrainingPlanRepository,
        planned_session_repo: PlannedSessionRepository,
        phase_arc_computer: PhaseArcComputer,
        brief_builder: PlanGenerationBriefBuilder,
        agent,  # PlanGenerationAgent
        validator: PlanConstraintValidator,
        repair_engine: PlanRepairEngine,
        methodology_profile_builder: MethodologyProfileBuilder,
    ):
        self.training_plan_repo = training_plan_repo
        self.planned_session_repo = planned_session_repo
        self.phase_arc_computer = phase_arc_computer
        self.brief_builder = brief_builder
        self.agent = agent
        self.validator = validator
        self.repair_engine = repair_engine
        self.methodology_profile_builder = methodology_profile_builder

    async def generate_plan(
        self,
        athlete_id: uuid.UUID,
        uow: UnitOfWork,
    ) -> TrainingPlanResponse:
        athlete = await uow.athletes.get_by_id(athlete_id)
        if athlete is None:
            raise ValueError(f"Athlete {athlete_id} not found")

        preferences = await uow.preferences.get_by_athlete(athlete_id)
        if preferences is None:
            raise ValueError(f"AthletePreferences for athlete {athlete_id} not found")

        training_block = await uow.blocks.get_active_by_athlete(athlete_id)
        if training_block is None:
            raise ValueError(f"Active TrainingBlock for athlete {athlete_id} not found")

        twin_state = await uow.twin_states.get_by_athlete_id(athlete_id)
        if twin_state is None:
            raise ValueError(f"TwinState for athlete {athlete_id} not found")

        # Compute phase arc
        phase_arc = self.phase_arc_computer.compute(
            training_block, twin_state, preferences
        )

        # Build methodology profile
        available_days = self._count_available_days(preferences)
        methodology_profile = self.methodology_profile_builder.build(
            event_type=training_block.goal_event_type,
            weeks_to_goal=phase_arc.total_weeks,
            training_age=preferences.years_structured_training,
            available_days=available_days,
            structural_capacity_score=twin_state.structural_capacity_score,
            adaptation_confidence_level=twin_state.confidence_level or ConfidenceLevel.LOW,
            consistency_score=0.7,  # Placeholder — could be derived from history
        )

        # Build brief and call agent
        brief = self.brief_builder.build(
            athlete=athlete,
            preferences=preferences,
            training_block=training_block,
            twin_state=twin_state,
            phase_arc=phase_arc,
            methodology_profile=methodology_profile,
        )

        blueprint_dict, metadata = await self.agent.generate(athlete_id, brief)

        # Validate blueprint
        try:
            blueprint = PlanBlueprint.model_validate(blueprint_dict)
        except ValidationError as e:
            raise ValueError(f"Agent returned invalid blueprint: {e}")

        available_days_map = self.brief_builder._build_available_days(preferences)
        validation_result = self.validator.validate(blueprint, available_days_map, phase_arc)

        # Repair if invalid
        if not validation_result.is_valid:
            blueprint = self.repair_engine.repair(blueprint, validation_result, available_days_map)
            # Re-validate
            validation_result = self.validator.validate(blueprint, available_days_map, phase_arc)
            if not validation_result.is_valid:
                violations = [v.model_dump() for v in validation_result.violations]
                raise ValueError(f"Plan validation failed after repair: {violations}")

        # Instantiate plan
        plan = await self._instantiate_plan(
            athlete_id=athlete_id,
            training_block=training_block,
            blueprint=blueprint,
            metadata=metadata,
            methodology_profile=methodology_profile,
            uow=uow,
        )

        return self._build_response(plan)

    async def _instantiate_plan(
        self,
        athlete_id: uuid.UUID,
        training_block,
        blueprint: PlanBlueprint,
        metadata: dict,
        methodology_profile: MethodologyProfile,
        uow: UnitOfWork,
    ) -> TrainingPlan:
        from datetime import datetime, timezone

        generation_metadata = {
            **metadata,
            "methodology_profile": methodology_profile.model_dump(),
            "phase_arc_version": PHASE_ARC_VERSION,
            "validator_version": VALIDATOR_VERSION,
        }

        plan = TrainingPlan(
            athlete_id=athlete_id,
            training_block_id=training_block.id,
            status=TrainingPlanStatus.ACTIVE,
            generation_metadata=generation_metadata,
            plan_rationale=blueprint.plan_rationale,
        )
        self.training_plan_repo.session.add(plan)
        await self.training_plan_repo.session.flush()
        await self.training_plan_repo.session.refresh(plan)

        # Map sessions: derive dates from today (week 1 = current ISO week)
        sessions_data = self._map_blueprint_to_sessions(plan.id, blueprint)

        sessions = await self.planned_session_repo.bulk_create(sessions_data)
        plan.planned_sessions = sessions
        return plan

    def _map_blueprint_to_sessions(
        self, plan_id: uuid.UUID, blueprint: PlanBlueprint
    ) -> list[dict]:
        today = date.today()
        sessions_data: list[dict] = []

        for week in blueprint.weeks:
            week_start = today + timedelta(weeks=week.week_number - 1)
            # Find Monday of that week
            days_since_monday = week_start.weekday()
            monday = week_start - timedelta(days=days_since_monday)

            for day_str, assignment in week.sessions.items():
                try:
                    day_offset = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"].index(
                        day_str.lower()
                    )
                except ValueError:
                    continue

                scheduled_date = monday + timedelta(days=day_offset)
                dominant_intent = SESSION_TYPE_TO_DOMINANT_INTENT[
                    assignment.session_type
                ]

                sessions_data.append(
                    {
                        "training_plan_id": plan_id,
                        "scheduled_date": scheduled_date,
                        "session_type": assignment.session_type,
                        "dominant_physiological_intent": dominant_intent,
                        "target_duration_minutes": assignment.target_duration_minutes,
                        "is_key_session": assignment.is_key_session,
                        "week_number": week.week_number,
                        "phase": week.phase,
                    }
                )

        return sessions_data

    async def get_active_plan(
        self, athlete_id: uuid.UUID, uow: UnitOfWork
    ) -> TrainingPlanResponse | None:
        plan = await self.training_plan_repo.get_active_by_athlete(athlete_id)
        if plan is None:
            return None
        return self._build_response(plan)

    async def get_plan_by_id(
        self, plan_id: uuid.UUID, uow: UnitOfWork
    ) -> TrainingPlanResponse | None:
        plan = await self.training_plan_repo.get_by_id(plan_id)
        if plan is None:
            return None
        return self._build_response(plan)

    async def archive_plan(
        self, plan_id: uuid.UUID, uow: UnitOfWork
    ) -> TrainingPlan | None:
        return await self.training_plan_repo.archive_plan(plan_id)

    def _build_response(self, plan: TrainingPlan) -> TrainingPlanResponse:
        sessions = list(plan.planned_sessions) if plan.planned_sessions else []
        return TrainingPlanResponse(
            training_plan=TrainingPlanBase.model_validate(plan),
            planned_sessions=[PlannedSessionBase.model_validate(s) for s in sessions],
        )

    def _count_available_days(self, preferences) -> int:
        schedule = preferences.weekly_schedule
        if not schedule or "days" not in schedule:
            return 0
        return sum(1 for info in schedule["days"].values() if info.get("available", False))