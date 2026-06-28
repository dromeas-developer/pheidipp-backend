"""TwinContextAssembler — translate ``TwinState`` into coaching language.

Deterministic computation (no LLM calls). Per the plan and the
architecture's principle "Python computes, LLM narrates", this service
turns raw ``TwinState`` integer / enum fields into the
coaching-relevant language and descriptors consumed by the
``FirstMessageAgent`` and (later) other agents via
``ContextBudgetService``.

Invariants:

* The assembler never raises on ``None`` threshold values. At
  onboarding ``TwinState.lt1_*, lt2_*, cp_*`` are commonly ``None``
  because the twin was bootstrapped from population priors; the
  first-message prompt explicitly addresses those by name.
* The assembler never modifies the source ``TwinState`` — it only
  reads its inline values.
* The output is a plain dataclass (``TwinContextSummary``) so
  ``ContextBudgetService`` can serialise it through the priority-
  weighted truncation logic without ORM session coupling.
"""

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


# ---------------------------------------------------------------------------
# Output contract — ``TwinContextSummary``.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TwinContextSummary:
    """Coaching-ready translation of a ``TwinState`` snapshot.

    Mirrors the shape declared in
    ``docs/architecture/02-computations/twin-context-assembler.md``.
    Fields are intentionally flat (no nested ``IntentRange`` etc.)
    because the ``FirstMessageAgent`` only requires the textual
    descriptors at this point; richer numerical targets belong to
    ``WorkoutGenerationAgent`` and ``PostWorkoutAgent``.
    """

    # Readiness
    readiness_level: RecoveryModifierLevel
    readiness_descriptor: str
    confidence_descriptor: str
    fitness_form_descriptor: str

    # Data tier — raw int preserved for downstream consumers that
    # need it; rendered as ``Athlete data tier: N`` inside the
    # context builder too.
    data_tier: DataTier
    confidence_level: TwinConfidenceLevel


# ---------------------------------------------------------------------------
# Translation tables — lattice constants from the architecture.
# ---------------------------------------------------------------------------


#: Source: ``docs/architecture/01-entities/twin-state.md`` →
#: ``RecoveryModifierLevel = 'green' | 'amber' | 'red'``. Plain English
#: so the LLM receives a coaching-friendly phrase; numeric modifiers
#: are deliberately avoided per the "no raw numbers without
#: context" voice rule.
_READINESS_DESCRIPTORS: dict[RecoveryModifierLevel, str] = {
    RecoveryModifierLevel.GREEN: "ready for full training load",
    RecoveryModifierLevel.AMBER: "navigating a partially recovered state",
    RecoveryModifierLevel.RED: "in a recovery window",
}


#: Source: ``docs/architecture/00-foundations/confidence-model.md`` →
#: ``TwinConfidenceLevel`` — descriptive copy matches the agent-side
#: rule "Tier 3 language tier at LOW confidence"
#: (``docs/vision/twin/confidence-and-uncertainty.md`` referenced in
#: the Phase-1.5a plan).
_CONFIDENCE_DESCRIPTORS: dict[TwinConfidenceLevel, str] = {
    TwinConfidenceLevel.LOW: "still learning your training history — thresholds are population-based estimates",
    TwinConfidenceLevel.MEDIUM: "building confidence in your personal thresholds from real training data",
    TwinConfidenceLevel.HIGH: "high confidence in your thresholds — multiple calibration data points received",
}


#: Fitness / form descriptor — narrative translation of
#: ``fitness - fatigue`` (``TwinState.form`` field, inline snapshot).
#: The crossover "structural capacity" insight referenced in
#: ``FirstMessageAgent.computed_observations.structural_risk_reason``
#: lives in :meth:`TwinContextAssembler.compute_observations`.
def _form_descriptor(form: float) -> str:
    """Return a narrative phrase for a Banister ``form`` score.

    The numeric regions below are placeholders anchored to the
    architecture's confidence tiers (LOW / MEDIUM / HIGH) rather than
    being a Banister-decoded score. Calibration against real Banister
    output lands in Phase 2 — the descriptor is intentionally
    qualitative so a regime change there does not require a prompt
    rewrite.
    """
    if form < -5.0:
        return "training load currently exceeds your aerobic capacity"
    if form < 5.0:
        return "training load and aerobic capacity roughly balanced"
    if form < 20.0:
        return "moderate fresh legs — recent training load is manageable"
    return "fresh and well-rested — accumulated fitness comfortably exceeds fatigue"


# ---------------------------------------------------------------------------
# Computed observations — derived from twin + preferences but never
# computed inside the LLM. The first-message required fields
# ``structural_risk_flag`` etc. live here per
# ``docs/architecture/03-agents/first-message-agent.md``.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ComputedObservations:
    """Non-LLM observations the FirstMessageAgent references verbatim."""

    aerobic_base_assessment: str
    structural_risk_flag: bool
    structural_risk_reason: Optional[str]
    training_consistency_signal: Optional[str]


@dataclass(frozen=True)
class AthleteTwinContext:
    """Combined output of :meth:`TwinContextAssembler.assemble`.

    Holds the :class:`TwinContextSummary` plus the
    :class:`ComputedObservations` so :class:`ContextBudgetService`
    can emit a single bundle without re-fetching repositories.
    """

    twin_context: TwinContextSummary
    computed_observations: ComputedObservations


# ---------------------------------------------------------------------------
# Public service.
# ---------------------------------------------------------------------------


class TwinContextAssembler:
    """Translate ``TwinState`` + ``AthletePreferences`` into coaching language.

    The assembler is constructed without state and is safe to
    instantiate per-request — there is no expensive lazy load.
    """

    def assemble_twin_context(
        self, twin_state: TwinState
    ) -> TwinContextSummary:
        """Return the :class:`TwinContextSummary` for ``twin_state``."""
        return TwinContextSummary(
            readiness_level=twin_state.readiness_level,
            readiness_descriptor=_READINESS_DESCRIPTORS[
                twin_state.readiness_level
            ],
            confidence_descriptor=_CONFIDENCE_DESCRIPTORS[
                twin_state.confidence_level
            ],
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
        """Compute the non-LLM observations the FirstMessageAgent needs.

        Parameters
        ----------
        twin_state:
            Latest ``TwinState`` snapshot for the athlete. The inline
            ``confidence_level``, ``data_tier`` and ``form`` are read;
            threshold values are not required here because the
            aerobic-base assessment is derived from prior weight via
            ``metric_confidence``.
        sport_background, years_structured_training:
            Required structural-risk and consistency inputs because
            they live on ``AthletePreferences`` (not on
            ``TwinState``). Callers must supply them explicitly so
            this service has no hidden dependency on a particular
            repository signature.
        """
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
        """One-shot bundle combining summary + computed observations.

        Convenience entry point used by :class:`ContextBudgetService`
        so it needs a single coroutine per agent request.
        """
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
