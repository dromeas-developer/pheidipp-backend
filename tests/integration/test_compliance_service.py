"""Integration tests for ComplianceService.

ComplianceService.evaluate is a pure function — no database access. The
tests construct Activity and PlannedSession model instances directly
and assert on the returned ComplianceFindings. The integration
directory is the home of these tests because the service is wired into
the ingestion pipeline at runtime.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from app.models.activity import Activity
from app.models.enums import (
    ActivitySource,
    PlannedSessionStatus,
    SessionType,
    SportType,
)
from app.models.planned_session import PlannedSession
from app.services.compliance_service import ComplianceService


def _build_activity(
    *,
    duration_seconds: int = 3600,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    notes: str | None = None,
    planned_session_id: uuid.UUID | None = None,
) -> Activity:
    return Activity(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        planned_session_id=planned_session_id,
        source=source,
        external_id=None,
        activity_date=date(2026, 1, 1),
        start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
        duration_seconds=duration_seconds,
        sport_type=SportType.RUNNING,
        has_hr=True,
        has_gps=True,
        quality_flags={},
        fit_file_key="athlete/2026-01-01/x.fit",
        ingestion_pipeline_version="v1-simple-fit",
        notes=notes,
    )


def _build_planned_session(
    *,
    approximate_duration_minutes: int = 60,
    session_type: SessionType = SessionType.THRESHOLD,
) -> PlannedSession:
    ps = PlannedSession(
        id=uuid.uuid4(),
        training_plan_id=uuid.uuid4(),
        weekly_plan_id=uuid.uuid4(),
        week_number=1,
        session_type=session_type,
        status=PlannedSessionStatus.SCHEDULED,
    )
    ps.approximate_duration_minutes = approximate_duration_minutes
    return ps


class TestComplianceComparesActualToPlanned:
    def test_under_execution_shows_shorter_descriptor(self) -> None:
        service = ComplianceService()
        activity = _build_activity(duration_seconds=50 * 60)
        planned = _build_planned_session(approximate_duration_minutes=60)

        findings = service.evaluate(
            activity=activity, planned_session=planned
        )

        assert findings.has_prescribed_session is True
        assert findings.prescribed_session_id == planned.id
        assert "shorter" in findings.duration_delta_descriptor
        assert findings.duration_delta_pct < 0

    def test_over_execution_shows_longer_descriptor(self) -> None:
        service = ComplianceService()
        activity = _build_activity(duration_seconds=75 * 60)
        planned = _build_planned_session(approximate_duration_minutes=60)

        findings = service.evaluate(
            activity=activity, planned_session=planned
        )

        assert "longer" in findings.duration_delta_descriptor
        assert findings.duration_delta_pct > 0

    def test_within_tolerance_shows_match(self) -> None:
        service = ComplianceService()
        activity = _build_activity(duration_seconds=64 * 60)
        planned = _build_planned_session(approximate_duration_minutes=60)

        findings = service.evaluate(
            activity=activity, planned_session=planned
        )

        assert findings.duration_delta_descriptor == (
            "duration matched the prescription"
        )

    def test_session_type_match_for_fit_upload(self) -> None:
        service = ComplianceService()
        activity = _build_activity(source=ActivitySource.INTERVALS_ICU)
        planned = _build_planned_session(session_type=SessionType.THRESHOLD)

        findings = service.evaluate(
            activity=activity, planned_session=planned
        )

        assert findings.session_type_match is True


class TestComplianceWithoutPlannedSession:
    def test_no_planned_session_returns_zero_delta(self) -> None:
        service = ComplianceService()
        activity = _build_activity(duration_seconds=1800)

        findings = service.evaluate(activity=activity, planned_session=None)

        assert findings.has_prescribed_session is False
        assert findings.prescribed_session_id is None
        assert findings.duration_delta_pct == 0.0
        assert "no prescribed session" in findings.duration_delta_descriptor

    def test_no_planned_session_session_type_match_true(self) -> None:
        service = ComplianceService()
        activity = _build_activity()

        findings = service.evaluate(activity=activity, planned_session=None)

        assert findings.session_type_match is True
        assert "no prescribed session" in findings.session_type_descriptor

    def test_no_planned_session_preserves_athlete_notes(self) -> None:
        service = ComplianceService()
        activity = _build_activity(notes="felt strong today")

        findings = service.evaluate(activity=activity, planned_session=None)

        assert findings.athlete_notes == "felt strong today"
