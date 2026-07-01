"""Unit tests for CalibrationEligibilityService.

Phase-1.6 simplification: all activities return calibration_eligible=False
because threshold detection requires multiple sessions with specific
structure (deferred to Phase 2).

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest

from app.models.activity import Activity
from app.models.enums import ActivitySource
from app.services.calibration_eligibility_service import (
    CalibrationEligibilityService,
)


def _activity_factory(
    *,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    has_hr: bool = True,
    duration_seconds: int = 3600,
    quality_flags: dict | None = None,
) -> Activity:
    """Create an Activity instance for testing."""
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
        calibration_eligible=False,
        quality_flags=quality_flags or {},
        fit_file_key="fit-files/test/uuid.fit",
        ingestion_pipeline_version="v1-simple-fit",
    )


class TestCalibrationEligibilityPhase16HardOff:
    """Phase-1.6: PHASE_1_6_HARD_OFF=True — all activities return False."""

    def test_manual_upload_returns_false(self) -> None:
        """manual_upload activities are not calibration-eligible in Phase 1.6."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(source=ActivitySource.MANUAL_UPLOAD)
        assert service.evaluate(activity) is False

    def test_intervals_icu_returns_false(self) -> None:
        """intervals_icu activities are not calibration-eligible in Phase 1.6."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(source=ActivitySource.INTERVALS_ICU)
        assert service.evaluate(activity) is False

    def test_garmin_direct_returns_false(self) -> None:
        """garmin_direct activities are not calibration-eligible in Phase 1.6."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(source=ActivitySource.GARMIN_DIRECT)
        assert service.evaluate(activity) is False

    def test_manual_entry_returns_false(self) -> None:
        """manual_entry activities are not calibration-eligible (no FIT trace)."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(source=ActivitySource.MANUAL_ENTRY)
        assert service.evaluate(activity) is False

    def test_activity_without_hr_returns_false(self) -> None:
        """Activities without HR data are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(has_hr=False)
        assert service.evaluate(activity) is False

    def test_short_duration_returns_false(self) -> None:
        """Activities under 20 minutes are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(duration_seconds=600)  # 10 minutes
        assert service.evaluate(activity) is False

    def test_activity_with_hr_dropout_returns_false(self) -> None:
        """Activities with excessive HR dropout are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            quality_flags={"hr_dropout_pct": 0.25}  # > 20% dropout
        )
        assert service.evaluate(activity) is False

    def test_activity_with_gps_loss_returns_false(self) -> None:
        """Activities with GPS loss are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(quality_flags={"gps_loss": True})
        assert service.evaluate(activity) is False

    def test_activity_with_sensor_malfunction_returns_false(self) -> None:
        """Activities with sensor malfunction are not calibration-eligible."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(quality_flags={"sensor_malfunction": True})
        assert service.evaluate(activity) is False

    def test_ideal_activity_returns_false(self) -> None:
        """Even an ideal activity (HR, long duration, no quality issues)
        returns False in Phase 1.6 because the gate is hard-wired off."""
        service = CalibrationEligibilityService()
        activity = _activity_factory(
            source=ActivitySource.GARMIN_DIRECT,
            has_hr=True,
            duration_seconds=3600,
            quality_flags={},
        )
        assert service.evaluate(activity) is False

    def test_gate_is_hard_wired_not_conditional(self) -> None:
        """Verify PHASE_1_6_HARD_OFF is True — the gate is hard-wired,
        not just the default."""
        service = CalibrationEligibilityService()
        assert service.PHASE_1_6_HARD_OFF is True