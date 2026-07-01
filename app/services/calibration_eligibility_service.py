"""CalibrationEligibilityService — gate activities for twin recalibration.

Implements the Phase-1.6 contract from
``docs/architecture/02-computations/load-computation.md` →
``CalibrationEligibilityService``.

Phase-1.6 simplification:

* Per the plan, ALL sessions in this phase are
  ``calibration_eligible = false``. Threshold detection requires
  multiple sessions with the intensity variation needed for HR
  deflection / RR inflection algorithms; Phase 1.6 only has the
  heuristic load path.
* The gate is implemented and exposed for Phase 2 to plug in the
  full five-rule evaluation, but the rule outcome is currently
  hard-wired to ``False`` so the architecture invariant
  ("never manually overridden; set by CalibrationEligibilityService")
  is preserved — Phase-2 will flip the gate to honour the
  underlying rules without changing the call site.

Inputs:

* ``Activity`` row (carries ``has_hr``, ``duration_seconds``,
  ``quality_flags``, ``source``).
* ``source`` rules out ``manual_entry`` (manual sessions are never
  calibration-eligible — they have no FIT trace).
"""

from __future__ import annotations

from app.models.activity import Activity


class CalibrationEligibilityService:
    """Compute the ``Activity.calibration_eligible`` flag.

    Stateless per-request. The full five-rule gate from
    ``docs/architecture/02-computations/load-computation.md``
    lands in Phase 2; this phase returns ``False`` for every
    activity so the recalibration path is bounded.
    """

    PHASE_1_6_HARD_OFF = True

    def evaluate(self, activity: Activity) -> bool:
        """Return the calibration-eligibility decision for *activity*.

        Phase-1.6: always ``False``. The full rules
        ``has_hr AND source != manual_entry AND moving_duration >= 1200
        AND hr_dropout_pct <= 0.20 AND no gps_loss AND no
        sensor_malfunction AND usable_session_type`` are deferred
        to Phase 2; the gate is wired into the ingestion pipeline
        now so Phase 2 can flip the hard-off without touching the
        ingestion call sites.
        """
        if self.PHASE_1_6_HARD_OFF:
            return False
        # Phase-2 path (not active yet) — kept here so the future
        # rules do not get retro-fitted with a "always false" branch
        # left dangling.
        return _evaluate_full_rules(activity)


def _evaluate_full_rules(activity: Activity) -> bool:
    """Future Phase-2 gate — not active in Phase 1.6."""
    if activity.source.value == "manual_entry":
        return False
    if not activity.has_hr:
        return False
    if activity.duration_seconds < 1200:
        return False
    quality = activity.quality_flags or {}
    if quality.get("hr_dropout_pct") and quality["hr_dropout_pct"] > 0.20:
        return False
    if quality.get("gps_loss"):
        return False
    if quality.get("sensor_malfunction"):
        return False
    return True