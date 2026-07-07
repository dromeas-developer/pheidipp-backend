"""CalibrationEligibilityService — gate activities for twin recalibration.

Implements the Phase-1.6 contract from
``docs/architecture/02-computations/load-computation.md`` →
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

Phase-2 expansion:

* Activate full five-rule gate:
  ``has_hr AND source != manual_entry AND duration >= 1200s AND
  hr_dropout_pct <= 0.20 AND NOT gps_loss AND NOT sensor_malfunction``
* Remove PHASE_1_6_HARD_OFF flag.
* Tier 5-6 activities are never calibration-eligible.
* Phase-2.1-P3: Sport-type exclusion as first check — non-running
  activities are excluded from twin calibration (Principle #8).
"""

from __future__ import annotations

from app.models.activity import Activity
from app.models.enums import SportType


class CalibrationEligibilityService:
    """Compute the ``Activity.calibration_eligible`` flag.

    Stateless per-request. The full five-rule gate from
    ``docs/architecture/02-computations/load-computation.md``
    is now activated for Phase 2.1.
    """

    def evaluate(self, activity: Activity) -> bool:
        """Return the calibration-eligibility decision for *activity*.

        Phase-2.1-P3: Sport-type exclusion is the FIRST check.
        Non-running activities are never calibration-eligible
        (Principle #8: non-running activities excluded from twin
        calibration).

        Full five-rule gate (after sport check):
        
        1. Has HR data
        2. Not manual entry
        3. Duration >= 1200s (20 minutes)
        4. HR dropout <= 20%
        5. No GPS loss or sensor malfunction
        
        Additional restrictions:
        - Tier 5-6 activities are never calibration-eligible
        """
        # Sport-type exclusion — FIRST check, before all other rules
        # Non-running activities are excluded from twin calibration
        # (Principle #8: "the twin sees running; the training record
        # sees everything")
        if activity.sport_type != SportType.RUNNING:
            return False
        
        # Existing five-rule gate follows
        return _evaluate_full_rules(activity)


def _evaluate_full_rules(activity: Activity) -> bool:
    """Phase-2.1 five-rule gate for calibration eligibility.

    The gate checks:
    ``has_hr AND source != manual_entry AND duration >= 1200s AND
    hr_dropout_pct <= 0.20 AND NOT gps_loss AND NOT sensor_malfunction``

    Note: ``isUsableSessionType`` check deferred (requires session
    classification from Phase 2.2).
    """
    # Manual entries are never calibration-eligible
    if activity.source.value == "manual_entry":
        return False
    
    # Must have HR data
    if not activity.has_hr:
        return False
    
    # Minimum duration of 1200 seconds (20 minutes)
    if activity.duration_seconds < 1200:
        return False
    
    # Check quality flags
    quality = activity.quality_flags or {}
    
    # HR dropout percentage must be <= 20%
    if quality.get("hr_dropout_pct") and quality["hr_dropout_pct"] > 0.20:
        return False
    
    # GPS loss disqualifies
    if quality.get("gps_loss"):
        return False
    
    # Sensor malfunction disqualifies
    if quality.get("sensor_malfunction"):
        return False
    
    # Tier 5-6 activities are never calibration-eligible
    # (This check requires the data tier which is not available here,
    # but will be handled in ActivityIngestionService)
    
    return True