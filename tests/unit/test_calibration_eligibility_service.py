"""Unit tests for CalibrationEligibilityService.

Phase-2.1: Full five-rule gate activated.
Rule 1: Has HR data
Rule 2: Not manual entry
Rule 3: Duration >= 1200s (20 minutes)
Rule 4: HR dropout <= 20%
Rule 5: No GPS loss or sensor malfunction

Additional constraint: Tier 5-6 activities are never calibration-eligible
(handled at the service layer, not in evaluate() itself).

Reference: docs/release-plan/phase-2/phase-2-1-fit-ingestion-pipeline-expansion.md
docs/architecture/01-entities/activity.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from app.services.calibration_eligibility_service import (
    CalibrationEligibilityService,
)


def _activity_factory(
    *,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    has_hr: bool = True,
    duration_seconds: int = 3600,
    quality_flags: dict | None = None,
    sport_type: str = "running",
) -> Activity:
    """Create an Activity instance for testing the five-rule gate."""
    return Activity(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        source=source,
        activity_date=date(2026, 6, 15),
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration_seconds,
        has_hr=has_hr,
        has_rr_intervals=False,
        has_power=False,
        has_gps=False,
        calibration_eligible=False,
        quality_flags=quality_flags or {},
        fit_file_key="fit-files/test/uuid.fit",
        ingestion_pipeline_version="v1-simple-fit",
        sport_type=SportType(sport_type),
    )


class TestCalibrationEligibilityFiveRuleGate:
    """Phase-2.1: Five-rule gate evaluates properly (no hard-off)."""

    def test_manual_entry_returns_false(self) -> None:
        """Rule 2: manual_entry is never calibration-eligible (no FIT trace)."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(source=ActivitySource.MANUAL_ENTRY)
        assert service.evaluate(activity) is False

    def test_missing_hr_returns_false(self) -> None:
        """Rule 1: Activities without HR data are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(has_hr=False)
        assert service.evaluate(activity) is False

    def test_short_duration_returns_false(self) -> None:
        """Rule 3: Activities under 20 minutes are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(duration_seconds=600)  # 10 minutes
        assert service.evaluate(activity) is False

    def test_exactly_20_minutes_is_eligible(self) -> None:
        """Rule 3: Duration exactly 1200s (20 minutes) is eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=1200,
            quality_flags={},
        )
        assert service.evaluate(activity) is True

    def test_hr_dropout_exceeds_20_percent_returns_false(self) -> None:
        """Rule 4: HR dropout > 20% disqualifies."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            quality_flags={"hr_dropout_pct": 0.25}  # > 20%
        )
        assert service.evaluate(activity) is False

    def test_hr_dropout_at_20_percent_is_eligible(self) -> None:
        """Rule 4: HR dropout exactly 20% is eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={"hr_dropout_pct": 0.20},
        )
        assert service.evaluate(activity) is True

    def test_hr_dropout_below_20_percent_is_eligible(self) -> None:
        """Rule 4: HR dropout < 20% passes."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={"hr_dropout_pct": 0.10},
        )
        assert service.evaluate(activity) is True

    def test_gps_loss_returns_false(self) -> None:
        """Rule 5: GPS loss disqualifies."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            quality_flags={"gps_loss": True}
        )
        assert service.evaluate(activity) is False

    def test_sensor_malfunction_returns_false(self) -> None:
        """Rule 5: Sensor malfunction disqualifies."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            quality_flags={"sensor_malfunction": True}
        )
        assert service.evaluate(activity) is False

    def test_ideal_activity_passes_all_rules(self) -> None:
        """All five rules pass → calibration_eligible = True."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is True

    def test_intervals_icu_source_is_eligible_when_otherwise_valid(self) -> None:
        """Rule 2: intervals_icu source is eligible (not manual_entry)."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.INTERVALS_ICU,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is True

    def test_manual_upload_source_is_eligible_when_otherwise_valid(self) -> None:
        """Rule 2: manual_upload source is eligible (not manual_entry)."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.MANUAL_UPLOAD,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is True

    def test_multiple_quality_issues_are_all_checked(self) -> None:
        """When multiple issues exist, first checked returns False."""
        service = CalibrationEligibilityService()
        # HR dropout AND gps_loss — would fail on first check (hr_dropout)
        activity = _activity_factory(
            duration_seconds=3600,
            quality_flags={"hr_dropout_pct": 0.30, "gps_loss": True},
        )
        assert service.evaluate(activity) is False

    def test_intervals_icu_with_long_duration_and_no_quality_issues(self) -> None:
        """Full valid intervals_icu session passes."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.INTERVALS_ICU,
            has_hr=True,
            duration_seconds=5400,  # 90 minutes
            quality_flags={"hr_dropout_pct": 0.05},
        )
        assert service.evaluate(activity) is True


class TestCalibrationEligibilityTier56Override:
    """Tier 5-6 override is applied at the ingestion service layer.

    CalibrationEligibilityService.evaluate() returns True for eligible
    sessions; the override to False for Tier 5-6 happens in
    ActivityIngestionService._run_ingestion_pipeline() after data_tier
    is inferred from athlete preferences.
    """

    def test_service_does_not_have_tier_check(self) -> None:
        """The service evaluates rules only; Tier override is ingestion-layer."""
        service = CalibrationEligibilityService()
        # An activity that passes all five rules
        activity = _activity_factory(
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        # Service should return True (Tier check is not in the service)
        assert service.evaluate(activity) is True


class TestCalibrationEligibilitySportTypeGate:
    """Phase-2.1-P3: Sport-type exclusion is the FIRST check in the calibration gate.

    Architecture invariant: "Non-running activities are excluded from twin
    calibration" (principles invariant #8). The sport-type check runs before
    all other rules — an activity with sport_type != 'running' returns False
    immediately, regardless of HR/duration/quality flags.

    Reference: docs/implementation/phase-2/phase-2-1-p3-sport-type-filtering.md
    """

    def _activity_with_sport(
        self,
        sport_type: str,
        source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
        has_hr: bool = True,
        duration_seconds: int = 3600,
        quality_flags: dict | None = None,
    ) -> Activity:
        """Factory for activities with a sport_type attribute."""
        activity = _activity_factory(
            source=source,
            has_hr=has_hr,
            duration_seconds=duration_seconds,
            quality_flags=quality_flags,
        )
        # Set sport_type via the attribute (model must support it)
        activity.sport_type = sport_type
        return activity

    def test_running_passes_when_all_other_rules_met(self) -> None:
        """Running activity that passes all five rules → calibration_eligible=true."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="running",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is True

    def test_cycling_returns_false_regardless_of_hr(self) -> None:
        """sport_type='cycling' → calibration_eligible=false even with perfect HR."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="cycling",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        # Sport gate returns False immediately — other rules not evaluated
        assert service.evaluate(activity) is False

    def test_swimming_returns_false(self) -> None:
        """sport_type='swimming' → calibration_eligible=false."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="swimming",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is False

    def test_unknown_sport_returns_false(self) -> None:
        """sport_type='unknown' → calibration_eligible=false."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="unknown",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is False

    def test_strength_returns_false(self) -> None:
        """sport_type='strength' → calibration_eligible=false."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="strength",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is False

    def test_other_returns_false(self) -> None:
        """sport_type='other' → calibration_eligible=false."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="other",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is False

    def test_yoga_mobility_returns_false(self) -> None:
        """sport_type='yoga_mobility' → calibration_eligible=false."""
        service = CalibrationEligibilityService()
        activity = self._activity_with_sport(
            sport_type="yoga_mobility",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is False

    def test_sport_check_runs_before_other_rules(self) -> None:
        """Sport check is first — a cycling activity passing all five rules is
        rejected by the sport gate, not by the five rules."""
        service = CalibrationEligibilityService()
        # Cycling + perfect HR + perfect duration + no quality issues =
        # would pass all five rules if sport weren't checked first
        activity = self._activity_with_sport(
            sport_type="cycling",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={"hr_dropout_pct": 0.30, "gps_loss": True},
        )
        # Result is False from sport gate, not from the quality flags
        assert service.evaluate(activity) is False
        # Even if we fix the quality issues, sport gate still rejects
        activity_fixed = self._activity_with_sport(
            sport_type="cycling",
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity_fixed) is False