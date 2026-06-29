"""Unit tests for ``workout_target_types`` module.

Tests:
- SESSION_INTENT_MAP covers all SessionType values
- DATA_TIER_TARGET_TYPE maps correctly: Tier 1-2 → power, Tier 3-4 → gap, Tier 5-6 → description
- get_step_physiological_intent() returns RECOVERY for warmup/cooldown/recovery steps
- get_step_physiological_intent() derives intent from SESSION_INTENT_MAP for work steps

Reference plan: docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md
"""

from __future__ import annotations

import pytest

from app.models.enums import (
    DataTier,
    PhysiologicalIntent,
    SessionType,
    StepType,
)
from app.services.workout_target_types import (
    DATA_TIER_TARGET_TYPE,
    SESSION_INTENT_MAP,
    get_step_physiological_intent,
)


# ---------------------------------------------------------------------------
# SESSION_INTENT_MAP completeness.
# ---------------------------------------------------------------------------


class TestSessionIntentMap:
    """Tests for SESSION_INTENT_MAP coverage and values."""

    def test_covers_all_session_types(self) -> None:
        """Every SessionType must have an entry in SESSION_INTENT_MAP."""
        for session_type in SessionType:
            assert (
                session_type in SESSION_INTENT_MAP
            ), f"SessionType.{session_type.name} is missing from SESSION_INTENT_MAP"

    def test_rest_maps_to_recovery(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.REST] == PhysiologicalIntent.RECOVERY

    def test_recovery_run_maps_to_recovery(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.RECOVERY_RUN] == PhysiologicalIntent.RECOVERY

    def test_easy_run_maps_to_low_aerobic(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.EASY_RUN] == PhysiologicalIntent.LOW_AEROBIC

    def test_long_run_maps_to_high_aerobic(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.LONG_RUN] == PhysiologicalIntent.HIGH_AEROBIC

    def test_medium_long_run_maps_to_high_aerobic(self) -> None:
        assert (
            SESSION_INTENT_MAP[SessionType.MEDIUM_LONG_RUN]
            == PhysiologicalIntent.HIGH_AEROBIC
        )

    def test_steady_state_maps_to_high_aerobic(self) -> None:
        assert (
            SESSION_INTENT_MAP[SessionType.STEADY_STATE]
            == PhysiologicalIntent.HIGH_AEROBIC
        )

    def test_tempo_maps_to_threshold(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.TEMPO] == PhysiologicalIntent.THRESHOLD

    def test_threshold_maps_to_threshold(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.THRESHOLD] == PhysiologicalIntent.THRESHOLD

    def test_vo2max_maps_to_vo2max(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.VO2MAX] == PhysiologicalIntent.VO2MAX

    def test_hill_repeats_maps_to_vo2max(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.HILL_REPEATS] == PhysiologicalIntent.VO2MAX

    def test_fartlek_maps_to_vo2max(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.FARTLEK] == PhysiologicalIntent.VO2MAX

    def test_strides_maps_to_neuromuscular(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.STRIDES] == PhysiologicalIntent.NEUROMUSCULAR

    def test_drills_mobility_maps_to_neuromuscular(self) -> None:
        assert (
            SESSION_INTENT_MAP[SessionType.DRILLS_MOBILITY]
            == PhysiologicalIntent.NEUROMUSCULAR
        )

    def test_cross_training_maps_to_low_aerobic(self) -> None:
        assert (
            SESSION_INTENT_MAP[SessionType.CROSS_TRAINING]
            == PhysiologicalIntent.LOW_AEROBIC
        )

    def test_test_session_maps_to_vo2max(self) -> None:
        assert (
            SESSION_INTENT_MAP[SessionType.TEST_SESSION] == PhysiologicalIntent.VO2MAX
        )

    def test_optional_run_maps_to_recovery(self) -> None:
        assert SESSION_INTENT_MAP[SessionType.OPTIONAL_RUN] == PhysiologicalIntent.RECOVERY


# ---------------------------------------------------------------------------
# DATA_TIER_TARGET_TYPE mapping.
# ---------------------------------------------------------------------------


class TestDataTierTargetType:
    """Tests for DATA_TIER_TARGET_TYPE mapping."""

    def test_tier_1_maps_to_power(self) -> None:
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_1] == "power"

    def test_tier_2_maps_to_power(self) -> None:
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_2] == "power"

    def test_tier_3_maps_to_gap(self) -> None:
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_3] == "gap"

    def test_tier_4_maps_to_gap(self) -> None:
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_4] == "gap"

    def test_tier_5_maps_to_description(self) -> None:
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_5] == "description"

    def test_tier_6_maps_to_description(self) -> None:
        assert DATA_TIER_TARGET_TYPE[DataTier.TIER_6] == "description"

    def test_covers_all_data_tiers(self) -> None:
        """Every DataTier must have an entry in DATA_TIER_TARGET_TYPE."""
        for tier in DataTier:
            assert (
                tier in DATA_TIER_TARGET_TYPE
            ), f"DataTier.TIER_{tier.value} is missing from DATA_TIER_TARGET_TYPE"


# ---------------------------------------------------------------------------
# get_step_physiological_intent()
# ---------------------------------------------------------------------------


class TestGetStepPhysiologicalIntent:
    """Tests for get_step_physiological_intent() helper."""

    def test_warmup_returns_recovery(self) -> None:
        intent = get_step_physiological_intent(StepType.WARMUP, SessionType.THRESHOLD)
        assert intent == PhysiologicalIntent.RECOVERY

    def test_cooldown_returns_recovery(self) -> None:
        intent = get_step_physiological_intent(StepType.COOLDOWN, SessionType.THRESHOLD)
        assert intent == PhysiologicalIntent.RECOVERY

    def test_recovery_step_type_returns_recovery(self) -> None:
        # Intra-interval recovery step
        intent = get_step_physiological_intent(StepType.RECOVERY, SessionType.THRESHOLD)
        assert intent == PhysiologicalIntent.RECOVERY

    def test_work_step_derives_from_session_intent_map(self) -> None:
        # threshold session → threshold intent
        intent = get_step_physiological_intent(StepType.WORK, SessionType.THRESHOLD)
        assert intent == PhysiologicalIntent.THRESHOLD

    def test_work_step_easy_run_yields_low_aerobic(self) -> None:
        intent = get_step_physiological_intent(StepType.WORK, SessionType.EASY_RUN)
        assert intent == PhysiologicalIntent.LOW_AEROBIC

    def test_work_step_vo2max_yields_vo2max(self) -> None:
        intent = get_step_physiological_intent(StepType.WORK, SessionType.VO2MAX)
        assert intent == PhysiologicalIntent.VO2MAX

    def test_work_step_strides_yields_neuromuscular(self) -> None:
        intent = get_step_physiological_intent(StepType.WORK, SessionType.STRIDES)
        assert intent == PhysiologicalIntent.NEUROMUSCULAR

    def test_work_step_rest_yields_recovery(self) -> None:
        # Rest day work step would still be recovery intent per map
        intent = get_step_physiological_intent(StepType.WORK, SessionType.REST)
        assert intent == PhysiologicalIntent.RECOVERY

    def test_warmup_ignores_session_type(self) -> None:
        # Regardless of session type, warmup is always recovery
        for session_type in SessionType:
            intent = get_step_physiological_intent(StepType.WARMUP, session_type)
            assert (
                intent == PhysiologicalIntent.RECOVERY
            ), f"warmup + {session_type} should yield RECOVERY, got {intent}"

    def test_cooldown_ignores_session_type(self) -> None:
        # Regardless of session type, cooldown is always recovery
        for session_type in SessionType:
            intent = get_step_physiological_intent(StepType.COOLDOWN, session_type)
            assert (
                intent == PhysiologicalIntent.RECOVERY
            ), f"cooldown + {session_type} should yield RECOVERY, got {intent}"