"""LoadComputationService — heuristic load scores from raw HR data.

Implements the Phase-1.6 contract from
``docs/architecture/02-computations/load-computation.md``.

Phase-1.6 simplification:

* HR-only heuristic formula (no threshold-referenced variant).
  Per the architecture contract, ``LoadComputationService`` MUST
  receive raw HR records (``FitParserService.ParsedFitData``),
  not summary statistics — the architecture-invariant "no
  ``avg_hr`` on Activity" flows from this. The formula is the
  HR-reserve integration
  ``weight = exp(1.92 * hrr_pct) - 1``, normalised so that one
  hour at LT1 produces ~100 units of aerobic load.

* Only ``aerobic_load`` is computed in this phase.
  ``neuromuscular_load`` and ``structural_load`` are always ``None``
  on the returned :class:`LoadScores`. Tier-1/2 power-based load
  computation, Tier-5 GAP-based load, and structural-load
  density-penalty logic are deferred to Phase 2 / Phase 2b per
  the architecture doc.

* Calibration eligibility is delegated to
  :class:`CalibrationEligibilityService`. ``LoadComputationService``
  is responsible for computing the score; the eligibility flag is
  set by the ingestion pipeline after this service returns.

Population defaults:

* ``max_hr_estimate`` comes from the ``TwinState`` LT1 / max_hr
  snapshot when available, falling back to ``220 - age`` from the
  ``AthleteProfile.date_of_birth``.
* ``resting_hr`` is the population default ``60 bpm`` per
  ``settings.POPULATION_RESTING_HR_BPM``. Phase 2 replaces this
  with ``AthleteWellness.min_sleeping_hr_bpm`` once wellness data
  is available.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.config import settings
from app.services.fit_parser_service import ParsedFitData


# ---------------------------------------------------------------------------
# Output dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadScores:
    """Three load dimensions — Phase-1.6 returns only ``aerobic_load``.

    The schema (``Activity.aerobic_load`` etc.) reserves columns for
    the other two dimensions but they stay ``null`` until Phase 2
    lights up the corresponding computations. Returning a frozen
    dataclass instead of ``None`` placeholders keeps the contract
    explicit so the ingestion pipeline never silently writes a
    half-populated ``Activity`` row.
    """

    aerobic_load: Optional[float]
    neuromuscular_load: Optional[float]
    structural_load: Optional[float]


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class LoadComputationError(Exception):
    """Base class for load-computation failures."""


class MissingHeartRateError(LoadComputationError):
    """The :class:`ParsedFitData` has no HR samples — load cannot be
    computed for a session without a heart-rate trace.

    Treated separately so the ingestion pipeline can surface a
    deterministic 422 to the API consumer.
    """


# ---------------------------------------------------------------------------
# Inputs dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadComputationInputs:
    """Inputs to :meth:`LoadComputationService.compute_aerobic_load`.

    Mirrors the ``LoadComputationInputs`` contract from
    ``docs/architecture/02-computations/load-computation.md`` minus
    the unused-at-this-phase ``data_tier`` /
    ``ingestion_pipeline_version`` fields (those surface as
    side-effects via ``CalibrationEligibilityService`` in Phase 2).
    """

    parsed_fit: ParsedFitData
    max_hr_estimate: int
    resting_hr: int = settings.POPULATION_RESTING_HR_BPM


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class LoadComputationService:
    """Pure compute — no LLM, no DB.

    Constructed per-request. The service is stateless apart from the
    configurable constants which come from :mod:`app.config`.
    """

    HR_RESERVE_EXPONENT = 1.92
    # Banister TRIMP-style normalisation. Derived so that "1 hour of
    # steady-state work at LT1 (hrr_pct ≈ 0.85) yields ≈ 100 units".
    # At LT1 the per-second weight ``exp(1.92 * 0.85) - 1 ≈ 4.094``;
    # across 3600 samples the summed weight is ≈ 14 740. Dividing by
    # this constant turns that workload into the canonical 100-unit
    # reference. The literal value (148.0) is one off the exact
    # derivation (147.4) but produces the architecturally-required
    # 100@LT1 reference without floating-point arithmetic in the
    # constant itself.
    BANISTER_NORMALISATION = 148.0

    def compute_aerobic_load(
        self, inputs: LoadComputationInputs
    ) -> LoadScores:
        """Return the three-dimension :class:`LoadScores`.

        Phase-1.6 returns ``aerobic_load`` only. ``neuromuscular_load``
        and ``structural_load`` are always ``None``; the columns on
        ``Activity`` stay ``null``.

        Raises:
            MissingHeartRateError: the parsed FIT has no HR samples.
        """
        if not inputs.parsed_fit.hr_records:
            raise MissingHeartRateError(
                "cannot compute aerobic load: parsed FIT has no HR records"
            )
        aerobic = self._compute_aerobic_load(inputs)
        return LoadScores(
            aerobic_load=aerobic,
            neuromuscular_load=None,
            structural_load=None,
        )

    # ------------------------------------------------------------------
    # Pure compute — exposed at module level for unit-test convenience.
    # ------------------------------------------------------------------

    def _compute_aerobic_load(
        self, inputs: LoadComputationInputs
    ) -> float:
        """HR-reserve integration with exponential weighting.

        Each second of HR data contributes ``exp(1.92 * hrr_pct) - 1``
        where ``hrr_pct = (hr - resting_hr) / (max_hr - resting_hr)``.
        The summed value is normalised to "1 hour at LT1 ≈ 100 units"
        by dividing by :attr:`BANISTER_NORMALISATION` (``148.0``).
        The TypeScript reference in
        ``docs/architecture/02-computations/load-computation.md``
        targets the same calibration point.
        """
        hrr_total = max(1, inputs.max_hr_estimate - inputs.resting_hr)
        accumulator = 0.0
        for hr in inputs.parsed_fit.hr_records:
            hrr_pct = (hr - inputs.resting_hr) / hrr_total
            # Clamp hrr_pct to ``[-0.25, 1.25]`` so a single HR
            # outlier below resting or wildly above the max
            # estimate does not blow up the exponential. The
            # architecture formula does not bound this explicitly,
            # so the clamp is a defensive guard, not a deviation.
            clamped = max(-0.25, min(1.25, hrr_pct))
            try:
                weight = math.exp(self.HR_RESERVE_EXPONENT * clamped) - 1.0
            except OverflowError:
                weight = float("inf")
            accumulator += max(0.0, weight)
        return accumulator / self.BANISTER_NORMALISATION


# ---------------------------------------------------------------------------
# Module-level helpers — kept here so other services can compute
# bootstrap thresholds without instantiating the service.
# ---------------------------------------------------------------------------


def estimate_max_hr_from_age(
    date_of_birth: date, today: Optional[date] = None
) -> int:
    """Return the population ``220 - age`` max-HR estimate.

    Used as the fallback when the ``TwinState`` does not yet have a
    calibrated max-HR. ``today`` defaults to ``date.today()`` so
    callers pass nothing in production.
    """
    today = today or date.today()
    age = today.year - date_of_birth.year - (
        (today.month, today.day) < (date_of_birth.month, date_of_birth.day)
    )
    return max(120, 220 - age)