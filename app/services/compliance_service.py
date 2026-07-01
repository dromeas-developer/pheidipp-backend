"""ComplianceService — compare actual session to prescribed session.

Implements the Phase-1.6 contract from
``docs/architecture/03-agents/post-workout-agent.md` →
``compliance`` sub-shape.

Phase-1.6 simplification:

* Only ``duration_delta_pct`` and ``session_type_match`` are
  computed at this phase. ``effort_delta`` and ``athlete_notes``
  surface as ``None`` (RPE capture and athlete notes are deferred
  to a later phase; the prompt handles both nulls gracefully per
  the architecture's "null handling rules").
* Pre-computed compliance findings are the input the
  :class:`PostWorkoutAgent` consumes. The agent never derives
  these from raw data — that is the Python layer's job per the
  architecture invariant.
* Output is plain-language so the LLM prompt receives a coaching-
  ready bundle rather than a numeric delta. The numeric value
  is preserved alongside for tests and downstream consumers.

Inputs:

* ``Activity`` row (the freshly ingested session) — carries
  ``duration_seconds`` and ``planned_session_id``.
* Optional ``PlannedSession`` (looked up via ``Activity.planned_session_id``).
  When the FK is ``None`` (unplanned / manual activity) the
  compliance payload reflects "no prescribed session".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from app.models.activity import Activity
from app.models.planned_session import PlannedSession


# ---------------------------------------------------------------------------
# Output dataclasses.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComplianceFindings:
    """Structured compliance payload consumed by ``PostWorkoutAgent``.

    Mirrors the ``compliance`` sub-shape from
    ``docs/architecture/03-agents/post-workout-agent.md``. Every
    field is plain-language so the prompt renders cleanly without
    numeric formatting.
    """

    duration_delta_pct: float
    duration_delta_descriptor: str
    session_type_match: bool
    session_type_descriptor: str
    effort_delta: Optional[str] = None
    athlete_notes: Optional[str] = None
    has_prescribed_session: bool = True
    prescribed_session_id: Optional[uuid.UUID] = None

    def to_dict(self) -> dict:
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


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class ComplianceError(Exception):
    """Base class for compliance-comparison failures."""


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class ComplianceService:
    """Compute compliance findings between an actual and prescribed session.

    Stateless per-request. The service is constructed without
    repositories because compliance is a pure-function over the two
    input rows — no DB I/O required.
    """

    DURATION_MATCH_TOLERANCE_PCT = 15.0

    def evaluate(
        self,
        *,
        activity: Activity,
        planned_session: Optional[PlannedSession],
    ) -> ComplianceFindings:
        """Return the :class:`ComplianceFindings` for ``activity``.

        When ``planned_session`` is ``None`` (manual activity,
        unplanned session, or unknown FK) the duration delta is
        reported as ``0.0`` (no comparison) and the session type
        match is ``True`` (no prescribed session to match against).
        """
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

        # Duration delta — actual vs prescribed (in minutes).
        actual_minutes = activity.duration_seconds / 60.0
        prescribed_minutes = planned_session.approximate_duration_minutes
        if prescribed_minutes <= 0:
            duration_delta_pct = 0.0
        else:
            duration_delta_pct = (
                (actual_minutes - prescribed_minutes) / prescribed_minutes
            ) * 100.0

        duration_descriptor = _describe_duration_delta(duration_delta_pct)

        # Session-type match.
        session_type_match = activity.source.value != "manual_entry" or (
            # For manual_entry the session_type is not in the FIT
            # trace; treat as matching only when the prescribed
            # session type is null or "rest".
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


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _describe_duration_delta(delta_pct: float) -> str:
    """Return a plain-language descriptor for a duration delta.

    Buckets match the coaching voice: the post-workout agent uses
    ``duration_delta_descriptor`` verbatim when narrating paragraph 1.
    """
    if abs(delta_pct) <= ComplianceService.DURATION_MATCH_TOLERANCE_PCT:
        return "duration matched the prescription"
    if delta_pct > 0:
        return f"ran {abs(delta_pct):.0f}% longer than prescribed"
    return f"finished {abs(delta_pct):.0f}% shorter than prescribed"