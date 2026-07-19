"""Gate activities for twin recalibration."""

from __future__ import annotations

from app.models.activity import Activity
from app.models.enums import SportType


class CalibrationEligibilityService:
    """Compute the Activity.calibration_eligible flag."""

    def evaluate(self, activity: Activity) -> bool:
        """Return calibration-eligibility decision for activity."""
        # Sport-type exclusion: non-running activities are excluded
        # from twin calibration (Principle #8).
        if activity.sport_type != SportType.RUNNING:
            return False

        return _evaluate_full_rules(activity)


def _evaluate_full_rules(activity: Activity) -> bool:
    """Phase-2.1 five-rule gate for calibration eligibility."""
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