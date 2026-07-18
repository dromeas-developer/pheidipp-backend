"""Unit tests for ComplianceService.

Compares actual Activity session to prescribed PlannedSession and produces
ComplianceFindings with duration_delta_pct and session_type_match.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.activity import Activity
from app.models.enums import ActivitySource, SessionType
from app.models.planned_session import PlannedSession
from app.services.compliance_service import (
    ComplianceService,
)


def _activity_factory(
    *,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    duration_seconds: int = 3600,
    notes: str | None = None,
) -> Activity:
    """Build a MagicMock Activity with properly set attributes.

    MagicMock(spec=Activity)(...) does NOT set attributes — it calls the
    mock as a callable. We must configure attributes explicitly.
    """
    mock_activity = MagicMock(spec=Activity)
    mock_activity.id = uuid.uuid4()
    mock_activity.athlete_id = uuid.uuid4()
    mock_activity.planned_session_id = None
    mock_activity.source = source
    mock_activity.activity_date = date(2026, 6, 15)
    mock_activity.start_time = datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)
    mock_activity.duration_seconds = duration_seconds
    mock_activity.aerobic_load = None
    mock_activity.neuromuscular_load = None
    mock_activity.structural_load = None
    mock_activity.has_hr = True
    mock_activity.has_rr_intervals = False
    mock_activity.has_power = False
    mock_activity.calibration_eligible = False
    mock_activity.quality_flags = {}
    mock_activity.fit_file_key = "fit-files/test/uuid.fit"
    mock_activity.ingestion_pipeline_version = "v1-simple-fit"
    mock_activity.cleaning_pipeline_version = None
    mock_activity.notes = notes
    return mock_activity


def _planned_session_factory(
    *,
    session_type: SessionType = SessionType.LONG_RUN,
    approximate_duration_minutes: float = 60.0,
) -> PlannedSession:
    """Build a MagicMock PlannedSession with properly set attributes.

    MagicMock(spec=PlannedSession)(...) does NOT set attributes — it calls
    the mock as a callable. We must configure attributes explicitly.
    """
    mock_session = MagicMock(spec=PlannedSession)
    mock_session.id = uuid.uuid4()
    mock_session.athlete_id = uuid.uuid4()
    mock_session.week_number = 1
    mock_session.phase_label = MagicMock(value="base")
    mock_session.session_type = session_type
    mock_session.approximate_duration_minutes = approximate_duration_minutes
    return mock_session


class TestComplianceServiceNoPrescribedSession:
    """When planned_session is None (manual / unplanned activity)."""

    def test_has_prescribed_session_is_false(self) -> None:
        service = ComplianceService()
        activity = _activity_factory()
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.has_prescribed_session is False

    def test_duration_delta_pct_is_zero(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=600)
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.duration_delta_pct == 0.0

    def test_session_type_match_is_true(self) -> None:
        """No prescribed session to compare against — always matches."""
        service = ComplianceService()
        activity = _activity_factory()
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.session_type_match is True

    def test_session_type_descriptor_no_prescribed(self) -> None:
        service = ComplianceService()
        activity = _activity_factory()
        findings = service.evaluate(activity=activity, planned_session=None)
        assert "no prescribed session" in findings.session_type_descriptor.lower()

    def test_prescribed_session_id_is_none(self) -> None:
        service = ComplianceService()
        activity = _activity_factory()
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.prescribed_session_id is None

    def test_effort_delta_is_none(self) -> None:
        """effort_delta is not computed in Phase 1.6."""
        service = ComplianceService()
        activity = _activity_factory()
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.effort_delta is None

    def test_athlete_notes_passed_through(self) -> None:
        """Activity.notes is passed to ComplianceFindings."""
        service = ComplianceService()
        activity = _activity_factory(notes="Felt strong today")
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.athlete_notes == "Felt strong today"

    def test_athlete_notes_none_passed_through(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(notes=None)
        findings = service.evaluate(activity=activity, planned_session=None)
        assert findings.athlete_notes is None


class TestComplianceServiceDurationDelta:
    """Duration delta computation: (actual - prescribed) / prescribed * 100."""

    def test_exact_match_returns_zero_delta(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=3600)  # 60 minutes
        planned = _planned_session_factory(approximate_duration_minutes=60.0)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.duration_delta_pct == 0.0

    def test_10_percent_longer(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=3960)  # 66 minutes
        planned = _planned_session_factory(approximate_duration_minutes=60.0)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.duration_delta_pct == pytest.approx(10.0, abs=0.5)

    def test_20_percent_shorter(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=2880)  # 48 minutes
        planned = _planned_session_factory(approximate_duration_minutes=60.0)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.duration_delta_pct == pytest.approx(-20.0, abs=0.5)

    def test_zero_prescribed_duration_returns_zero_delta(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=3600)
        planned = _planned_session_factory(approximate_duration_minutes=0.0)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.duration_delta_pct == 0.0

    def test_negative_prescribed_duration_returns_zero_delta(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=3600)
        planned = _planned_session_factory(approximate_duration_minutes=-10.0)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.duration_delta_pct == 0.0

    def test_duration_descriptor_within_15_percent_is_matched(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=3600)  # 60 min
        planned = _planned_session_factory(approximate_duration_minutes=55.0)  # ~9% off
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert "matched" in findings.duration_delta_descriptor.lower()

    def test_duration_descriptor_too_long(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=5400)  # 90 min
        planned = _planned_session_factory(approximate_duration_minutes=60.0)  # 50% longer
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert "longer" in findings.duration_delta_descriptor.lower()

    def test_duration_descriptor_too_short(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(duration_seconds=2400)  # 40 min
        planned = _planned_session_factory(approximate_duration_minutes=60.0)  # 33% shorter
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert "shorter" in findings.duration_delta_descriptor.lower()


class TestComplianceServiceSessionTypeMatch:
    """Session type matching logic."""

    def test_non_manual_entry_matches_prescribed(self) -> None:
        """For non-manual_entry sources, session type always matches the prescription."""
        service = ComplianceService()
        activity = _activity_factory(source=ActivitySource.MANUAL_UPLOAD)
        planned = _planned_session_factory(session_type=SessionType.LONG_RUN)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.session_type_match is True

    def test_manual_entry_with_non_rest_session_type_does_not_match(self) -> None:
        """manual_entry source cannot verify session type, so non-rest prescriptions don't match."""
        service = ComplianceService()
        activity = _activity_factory(source=ActivitySource.MANUAL_ENTRY)
        planned = _planned_session_factory(session_type=SessionType.LONG_RUN)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.session_type_match is False

    def test_manual_entry_with_rest_matches(self) -> None:
        """manual_entry with rest session type matches (no trace to verify)."""
        service = ComplianceService()
        activity = _activity_factory(source=ActivitySource.MANUAL_ENTRY)
        planned = _planned_session_factory(session_type=SessionType.REST)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert findings.session_type_match is True

    def test_session_type_descriptor_non_match(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(source=ActivitySource.MANUAL_ENTRY)
        planned = _planned_session_factory(session_type=SessionType.THRESHOLD)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert "did not match" in findings.session_type_descriptor.lower()
        assert "threshold" in findings.session_type_descriptor.lower()

    def test_session_type_descriptor_match(self) -> None:
        service = ComplianceService()
        activity = _activity_factory(source=ActivitySource.MANUAL_UPLOAD)
        planned = _planned_session_factory(session_type=SessionType.TEMPO)
        findings = service.evaluate(activity=activity, planned_session=planned)
        assert "matched" in findings.session_type_descriptor.lower()


class TestComplianceFindingsToDict:
    """ComplianceFindings.to_dict() serialisation for LLM prompt rendering."""

    def test_serialises_all_fields(self) -> None:
        service = ComplianceService()
        activity = _activity_factory()
        planned = _planned_session_factory()
        findings = service.evaluate(activity=activity, planned_session=planned)
        d = findings.to_dict()
        assert "duration_delta_pct" in d
        assert "duration_delta_descriptor" in d
        assert "session_type_match" in d
        assert "session_type_descriptor" in d
        assert "effort_delta" in d
        assert "athlete_notes" in d
        assert "has_prescribed_session" in d
        assert "prescribed_session_id" in d

    def test_prescribed_session_id_serialised_as_string(self) -> None:
        service = ComplianceService()
        activity = _activity_factory()
        planned = _planned_session_factory()
        findings = service.evaluate(activity=activity, planned_session=planned)
        d = findings.to_dict()
        assert d["prescribed_session_id"] == str(planned.id)

    def test_prescribed_session_id_none_serialised_as_none(self) -> None:
        service = ComplianceService()
        activity = _activity_factory()
        findings = service.evaluate(activity=activity, planned_session=None)
        d = findings.to_dict()
        assert d["prescribed_session_id"] is None