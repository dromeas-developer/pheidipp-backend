"""Compare actual session to prescribed session."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Optional

from app.models.activity import Activity
from app.models.planned_session import PlannedSession


@dataclass(frozen=True)
class ComplianceFindings:
    """Structured compliance payload consumed by PostWorkoutAgent."""

    duration_delta_pct: float
    duration_delta_descriptor: str
    session_type_match: bool
    session_type_descriptor: str
    effort_delta: Optional[str] = None
    athlete_notes: Optional[str] = None
    has_prescribed_session: bool = True
    prescribed_session_id: Optional[uuid.UUID] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict for prompt rendering."""
        return {
            "duration_delta_pct": self.duration_delta_pct,
            "duration_delta_descriptor": self.duration_delta_descriptor,
            "session_type_match": self.session_type_match,
            "session_type_descriptor": self.session_type_descriptor,
            "effort_delta": self.effort_delta,
            "athlete_notes": self.athlete_notes,
            "has_prescribed_session": self.has_prescribed_session,
            "prescribed_session_id": (
                str(self.prescribed_session_id)
                if self.prescribed_session_id is not None
                else None
            ),
        }


class ComplianceError(Exception):
    """Base class for compliance-comparison failures."""


class ComplianceService:
    """Compute compliance findings between actual and prescribed session."""

    DURATION_MATCH_TOLERANCE_PCT = 15.0

    def evaluate(
        self,
        *,
        activity: Activity,
        planned_session: Optional[PlannedSession],
    ) -> ComplianceFindings:
        """Return ComplianceFindings for activity."""
        if planned_session is None:
            return ComplianceFindings(
                duration_delta_pct=0.0,
                duration_delta_descriptor=(
                    "no prescribed session — actual duration retained as-is"
                ),
                session_type_match=True,
                session_type_descriptor=(
                    "no prescribed session to compare against"
                ),
                effort_delta=None,
                athlete_notes=activity.notes,
                has_prescribed_session=False,
                prescribed_session_id=None,
            )

        actual_minutes = activity.duration_seconds / 60.0
        prescribed_minutes = planned_session.approximate_duration_minutes
        if prescribed_minutes <= 0:
            duration_delta_pct = 0.0
        else:
            duration_delta_pct = (
                (actual_minutes - prescribed_minutes) / prescribed_minutes
            ) * 100.0

        duration_descriptor = _describe_duration_delta(duration_delta_pct)

        session_type_match = activity.source.value != "manual_entry" or (
            planned_session.session_type.value in {"rest"}
        )
        session_type_descriptor = (
            f"session matched the prescribed {planned_session.session_type.value}"
            if session_type_match
            else f"session type did not match the prescribed {planned_session.session_type.value}"
        )

        return ComplianceFindings(
            duration_delta_pct=round(duration_delta_pct, 2),
            duration_delta_descriptor=duration_descriptor,
            session_type_match=session_type_match,
            session_type_descriptor=session_type_descriptor,
            effort_delta=None,
            athlete_notes=activity.notes,
            has_prescribed_session=True,
            prescribed_session_id=planned_session.id,
        )


def _describe_duration_delta(delta_pct: float) -> str:
    """Return plain-language descriptor for a duration delta."""
    if abs(delta_pct) <= ComplianceService.DURATION_MATCH_TOLERANCE_PCT:
        return "duration matched the prescription"
    if delta_pct > 0:
        return f"ran {abs(delta_pct):.0f}% longer than prescribed"
    return f"finished {abs(delta_pct):.0f}% shorter than prescribed"