"""Unit tests for FirstMessageBriefBuilder."""

import uuid
from datetime import date, datetime

import pytest

from app.services.first_message_brief_builder import (
    FirstMessageBriefBuilder,
    FirstMessageCoachingBrief,
    ContextBudget,
)
from app.models.enums import (
    Gender,
    SportBackground,
    GoalType,
    ConfidenceLevel,
    DataTier,
    GoalEventType,
    GoalStatus,
)
from tests.factories import (
    make_athlete,
    make_athlete_profile,
    make_athlete_preferences,
    make_training_block,
    make_twin_state,
)


@pytest.fixture
def builder():
    """Fixture returning FirstMessageBriefBuilder."""
    return FirstMessageBriefBuilder()


@pytest.fixture
def sample_athlete():
    """Fixture returning a sample Athlete."""
    return make_athlete()


@pytest.fixture
def sample_profile():
    """Fixture returning a sample AthleteProfile."""
    return make_athlete_profile(
        first_name="John",
        date_of_birth=date(1990, 5, 15),
        gender=Gender.MALE,
    )


@pytest.fixture
def sample_preferences():
    """Fixture returning a sample AthletePreferences."""
    return make_athlete_preferences(
        sport_background=SportBackground.RUNNING_PRIMARY,
        years_structured_training=3.0,
    )


@pytest.fixture
def sample_training_block():
    """Fixture returning a sample TrainingBlock."""
    return make_training_block(
        goal_type=GoalType.RACE,
        goal_event_type=GoalEventType.MARATHON,
        goal_event_name="Boston Marathon 2024",
        goal_event_date=date(2024, 4, 15),
    )


@pytest.fixture
def sample_twin_state():
    """Fixture returning a sample TwinState."""
    return make_twin_state(
        fitness_score=65.0,
        fatigue_score=20.0,
        max_hr_estimate=185.0,
        lt1_hr_estimate=135.0,
        lt2_hr_estimate=160.0,
        structural_capacity_score=0.65,
        confidence_level=ConfidenceLevel.MEDIUM,
        data_tier=DataTier.TIER1,
    )


class TestFirstMessageBriefBuilder:
    """Tests for FirstMessageBriefBuilder."""

    @pytest.mark.asyncio
    async def test_build_returns_brief_with_version(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify build returns a FirstMessageCoachingBrief with brief_version='v1'."""
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert isinstance(brief, FirstMessageCoachingBrief)
        assert brief.brief_version == "v1"

    @pytest.mark.asyncio
    async def test_build_includes_budget_snapshot(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify build includes budget_snapshot with default budget values."""
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert "max_input_tokens" in brief.budget_snapshot
        assert brief.budget_snapshot["max_input_tokens"] == 4000
        assert brief.budget_snapshot["include_recent_sessions"] == 0
        assert brief.budget_snapshot["include_coach_messages"] == 0
        assert brief.budget_snapshot["include_wellness_trend"] is False
        assert brief.budget_snapshot["summarize_older_blocks"] is False
        assert brief.budget_snapshot["omit_low_confidence_signals"] is True

    @pytest.mark.asyncio
    async def test_first_name_from_profile(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify first_name is read from profile.first_name, not from athlete."""
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert brief.athlete.first_name == "John"

    @pytest.mark.asyncio
    async def test_age_computed_from_date_of_birth(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify age is computed correctly from profile.date_of_birth."""
        # Profile DOB is 1990-05-15, today is 2026-05-19
        # Age should be 36 (birthday has passed this year: May 19 >= May 15)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert brief.athlete.age == 36

    @pytest.mark.asyncio
    async def test_fitness_band_elite(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify fitness band is 'elite' when score >= 81."""
        twin = make_twin_state(fitness_score=85.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.fitness_band == "elite"

    @pytest.mark.asyncio
    async def test_fitness_band_advanced(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify fitness band is 'advanced' when score >= 51."""
        twin = make_twin_state(fitness_score=60.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.fitness_band == "advanced"

    @pytest.mark.asyncio
    async def test_fitness_band_intermediate(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify fitness band is 'intermediate' when score >= 21."""
        twin = make_twin_state(fitness_score=30.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.fitness_band == "intermediate"

    @pytest.mark.asyncio
    async def test_fitness_band_beginner(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify fitness band is 'beginner' when score < 21."""
        twin = make_twin_state(fitness_score=15.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.fitness_band == "beginner"

    @pytest.mark.asyncio
    async def test_structural_band_established(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify structural band is 'established' when score >= 0.6."""
        twin = make_twin_state(structural_capacity_score=0.7)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.structural_band == "established"

    @pytest.mark.asyncio
    async def test_structural_band_developing(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify structural band is 'developing' when score >= 0.4."""
        twin = make_twin_state(structural_capacity_score=0.5)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.structural_band == "developing"

    @pytest.mark.asyncio
    async def test_structural_band_building(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify structural band is 'building' when score < 0.4."""
        twin = make_twin_state(structural_capacity_score=0.3)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.twin.structural_band == "building"

    @pytest.mark.asyncio
    async def test_hr_descriptor(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify HR descriptor converts precise HR to natural language."""
        # Test various HR ranges
        twin = make_twin_state(max_hr_estimate=192.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )
        assert brief.twin.hr_descriptor == "high 180s"

        twin = make_twin_state(max_hr_estimate=182.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )
        assert brief.twin.hr_descriptor == "high 170s"

        twin = make_twin_state(max_hr_estimate=172.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )
        assert brief.twin.hr_descriptor == "mid 160s"

        twin = make_twin_state(max_hr_estimate=162.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )
        assert brief.twin.hr_descriptor == "low 160s"

        twin = make_twin_state(max_hr_estimate=155.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )
        assert brief.twin.hr_descriptor == "150s"

    @pytest.mark.asyncio
    async def test_is_open_training_when_goal_type_none(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify is_open_training is True when goal_type is None."""
        block = make_training_block(goal_type=None)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=sample_twin_state,
        )

        assert brief.goal.is_open_training is True

    @pytest.mark.asyncio
    async def test_is_open_training_when_goal_type_maintenance(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify is_open_training is True when goal_type is maintenance."""
        block = make_training_block(goal_type=GoalType.MAINTENANCE)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=sample_twin_state,
        )

        assert brief.goal.is_open_training is True

    @pytest.mark.asyncio
    async def test_is_open_training_when_goal_type_recovery(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify is_open_training is True when goal_type is recovery."""
        block = make_training_block(goal_type=GoalType.RECOVERY)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=sample_twin_state,
        )

        assert brief.goal.is_open_training is True

    @pytest.mark.asyncio
    async def test_is_open_training_when_no_event_date(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify is_open_training is True when no event date."""
        block = make_training_block(goal_type=GoalType.RACE, goal_event_date=None)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=sample_twin_state,
        )

        assert brief.goal.is_open_training is True

    @pytest.mark.asyncio
    async def test_include_threshold_descriptors_false_when_omit_low_confidence(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify include_threshold_descriptors is False when omit_low_confidence_signals=True and confidence is LOW."""
        twin = make_twin_state(confidence_level=ConfidenceLevel.LOW)
        budget = ContextBudget(omit_low_confidence_signals=True)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
            budget=budget,
        )

        assert brief.twin.include_threshold_descriptors is False

    @pytest.mark.asyncio
    async def test_include_threshold_descriptors_true_when_not_low_confidence(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify include_threshold_descriptors is True when confidence is not LOW."""
        twin = make_twin_state(confidence_level=ConfidenceLevel.HIGH)
        budget = ContextBudget(omit_low_confidence_signals=True)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
            budget=budget,
        )

        assert brief.twin.include_threshold_descriptors is True

    @pytest.mark.asyncio
    async def test_plan_arc_short_term(
        self, builder, sample_athlete, sample_profile, sample_preferences
    ):
        """Verify plan arc heuristic for short timeline (<=12 weeks)."""
        block = make_training_block(
            goal_type=GoalType.RACE,
            goal_event_date=date(2024, 2, 1),  # ~2 weeks away
        )
        twin = make_twin_state(structural_capacity_score=0.5)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=twin,
        )

        assert "short-term" in brief.plan.plan_arc.lower() or "build" in brief.plan.plan_arc.lower()

    @pytest.mark.asyncio
    async def test_plan_arc_medium_term(
        self, builder, sample_athlete, sample_profile, sample_preferences
    ):
        """Verify plan arc heuristic for medium timeline (12-26 weeks)."""
        # Use a date 20 weeks in the future from today (2026-05-19 + 20 weeks = ~Oct 2026)
        block = make_training_block(
            goal_type=GoalType.RACE,
            goal_event_date=date(2026, 10, 1),  # ~20 weeks away
        )
        twin = make_twin_state(structural_capacity_score=0.5)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=twin,
        )

        assert "20" in brief.plan.plan_arc or "progressive" in brief.plan.plan_arc.lower()

    @pytest.mark.asyncio
    async def test_first_block_focus_from_structural_capacity(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify first block focus derives from structural_capacity_score."""
        # Low structural capacity
        twin = make_twin_state(structural_capacity_score=0.3, fitness_score=30.0)
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert "structural" in brief.plan.first_block_focus.lower() or "aerobic" in brief.plan.first_block_focus.lower()

    @pytest.mark.asyncio
    async def test_strengths_cycling_crossover(
        self, builder, sample_athlete, sample_profile, sample_training_block
    ):
        """Verify strengths list includes entry for cycling_crossover."""
        prefs = make_athlete_preferences(sport_background=SportBackground.CYCLING_CROSSOVER)
        twin = make_twin_state(fitness_score=65.0)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=prefs,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert any("cycling" in s.lower() for s in brief.insights.strengths)

    @pytest.mark.asyncio
    async def test_strengths_swimming_crossover(
        self, builder, sample_athlete, sample_profile, sample_training_block
    ):
        """Verify strengths list includes entry for swimming_crossover."""
        prefs = make_athlete_preferences(sport_background=SportBackground.SWIMMING_CROSSOVER)
        twin = make_twin_state(fitness_score=65.0)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=prefs,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert any("swimming" in s.lower() for s in brief.insights.strengths)

    @pytest.mark.asyncio
    async def test_strengths_chest_strap(
        self, builder, sample_athlete, sample_profile, sample_training_block,
        sample_twin_state
    ):
        """Verify strengths list includes entry for chest_strap HR source."""
        from app.models.enums import HrSource
        prefs = make_athlete_preferences(hr_source=HrSource.CHEST_STRAP)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=prefs,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert any("chest" in s.lower() or "hr" in s.lower() for s in brief.insights.strengths)

    @pytest.mark.asyncio
    async def test_strengths_running_power(
        self, builder, sample_athlete, sample_profile, sample_training_block,
        sample_twin_state
    ):
        """Verify strengths list includes entry for running_power."""
        from app.models.enums import PowerSource
        prefs = make_athlete_preferences(power_source=PowerSource.RUNNING_POWER)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=prefs,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert any("power" in s.lower() for s in brief.insights.strengths)

    @pytest.mark.asyncio
    async def test_gaps_low_structural_capacity(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify gaps list includes entry for low structural capacity."""
        twin = make_twin_state(structural_capacity_score=0.3)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert any("structural" in g.lower() for g in brief.insights.gaps)

    @pytest.mark.asyncio
    async def test_gaps_short_timeline(
        self, builder, sample_athlete, sample_profile, sample_preferences
    ):
        """Verify gaps list includes entry for short timeline."""
        # Use a date 8 weeks in the future from today (2026-05-19 + 8 weeks = ~July 2026)
        block = make_training_block(
            goal_type=GoalType.RACE,
            goal_event_date=date(2026, 7, 12),  # ~8 weeks away
        )
        twin = make_twin_state()

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=block,
            twin_state=twin,
        )

        assert any("short" in g.lower() or "timeline" in g.lower() for g in brief.insights.gaps)

    @pytest.mark.asyncio
    async def test_gaps_missing_hr_data(
        self, builder, sample_athlete, sample_profile, sample_training_block,
        sample_twin_state
    ):
        """Verify gaps list includes entry for missing HR data."""
        from app.models.enums import HrSource
        prefs = make_athlete_preferences(hr_source=HrSource.NONE)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=prefs,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert any("hr" in g.lower() or "heart" in g.lower() for g in brief.insights.gaps)

    @pytest.mark.asyncio
    async def test_primary_focus_order_structural(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify primary focus ordering: structural when structural capacity < 0.4."""
        twin = make_twin_state(structural_capacity_score=0.3, fitness_score=50.0)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.plan.primary_focus == "structural capacity"

    @pytest.mark.asyncio
    async def test_primary_focus_order_aerobic(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify primary focus ordering: aerobic base when structural < 0.6."""
        twin = make_twin_state(structural_capacity_score=0.5, fitness_score=50.0)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.plan.primary_focus == "aerobic base"

    @pytest.mark.asyncio
    async def test_primary_focus_order_race_prep(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify primary focus ordering: race-prep when structural >= 0.6 and fitness < 50."""
        twin = make_twin_state(structural_capacity_score=0.7, fitness_score=45.0)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.plan.primary_focus == "race-prep"

    @pytest.mark.asyncio
    async def test_primary_focus_order_threshold(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block
    ):
        """Verify primary focus ordering: threshold when structural >= 0.6 and fitness >= 50."""
        twin = make_twin_state(structural_capacity_score=0.7, fitness_score=60.0)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=twin,
        )

        assert brief.plan.primary_focus == "threshold"

    @pytest.mark.asyncio
    async def test_menstrual_cycle_tracking_note_for_female(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify menstrual cycle tracking note is included when profile.gender == FEMALE."""
        profile = make_athlete_profile(gender=Gender.FEMALE)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert brief.insights.cycle_tracking_note is not None
        assert "cycle" in brief.insights.cycle_tracking_note.lower()

    @pytest.mark.asyncio
    async def test_no_menstrual_cycle_note_for_male(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify menstrual cycle tracking note is NOT included when profile.gender != FEMALE."""
        profile = make_athlete_profile(gender=Gender.MALE)

        brief = await builder.build(
            athlete=sample_athlete,
            profile=profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert brief.insights.cycle_tracking_note is None

    @pytest.mark.asyncio
    async def test_context_budget_defaults(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify ContextBudget defaults are correct."""
        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
        )

        assert brief.budget_snapshot["max_input_tokens"] == 4000
        assert brief.budget_snapshot["include_recent_sessions"] == 0
        assert brief.budget_snapshot["include_coach_messages"] == 0
        assert brief.budget_snapshot["include_wellness_trend"] is False
        assert brief.budget_snapshot["summarize_older_blocks"] is False
        assert brief.budget_snapshot["omit_low_confidence_signals"] is True

    @pytest.mark.asyncio
    async def test_custom_context_budget_overrides(
        self, builder, sample_athlete, sample_profile, sample_preferences,
        sample_training_block, sample_twin_state
    ):
        """Verify custom ContextBudget overrides are reflected in budget_snapshot."""
        budget = ContextBudget(
            max_input_tokens=6000,
            include_recent_sessions=5,
            include_coach_messages=2,
            include_wellness_trend=True,
            summarize_older_blocks=True,
            omit_low_confidence_signals=False,
        )

        brief = await builder.build(
            athlete=sample_athlete,
            profile=sample_profile,
            preferences=sample_preferences,
            training_block=sample_training_block,
            twin_state=sample_twin_state,
            budget=budget,
        )

        assert brief.budget_snapshot["max_input_tokens"] == 6000
        assert brief.budget_snapshot["include_recent_sessions"] == 5
        assert brief.budget_snapshot["include_coach_messages"] == 2
        assert brief.budget_snapshot["include_wellness_trend"] is True
        assert brief.budget_snapshot["summarize_older_blocks"] is True
        assert brief.budget_snapshot["omit_low_confidence_signals"] is False