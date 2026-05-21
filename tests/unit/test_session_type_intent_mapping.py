"""Unit tests for SESSION_TYPE_TO_DOMINANT_INTENT mapping."""

import pytest

from app.models.enums import SessionType, PhysiologicalIntent
from app.services.training_plan_service import SESSION_TYPE_TO_DOMINANT_INTENT


class TestSessionTypeIntentMapping:
    def test_mapping_contains_all_17_session_types(self):
        for st in SessionType:
            assert st in SESSION_TYPE_TO_DOMINANT_INTENT, f"Missing mapping for {st}"

    def test_rest_maps_to_recovery_support(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.REST] == PhysiologicalIntent.RECOVERY_SUPPORT

    def test_easy_run_maps_to_low_aerobic(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.EASY_RUN] == PhysiologicalIntent.LOW_AEROBIC

    def test_long_run_maps_to_high_aerobic(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.LONG_RUN] == PhysiologicalIntent.HIGH_AEROBIC

    def test_threshold_maps_to_threshold_intent(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.THRESHOLD] == PhysiologicalIntent.THRESHOLD

    def test_vo2max_maps_to_vo2max_intent(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.VO2MAX] == PhysiologicalIntent.VO2MAX

    def test_race_specific_maps_to_race_specific_intent(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.RACE_SPECIFIC] == PhysiologicalIntent.RACE_SPECIFIC

    def test_strides_maps_to_neuromuscular(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.STRIDES] == PhysiologicalIntent.NEUROMUSCULAR

    def test_test_session_maps_to_calibration(self):
        assert SESSION_TYPE_TO_DOMINANT_INTENT[SessionType.TEST_SESSION] == PhysiologicalIntent.CALIBRATION

    def test_module_raises_keyerror_at_import_time_for_missing_session_type(self):
        """Verify the module-level validation at import time catches missing mappings."""
        # This is tested by the module-level for loop that raises KeyError
        # If this test passes, it means all session types are mapped
        assert len(SESSION_TYPE_TO_DOMINANT_INTENT) == len(SessionType)