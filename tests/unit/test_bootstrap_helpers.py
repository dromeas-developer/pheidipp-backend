from datetime import date, datetime, timezone

from app.services.onboarding_service import (
    age_in_years,
    bootstrap_metric_confidence,
    bootstrap_signal,
)
from app.models.enums import TwinConfidenceLevel


class TestAgeInYears:
    def test_age_36_with_dob_1990_jan_15_and_now_2026_jul_25(self):
        dob = date(1990, 1, 15)
        now = datetime(2026, 7, 25, tzinfo=timezone.utc)
        assert age_in_years(dob, now) == 36

    def test_age_increments_on_birthday(self):
        dob = date(1990, 1, 15)
        day_before = datetime(2026, 1, 14, tzinfo=timezone.utc)
        day_of = datetime(2026, 1, 15, tzinfo=timezone.utc)
        assert age_in_years(dob, day_before) == 35
        assert age_in_years(dob, day_of) == 36

    def test_age_zero_for_newborn(self):
        today = datetime(2026, 7, 25, tzinfo=timezone.utc)
        assert age_in_years(date(2026, 7, 25), today) == 0


class TestBootstrapSignal:
    def test_returns_required_keys(self):
        sig = bootstrap_signal(
            value=150.0, observation_date=datetime(2026, 7, 25, tzinfo=timezone.utc)
        )
        assert "value" in sig
        assert "uncertainty" in sig
        assert "prior_weight" in sig
        assert "dominant_source" in sig
        assert "last_observation_date" in sig

    def test_prior_weight_is_05(self):
        sig = bootstrap_signal(
            value=150.0, observation_date=datetime(2026, 7, 25, tzinfo=timezone.utc)
        )
        assert sig["prior_weight"] == 0.5

    def test_uncertainty_is_1(self):
        sig = bootstrap_signal(
            value=150.0, observation_date=datetime(2026, 7, 25, tzinfo=timezone.utc)
        )
        assert sig["uncertainty"] == 1.0

    def test_dominant_source_is_questionnaire_estimate(self):
        sig = bootstrap_signal(
            value=150.0, observation_date=datetime(2026, 7, 25, tzinfo=timezone.utc)
        )
        assert sig["dominant_source"] == "questionnaire_estimate"

    def test_value_passed_through(self):
        sig = bootstrap_signal(
            value=123.45, observation_date=datetime(2026, 7, 25, tzinfo=timezone.utc)
        )
        assert sig["value"] == 123.45


class TestBootstrapMetricConfidence:
    def test_lt1_hr_is_low(self):
        mc = bootstrap_metric_confidence()
        assert mc["lt1_hr"] == TwinConfidenceLevel.LOW.value

    def test_lt2_hr_is_low(self):
        mc = bootstrap_metric_confidence()
        assert mc["lt2_hr"] == TwinConfidenceLevel.LOW.value

    def test_lt1_power_is_null(self):
        mc = bootstrap_metric_confidence()
        assert mc["lt1_power"] is None

    def test_lt1_pace_is_null(self):
        mc = bootstrap_metric_confidence()
        assert mc["lt1_pace"] is None

    def test_lt2_power_is_null(self):
        mc = bootstrap_metric_confidence()
        assert mc["lt2_power"] is None

    def test_lt2_pace_is_null(self):
        mc = bootstrap_metric_confidence()
        assert mc["lt2_pace"] is None

    def test_cp_is_null(self):
        mc = bootstrap_metric_confidence()
        assert mc["cp"] is None

    def test_only_lt1_hr_and_lt2_hr_are_low_rest_null(self):
        mc = bootstrap_metric_confidence()
        low_keys = {k for k, v in mc.items() if v == TwinConfidenceLevel.LOW.value}
        null_keys = {k for k, v in mc.items() if v is None}
        assert low_keys == {"lt1_hr", "lt2_hr"}
        assert null_keys == {"lt1_power", "lt1_pace", "lt2_power", "lt2_pace", "cp"}
