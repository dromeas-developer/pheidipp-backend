from dataclasses import dataclass
from datetime import date
from typing import Optional

from pydantic import BaseModel

from app.models.athlete import Athlete
from app.models.athlete_profile import AthleteProfile
from app.models.athlete_preferences import AthletePreferences
from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState
from app.models.enums import Gender, SportBackground, GoalType, ConfidenceLevel


@dataclass
class ContextBudget:
    max_input_tokens: int = 4000
    include_recent_sessions: int = 0
    include_coach_messages: int = 0
    include_wellness_trend: bool = False
    summarize_older_blocks: bool = False
    omit_low_confidence_signals: bool = True


class AthleteContext(BaseModel):
    first_name: str
    age: Optional[int] = None
    gender: Optional[Gender] = None
    sport_background: Optional[SportBackground] = None
    years_structured_training: Optional[float] = None
    training_time_of_day: Optional[str] = None
    gps_source: Optional[str] = None
    hr_source: Optional[str] = None
    power_source: Optional[str] = None


class GoalContext(BaseModel):
    goal_type: Optional[GoalType] = None
    goal_event_type: Optional[str] = None
    goal_event_name: Optional[str] = None
    goal_event_date: Optional[date] = None
    goal_description: Optional[str] = None
    weeks_to_event: Optional[int] = None
    is_open_training: bool = False


class TwinContext(BaseModel):
    fitness_score: float
    fatigue_score: float
    max_hr_estimate: float
    lt1_hr_estimate: float
    lt2_hr_estimate: float
    lt1_pace_estimate: Optional[float] = None
    lt2_pace_estimate: Optional[float] = None
    structural_capacity_score: float
    confidence_level: ConfidenceLevel
    data_tier: str
    fitness_band: str
    structural_band: str
    hr_descriptor: str
    include_threshold_descriptors: bool = True


class PlanContext(BaseModel):
    plan_arc: str
    first_block_focus: str
    sessions_per_week: int
    primary_focus: str


class CoachingInsights(BaseModel):
    strengths: list[str]
    gaps: list[str]
    crossover_note: Optional[str] = None
    cycle_tracking_note: Optional[str] = None


class FirstMessageCoachingBrief(BaseModel):
    brief_version: str = "v1"
    athlete: AthleteContext
    goal: GoalContext
    twin: TwinContext
    plan: PlanContext
    insights: CoachingInsights
    budget_snapshot: dict


class FirstMessageBriefBuilder:
    def __init__(self):
        pass

    async def build(
        self,
        athlete: Athlete,
        profile: AthleteProfile,
        preferences: AthletePreferences,
        training_block: TrainingBlock,
        twin_state: TwinState,
        budget: Optional[ContextBudget] = None,
    ) -> FirstMessageCoachingBrief:
        if budget is None:
            budget = ContextBudget()

        # Athlete context
        first_name = profile.first_name or "Athlete"
        age = None
        if profile.date_of_birth:
            today = date.today()
            age = (
                today.year
                - profile.date_of_birth.year
                - (
                    (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
                )
            )

        athlete_ctx = AthleteContext(
            first_name=first_name,
            age=age,
            gender=profile.gender,
            sport_background=preferences.sport_background,
            years_structured_training=preferences.years_structured_training,
            training_time_of_day=preferences.training_time_of_day.value if preferences.training_time_of_day else None,
            gps_source=preferences.gps_source.value if preferences.gps_source else None,
            hr_source=preferences.hr_source.value if preferences.hr_source else None,
            power_source=preferences.power_source.value if preferences.power_source else None,
        )

        # Goal context
        weeks_to_event = None
        if training_block.goal_event_date:
            today = date.today()
            if training_block.goal_event_date >= today:
                weeks_to_event = (
                    training_block.goal_event_date - today
                ).days // 7

        is_open_training = (
            training_block.goal_type is None
            or training_block.goal_type == GoalType.MAINTENANCE
            or training_block.goal_type == GoalType.RECOVERY
            or training_block.goal_event_date is None
        )

        goal_ctx = GoalContext(
            goal_type=training_block.goal_type,
            goal_event_type=training_block.goal_event_type.value if training_block.goal_event_type else None,
            goal_event_name=training_block.goal_event_name,
            goal_event_date=training_block.goal_event_date,
            goal_description=training_block.goal_description,
            weeks_to_event=weeks_to_event,
            is_open_training=is_open_training,
        )

        # Twin context
        fitness_score = twin_state.fitness_score
        if fitness_score >= 81:
            fitness_band = "elite"
        elif fitness_score >= 51:
            fitness_band = "advanced"
        elif fitness_score >= 21:
            fitness_band = "intermediate"
        else:
            fitness_band = "beginner"

        structural_score = twin_state.structural_capacity_score
        if structural_score >= 0.6:
            structural_band = "established"
        elif structural_score >= 0.4:
            structural_band = "developing"
        else:
            structural_band = "building"

        max_hr = twin_state.max_hr_estimate
        if max_hr >= 190:
            hr_descriptor = "high 180s"
        elif max_hr >= 180:
            hr_descriptor = "high 170s"
        elif max_hr >= 170:
            hr_descriptor = "mid 160s"
        elif max_hr >= 160:
            hr_descriptor = "low 160s"
        else:
            hr_descriptor = "150s"

        include_threshold_descriptors = True
        if budget.omit_low_confidence_signals and twin_state.confidence_level == ConfidenceLevel.LOW:
            include_threshold_descriptors = False

        twin_ctx = TwinContext(
            fitness_score=fitness_score,
            fatigue_score=twin_state.fatigue_score,
            max_hr_estimate=max_hr,
            lt1_hr_estimate=twin_state.lt1_hr_estimate,
            lt2_hr_estimate=twin_state.lt2_hr_estimate,
            lt1_pace_estimate=twin_state.lt1_pace_estimate,
            lt2_pace_estimate=twin_state.lt2_pace_estimate,
            structural_capacity_score=structural_score,
            confidence_level=twin_state.confidence_level,
            data_tier=twin_state.data_tier.value,
            fitness_band=fitness_band,
            structural_band=structural_band,
            hr_descriptor=hr_descriptor,
            include_threshold_descriptors=include_threshold_descriptors,
        )

        # Plan context
        if weeks_to_event is not None and weeks_to_event <= 12:
            if is_open_training:
                plan_arc = "short-term build to race-ready fitness"
            else:
                plan_arc = f"focused {weeks_to_event}-week build toward {training_block.goal_event_name or 'your goal'}"
        elif weeks_to_event is not None and weeks_to_event <= 26:
            plan_arc = f"{weeks_to_event}-week progressive periodization toward {training_block.goal_event_name or 'your goal'}"
        else:
            plan_arc = "long-term aerobic development and structural building"

        if structural_score < 0.4:
            first_block_focus = "building aerobic base and structural resilience"
            sessions_per_week = 4
            primary_focus = "structural capacity"
        elif structural_score < 0.6:
            first_block_focus = "consolidating aerobic foundation while introducing threshold work"
            sessions_per_week = 4
            primary_focus = "aerobic base"
        else:
            if fitness_score < 50:
                first_block_focus = "establishing race-specific fitness and pace familiarity"
                sessions_per_week = 5
                primary_focus = "race-prep"
            else:
                first_block_focus = "refining threshold capacity and race execution"
                sessions_per_week = 5
                primary_focus = "threshold"

        plan_ctx = PlanContext(
            plan_arc=plan_arc,
            first_block_focus=first_block_focus,
            sessions_per_week=sessions_per_week,
            primary_focus=primary_focus,
        )

        # Coaching insights
        strengths = []
        gaps = []

        if preferences.sport_background == SportBackground.CYCLING_CROSSOVER:
            strengths.append("crossover from cycling with strong aerobic base")
        if preferences.sport_background == SportBackground.SWIMMING_CROSSOVER:
            strengths.append("crossover from swimming with excellent work capacity")
        if preferences.sport_background == SportBackground.RUNNING_PRIMARY:
            strengths.append("running-focused background")

        if preferences.years_structured_training and preferences.years_structured_training >= 3:
            strengths.append("several years of structured training")

        if fitness_score >= 60:
            strengths.append("solid fitness foundation")

        if preferences.hr_source and preferences.hr_source.value == "chest_strap":
            strengths.append("chest strap HR monitoring for accurate training zones")

        if preferences.power_source and preferences.power_source.value == "running_power":
            strengths.append("running power data available")

        if structural_score < 0.4:
            gaps.append("building structural capacity")
        if fitness_score < 40:
            gaps.append("developing aerobic base")
        if weeks_to_event and weeks_to_event < 12:
            gaps.append("short timeline to event")
        if not preferences.hr_source or preferences.hr_source.value == "none":
            gaps.append("no HR data — using estimated thresholds")

        crossover_note = None
        if preferences.sport_background == SportBackground.CYCLING_CROSSOVER:
            crossover_note = "Your cycling background gives you a strong aerobic engine — we'll leverage that while building running-specific strength."
        elif preferences.sport_background == SportBackground.SWIMMING_CROSSOVER:
            crossover_note = "Your swimming background means you're comfortable at intensity — we'll channel that into running-specific threshold work."

        cycle_tracking_note = None
        if profile.gender == Gender.FEMALE:
            cycle_tracking_note = "Note: Consider tracking menstrual cycle for training load optimization — we can adjust intensity on low-energy days."

        insights = CoachingInsights(
            strengths=strengths,
            gaps=gaps,
            crossover_note=crossover_note,
            cycle_tracking_note=cycle_tracking_note if profile.gender == Gender.FEMALE else None,
        )

        return FirstMessageCoachingBrief(
            brief_version="v1",
            athlete=athlete_ctx,
            goal=goal_ctx,
            twin=twin_ctx,
            plan=plan_ctx,
            insights=insights,
            budget_snapshot={
                "max_input_tokens": budget.max_input_tokens,
                "include_recent_sessions": budget.include_recent_sessions,
                "include_coach_messages": budget.include_coach_messages,
                "include_wellness_trend": budget.include_wellness_trend,
                "summarize_older_blocks": budget.summarize_older_blocks,
                "omit_low_confidence_signals": budget.omit_low_confidence_signals,
            },
        )