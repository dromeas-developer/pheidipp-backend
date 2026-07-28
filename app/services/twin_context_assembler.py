"""Translate TwinState into coaching language."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    SportBackground,
    TwinConfidenceLevel,
)
from app.models.twin_state import TwinState


@dataclass(frozen=True)
class TwinContextSummary:
    """Coaching-ready translation of a TwinState snapshot."""

    readiness_level: RecoveryModifierLevel
    readiness_descriptor: str
    confidence_descriptor: str
    fitness_form_descriptor: str

    data_tier: DataTier
    confidence_level: TwinConfidenceLevel


_READINESS_DESCRIPTORS: dict[RecoveryModifierLevel, str] = {
    RecoveryModifierLevel.GREEN: "ready for full training load",
    RecoveryModifierLevel.AMBER: "navigating a partially recovered state",
    RecoveryModifierLevel.RED: "in a recovery window",
}

_CONFIDENCE_DESCRIPTORS: dict[TwinConfidenceLevel, str] = {
    TwinConfidenceLevel.LOW: "still learning your training history — thresholds are population-based estimates",
    TwinConfidenceLevel.MEDIUM: "building confidence in your personal thresholds from real training data",
    TwinConfidenceLevel.HIGH: "high confidence in your thresholds — multiple calibration data points received",
}


def _form_descriptor(form: float) -> str:
    """Return a narrative phrase for a Banister form score."""
    if form < -5.0:
        return "training load currently exceeds your aerobic capacity"
    if form < 5.0:
        return "training load and aerobic capacity roughly balanced"
    if form < 20.0:
        return "moderate fresh legs — recent training load is manageable"
    return "fresh and well-rested — accumulated fitness comfortably exceeds fatigue"


@dataclass(frozen=True)
class ComputedObservations:
    """Non-LLM observations the FirstMessageAgent references verbatim."""

    aerobic_base_assessment: str
    structural_risk_flag: bool
    structural_risk_reason: Optional[str]
    training_consistency_signal: Optional[str]


@dataclass(frozen=True)
class AthleteTwinContext:
    """Combined output of TwinContextAssembler.assemble."""

    twin_context: TwinContextSummary
    computed_observations: ComputedObservations


class TwinContextAssembler:
    """Translate TwinState + AthletePreferences into coaching language."""

    def assemble_twin_context(self, twin_state: TwinState) -> TwinContextSummary:
        """Return TwinContextSummary for twin_state."""
        return TwinContextSummary(
            readiness_level=twin_state.readiness_level,
            readiness_descriptor=_READINESS_DESCRIPTORS[twin_state.readiness_level],
            confidence_descriptor=_CONFIDENCE_DESCRIPTORS[twin_state.confidence_level],
            fitness_form_descriptor=_form_descriptor(twin_state.form),
            data_tier=DataTier(twin_state.data_tier),
            confidence_level=twin_state.confidence_level,
        )

    def compute_observations(
        self,
        *,
        twin_state: TwinState,
        sport_background: SportBackground,
        years_structured_training: int,
    ) -> ComputedObservations:
        """Compute non-LLM observations the FirstMessageAgent needs."""
        structural_risk_flag = sport_background != SportBackground.RUNNING_PRIMARY
        structural_risk_reason: str | None = None
        if structural_risk_flag:
            # Athletes whose primary sport is not running benefit from
            # an explicit ramp for impact/structural load. The
            # exact phrase ("non-running primary sport background")
            # matches the architecture spec.
            structural_risk_reason = "non-running primary sport background"

        return ComputedObservations(
            # At onboarding confidence is LOW, so the assessment is a
            # qualitative placeholder — Phase 2's threshold detection
            # refinements will tighten this once per-metric confidence
            # is populated by training data.
            aerobic_base_assessment=(
                "above-average for age group"
                if twin_state.confidence_level == TwinConfidenceLevel.HIGH
                else "limited running history on record — we'll refine the picture as you train"
            ),
            structural_risk_flag=structural_risk_flag,
            structural_risk_reason=structural_risk_reason,
            training_consistency_signal=(
                f"{years_structured_training} year(s) of structured training on record"
                if years_structured_training > 0
                else None
            ),
        )

    def assemble(
        self,
        *,
        twin_state: TwinState,
        sport_background: SportBackground,
        years_structured_training: int,
    ) -> AthleteTwinContext:
        """One-shot bundle combining summary + computed observations."""
        twin_context = self.assemble_twin_context(twin_state)
        computed_observations = self.compute_observations(
            twin_state=twin_state,
            sport_background=sport_background,
            years_structured_training=years_structured_training,
        )
        return AthleteTwinContext(
            twin_context=twin_context,
            computed_observations=computed_observations,
        )
