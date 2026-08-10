"""Unit tests for CalibrationEligibilityService — pure gate, no DB.

The service evaluates an Activity ORM instance but performs no database
access, so tests construct in-memory Activity objects directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, date

import pytest

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from app.services.calibration_eligibility_service import (
    CalibrationEligibilityService,
)


@pytest.fixture
def service() -> CalibrationEligibilityService:
    return CalibrationEligibilityService()


def _build_activity(
    *,
    sport_type: SportType = SportType.RUNNING,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    has_hr: bool = True,
    duration_seconds: int = 1800,
    quality_flags: dict[str, object] | None = None,
) -> Activity:
    return Activity(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        source=source,
        external_id=None,
        activity_date=date(2026, 1, 1),
        start_time=datetime(2026, 1, 1, 8, 0, 0),
        duration_seconds=duration_seconds,
        sport_type=sport_type,
        sport_type_detection_version="v1",
        aerobic_load=None,
        neuromuscular_load=None,
        structural_load=None,
        has_hr=has_hr,
        has_rr_intervals=False,
        has_power=False,
        has_gps=False,
        calibration_eligible=False,
        quality_flags=quality_flags or {},
        fit_file_key=None,
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version=None,
        notes=None,
    )


class TestCalibrationEligibilityGate:
    def test_all_conditions_met_returns_true(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity()

        assert service.evaluate(activity) is True

    def test_non_running_sport_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(sport_type=SportType.CYCLING)

        assert service.evaluate(activity) is False

    def test_no_hr_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(has_hr=False)

        assert service.evaluate(activity) is False

    def test_manual_entry_source_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(source=ActivitySource.MANUAL_ENTRY)

        assert service.evaluate(activity) is False

    def test_duration_below_1200_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(duration_seconds=1199)

        assert service.evaluate(activity) is False

    def test_duration_at_1200_boundary_returns_true(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(duration_seconds=1200)

        assert service.evaluate(activity) is True

    def test_duration_above_1200_returns_true(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(duration_seconds=1201)

        assert service.evaluate(activity) is True

    def test_hr_dropout_above_20_percent_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(quality_flags={"hr_dropout_pct": 0.21})

        assert service.evaluate(activity) is False

    def test_hr_dropout_at_20_percent_boundary_returns_true(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(quality_flags={"hr_dropout_pct": 0.20})

        assert service.evaluate(activity) is True

    def test_hr_dropout_below_20_percent_returns_true(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(quality_flags={"hr_dropout_pct": 0.10})

        assert service.evaluate(activity) is True

    def test_gps_loss_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(quality_flags={"gps_loss": True})

        assert service.evaluate(activity) is False

    def test_sensor_malfunction_returns_false(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(quality_flags={"sensor_malfunction": True})

        assert service.evaluate(activity) is False

    def test_null_quality_flags_evaluates_as_eligible(
        self,
        service: CalibrationEligibilityService,
    ) -> None:
        activity = _build_activity(quality_flags=None)

        assert service.evaluate(activity) is True
