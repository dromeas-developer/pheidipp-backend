"""Unit tests for PlanGenerationBriefBuilder."""

import uuid
from datetime import date

import pytest

from app.models.enums import (
    GoalEventType,
    SportBackground,
    ConfidenceLevel,
    DataTier,
    TrainingPlanStatus,
    SessionType,
    PhysiologicalIntent,
    TrainingPhase,
)
from app.services.plan_generation_brief_builder import PlanGenerationBriefBuilder
from app.schemas.plan_generation import MethodologyProfile, PhaseArc, PhaseArcPhase
from tests.factories import (
    make_athlete,
    make_athlete_profile,
    make_athlete_preferences,
    make_training_block,
    make_twin_state,
    make_training_plan,
    make_planned_session,
)


class TestPlanGenerationBriefBuilderBuild:
    @pytest.fixture
    def athlete(self):
        a = make_athlete()
        a.profile = make_athlete_profile(athlete_id=a.id)
        return a

    @pytest.fixture
    def preferences(self):
        return make_athlete_preferences(
            weekly_schedule={
                "days": {
                    "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                    "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                    "fri": {"available": False, "max_hours": 0, "long_workout": False},
                    "sat": {"available": True, "max_hours": 3.0, "long_workout": True},
                    "sun": {"available": True, "max_hours": 2.0, "long_workout": True},
                }
            }
        )

    @pytest.fixture
    def training_block(self):
        return make_training_block(
            goal_event_type=GoalEventType.MARATHON,
            goal_event_name="Boston Marathon",
            goal_event_date=date(2025, 4, 21),
        )

    @pytest.fixture
    def twin_state(self):
        return make_twin_state(
            fitness_score=0.7,
            structural_capacity_score=0.6,
            max_hr_estimate=185,
            confidence_level=ConfidenceLevel.MEDIUM,
            data_tier=DataTier.TIER2,
        )

    @pytest.fixture
    def phase_arc(self):
        return PhaseArc(
            total_weeks=16,
            phases=[
                PhaseArcPhase(phase=TrainingPhase.BASE, start_week=1, end_week=4),
                PhaseArcPhase(phase=TrainingPhase.BUILD, start_week=5, end_week=14),
                PhaseArcPhase(phase=TrainingPhase.TAPER, start_week=15, end_week=16),
            ],
            recovery_weeks=[5],
        )

    @pytest.fixture
    def methodology_profile(self):
        from app.models.enums import MethodologyTrait
        return MethodologyProfile(
            trait_weights={
                MethodologyTrait.HIGH_AEROBIC_VOLUME: 1.0,
                MethodologyTrait.LOW_INTENSITY_DOMINANT: 0.9,
                MethodologyTrait.THRESHOLD_DENSITY: 0.2,
                MethodologyTrait.HIGH_INTENSITY_SPARSE: 0.3,
                MethodologyTrait.HIGH_FREQUENCY: 0.7,
                MethodologyTrait.STRUCTURAL_DURABILITY: 0.9,
                MethodologyTrait.RACE_SPECIFICITY: 0.2,
                MethodologyTrait.VARIETY_EMPHASIS: 0.5,
                MethodologyTrait.NEUROMUSCULAR_SUPPORT: 0.5,
                MethodologyTrait.CONSERVATIVE_PROGRESSION: 0.8,
            }
        )

    def test_build_returns_brief_with_v1_version(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        assert brief.brief_version == "v1"

    def test_athlete_summary_contains_required_fields(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        summary = brief.athlete_summary
        assert "name" in summary
        assert "sport_background" in summary
        assert "years_structured_training" in summary
        assert "available_days_count" in summary

    def test_goal_summary_contains_required_fields(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        goal = brief.goal_summary
        assert "goal_event_type" in goal
        assert "goal_event_name" in goal
        assert "goal_event_date" in goal

    def test_twin_summary_contains_required_fields(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        twin = brief.twin_summary
        assert "fitness_score" in twin
        assert "structural_capacity_score" in twin
        assert "max_hr_estimate" in twin
        assert "confidence_level" in twin
        assert "data_tier" in twin

    def test_available_days_contains_only_available_days(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        available = brief.available_days
        assert "mon" in available
        assert "wed" in available
        assert "sat" in available
        assert "sun" in available
        assert "fri" not in available

    def test_available_days_empty_when_weekly_schedule_none(self, athlete, training_block, twin_state, phase_arc, methodology_profile):
        builder = PlanGenerationBriefBuilder()
        prefs_no_schedule = make_athlete_preferences(weekly_schedule=None)
        brief = builder.build(
            athlete, prefs_no_schedule, training_block, twin_state, phase_arc, methodology_profile
        )
        assert brief.available_days == {}

    def test_explicit_constraints_contains_all_8_constraints(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        assert len(brief.explicit_constraints) == 8

    def test_coaching_insights_contains_primary_methodology_trait(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        insights = brief.coaching_insights
        assert "primary_methodology_trait" in insights
        # Should be HIGH_AEROBIC_VOLUME as it has highest weight (1.0)
        assert insights["primary_methodology_trait"] == "HIGH_AEROBIC_VOLUME"

    def test_methodology_profile_passed_through_unchanged(
        self, athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
    ):
        builder = PlanGenerationBriefBuilder()
        brief = builder.build(
            athlete, preferences, training_block, twin_state, phase_arc, methodology_profile
        )
        assert brief.methodology_profile == methodology_profile

    def test_count_available_days_returns_correct_count(self, preferences):
        builder = PlanGenerationBriefBuilder()
        count = builder._count_available_days(preferences)
        assert count == 4  # mon, wed, sat, sun

    def test_count_available_days_returns_0_when_schedule_none(self):
        builder = PlanGenerationBriefBuilder()
        prefs = make_athlete_preferences(weekly_schedule=None)
        count = builder._count_available_days(prefs)
        assert count == 0

    def test_count_available_days_returns_0_when_days_missing(self):
        builder = PlanGenerationBriefBuilder()
        prefs = make_athlete_preferences(weekly_schedule={"other_key": "value"})
        count = builder._count_available_days(prefs)
        assert count == 0

    def test_build_available_days_returns_empty_when_days_missing(self):
        builder = PlanGenerationBriefBuilder()
        prefs = make_athlete_preferences(weekly_schedule={"other_key": "value"})
        available = builder._build_available_days(prefs)
        assert available == {}