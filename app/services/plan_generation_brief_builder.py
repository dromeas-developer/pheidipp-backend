import json
from uuid import UUID

from pydantic import BaseModel

from app.models.athlete import Athlete
from app.models.athlete_preferences import AthletePreferences
from app.models.training_block import TrainingBlock
from app.models.twin_state import TwinState
from app.models.enums import SportBackground
from app.schemas.plan_generation import (
    PhaseArc,
    PlanBlueprint,
    MethodologyProfile,
)


class PlanGenerationBrief(BaseModel):
    brief_version: str = "v1"
    athlete_summary: dict
    goal_summary: dict
    twin_summary: dict
    available_days: dict[str, dict]
    phase_arc: PhaseArc
    explicit_constraints: list[str]
    coaching_insights: dict
    methodology_profile: MethodologyProfile


class PlanGenerationBriefBuilder:
    def build(
        self,
        athlete: Athlete,
        preferences: AthletePreferences,
        training_block: TrainingBlock,
        twin_state: TwinState,
        phase_arc: PhaseArc,
        methodology_profile: MethodologyProfile,
    ) -> PlanGenerationBrief:
        athlete_summary = self._build_athlete_summary(athlete, preferences)
        goal_summary = self._build_goal_summary(training_block)
        twin_summary = self._build_twin_summary(twin_state)
        available_days = self._build_available_days(preferences)
        explicit_constraints = self._build_explicit_constraints(
            preferences, phase_arc
        )
        coaching_insights = self._build_coaching_insights(
            preferences, twin_state, methodology_profile
        )

        return PlanGenerationBrief(
            athlete_summary=athlete_summary,
            goal_summary=goal_summary,
            twin_summary=twin_summary,
            available_days=available_days,
            phase_arc=phase_arc,
            explicit_constraints=explicit_constraints,
            coaching_insights=coaching_insights,
            methodology_profile=methodology_profile,
        )

    def _build_athlete_summary(
        self, athlete: Athlete, preferences: AthletePreferences
    ) -> dict:
        profile = athlete.profile
        return {
            "name": profile.display_name if profile else None,
            "sport_background": (
                preferences.sport_background.value
                if preferences.sport_background
                else None
            ),
            "years_structured_training": preferences.years_structured_training,
            "available_days_count": self._count_available_days(preferences),
        }

    def _build_goal_summary(self, training_block: TrainingBlock) -> dict:
        return {
            "goal_event_type": (
                training_block.goal_event_type.value
                if training_block.goal_event_type
                else None
            ),
            "goal_event_name": training_block.goal_event_name,
            "goal_event_date": (
                training_block.goal_event_date.isoformat()
                if training_block.goal_event_date
                else None
            ),
        }

    def _build_twin_summary(self, twin_state: TwinState) -> dict:
        return {
            "fitness_score": twin_state.fitness_score,
            "structural_capacity_score": twin_state.structural_capacity_score,
            "max_hr_estimate": twin_state.max_hr_estimate,
            "lt1_hr_estimate": twin_state.lt1_hr_estimate,
            "lt2_hr_estimate": twin_state.lt2_hr_estimate,
            "confidence_level": (
                twin_state.confidence_level.value
                if twin_state.confidence_level
                else None
            ),
            "data_tier": (
                twin_state.data_tier.value
                if twin_state.data_tier
                else None
            ),
        }

    def _build_available_days(
        self, preferences: AthletePreferences
    ) -> dict[str, dict]:
        schedule = preferences.weekly_schedule
        if not schedule or "days" not in schedule:
            return {}
        return {
            day: info
            for day, info in schedule["days"].items()
            if info.get("available", False)
        }

    def _count_available_days(self, preferences: AthletePreferences) -> int:
        return len(self._build_available_days(preferences))

    def _build_explicit_constraints(
        self, preferences: AthletePreferences, phase_arc: PhaseArc
    ) -> list[str]:
        constraints = [
            "No back-to-back threshold or VO2 sessions.",
            "Long runs must be followed by rest or recovery_run in the next scheduled day.",
            "Hard sessions require easy day before.",
            "Maximum two key sessions per week.",
            "Sessions may only occur on available days exactly as specified in available_days.",
            "Recovery weeks must have reduced hard-session density.",
            "Respect available_days keys precisely.",
            "Recovery weeks must reduce overall load significantly.",
        ]
        return constraints

    def _build_coaching_insights(
        self,
        preferences: AthletePreferences,
        twin_state: TwinState,
        methodology_profile: MethodologyProfile,
    ) -> dict:
        trait_weights = methodology_profile.trait_weights
        top_trait = (
            max(trait_weights.items(), key=lambda x: x[1])[0]
            if trait_weights
            else None
        )
        return {
            "long_run_progression": (
                "Long runs should generally progress gradually."
            ),
            "recovery_week_guidance": (
                "Recovery weeks should reduce stress exposure."
            ),
            "race_specificity_timing": (
                "Race specificity should increase near the event."
            ),
            "taper_guidance": (
                "Taper weeks should reduce overall load."
            ),
            "key_session_density": (
                "Key session density should evolve progressively."
            ),
            "primary_methodology_trait": (
                top_trait.value if top_trait else None
            ),
        }