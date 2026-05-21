"""Unit tests for MethodologyProfileBuilder."""

import pytest

from app.models.enums import (
    GoalEventType,
    SportBackground,
    ConfidenceLevel,
    MethodologyTrait,
)
from app.services.methodology_profile_builder import MethodologyProfileBuilder
from app.schemas.plan_generation import MethodologyProfile


class TestMethodologyProfileBuilderBuild:
    def _builder(self) -> MethodologyProfileBuilder:
        return MethodologyProfileBuilder()

    def test_build_returns_methodology_profile_with_all_10_traits(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )

        assert isinstance(profile, MethodologyProfile)
        trait_keys = set(profile.trait_weights.keys())
        expected = {
            MethodologyTrait.HIGH_AEROBIC_VOLUME,
            MethodologyTrait.LOW_INTENSITY_DOMINANT,
            MethodologyTrait.THRESHOLD_DENSITY,
            MethodologyTrait.HIGH_INTENSITY_SPARSE,
            MethodologyTrait.HIGH_FREQUENCY,
            MethodologyTrait.STRUCTURAL_DURABILITY,
            MethodologyTrait.RACE_SPECIFICITY,
            MethodologyTrait.VARIETY_EMPHASIS,
            MethodologyTrait.NEUROMUSCULAR_SUPPORT,
            MethodologyTrait.CONSERVATIVE_PROGRESSION,
        }
        assert trait_keys == expected

    def test_marathon_profile_has_high_aerobic_volume_at_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] == 1.0

    def test_marathon_profile_has_structural_durability_at_0_9(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.STRUCTURAL_DURABILITY] == 0.9

    def test_marathon_profile_with_weeks_lt_12_has_conservative_progression_at_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=10,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] == 1.0

    def test_marathon_profile_with_weeks_lt_12_has_reduced_high_aerobic_volume(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=10,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        # Should be 0.8 (not 1.0) for short timeline
        assert profile.trait_weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] == 0.8

    def test_half_marathon_profile_has_elevated_threshold_density(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.HALF_MARATHON,
            weeks_to_goal=12,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        # half_marathon should have elevated THRESHOLD_DENSITY from build phase
        assert profile.trait_weights[MethodologyTrait.THRESHOLD_DENSITY] >= 0.7

    def test_5k_profile_has_high_intensity_sparse_at_0_9(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.FIVE_K,
            weeks_to_goal=12,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.HIGH_INTENSITY_SPARSE] == 0.9

    def test_5k_profile_has_race_specificity_at_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.FIVE_K,
            weeks_to_goal=12,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.RACE_SPECIFICITY] == 1.0

    def test_ultra_profile_has_high_aerobic_volume_at_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.ULTRA,
            weeks_to_goal=20,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.HIGH_AEROBIC_VOLUME] == 1.0

    def test_ultra_profile_has_structural_durability_at_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.ULTRA,
            weeks_to_goal=20,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.STRUCTURAL_DURABILITY] == 1.0

    def test_ultra_profile_has_variety_emphasis_at_0_9(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.ULTRA,
            weeks_to_goal=20,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.VARIETY_EMPHASIS] == 0.9

    def test_default_profile_uses_build_phase_weights(self):
        builder = self._builder()
        profile = builder.build(
            event_type=None,
            weeks_to_goal=12,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.RACE_SPECIFICITY] >= 0.8

    def test_training_age_lt_1_increases_conservative_progression(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=0.5,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] >= 0.9

    def test_training_age_lt_1_decreases_high_intensity_sparse(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.TEN_K,
            weeks_to_goal=12,
            training_age=0.5,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        # Track profile starts at 0.9, experience modifier applies * 0.8 = 0.72
        assert profile.trait_weights[MethodologyTrait.HIGH_INTENSITY_SPARSE] < 0.9

    def test_consistency_score_lt_0_6_increases_conservative_progression(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.4,
        )
        assert profile.trait_weights[MethodologyTrait.CONSERVATIVE_PROGRESSION] >= 0.8

    def test_structural_capacity_score_lt_0_4_sets_durability_and_low_intensity_to_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.3,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.STRUCTURAL_DURABILITY] == 1.0
        assert profile.trait_weights[MethodologyTrait.LOW_INTENSITY_DOMINANT] == 1.0

    def test_available_days_gte_6_sets_high_frequency_to_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=6,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.HIGH_FREQUENCY] == 1.0

    def test_available_days_lte_4_sets_high_frequency_to_0_4(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=3.0,
            available_days=4,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert profile.trait_weights[MethodologyTrait.HIGH_FREQUENCY] == 0.4

    def test_all_weights_normalized_to_lte_1_0(self):
        builder = self._builder()
        profile = builder.build(
            event_type=GoalEventType.MARATHON,
            weeks_to_goal=16,
            training_age=0.5,
            available_days=6,
            structural_capacity_score=0.3,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.4,
        )
        for weight in profile.trait_weights.values():
            assert weight <= 1.0

    def test_build_with_none_event_type_does_not_raise(self):
        builder = self._builder()
        profile = builder.build(
            event_type=None,
            weeks_to_goal=12,
            training_age=3.0,
            available_days=5,
            structural_capacity_score=0.6,
            adaptation_confidence_level=ConfidenceLevel.MEDIUM,
            consistency_score=0.7,
        )
        assert isinstance(profile, MethodologyProfile)