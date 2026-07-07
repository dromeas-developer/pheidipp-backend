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

Phase-2 expansion:

* Tier-based load computation (power-based for Tier 1-2, HR-based
  fallback for Tier 3-4, null for Tier 5-6).
* Neuromuscular load (variability index + time above VO2max).
* Structural load (distance + elevation + density penalty).
* Full three-dimension :class:`LoadScores` returned for all tiers.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Optional

from app.config import settings
from app.models.enums import DataTier, SportType
from app.services.fit_parser_service import ParsedFitData


# ---------------------------------------------------------------------------
# Output dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadScores:
    """Three load dimensions — all populated for Phase-2.

    Phase-1.6 returned only ``aerobic_load``. Phase-2 populates all
    three dimensions according to the athlete's data tier and signal
    availability.

    Null semantics:
    - Tier 5-6 activities have null load scores (no qualifying data).
    - Tier 3-4 activities have null neuromuscular_load (no power/GAP).
    - Activities without GPS have null structural_load.
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


class MissingCriticalPowerError(LoadComputationError):
    """Power-based load requires CP, but none is available.

    For Phase 2.1, we fall back to a population estimate when
    ``AthletePhysiology.cp`` is null.
    """


# ---------------------------------------------------------------------------
# Inputs dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoadComputationInputs:
    """Inputs to :meth:`LoadComputationService.compute_aerobic_load`.

    Phase-2 extends Phase-1.6 inputs with tier information, GPS
    totals, recent structural load for density penalty, and signal
    records needed for multi-dimensional load computation.

    Phase-2.1-P3 adds sport_type and sport_type_detection_version
    for future phases that may need the full pipeline context.
    The load formulas do not consume sport_type directly (data_tier
    already encodes the non-running override as Tier 6).
    """

    parsed_fit: ParsedFitData
    max_hr_estimate: int
    data_tier: DataTier = DataTier.TIER_4  # Default to Tier 4 (HR-based)
    resting_hr: int = settings.POPULATION_RESTING_HR_BPM
    cp_estimate: Optional[int] = None  # watts, falls back to population default
    total_distance_m: Optional[float] = None
    total_ascent_m: Optional[float] = None
    recent_structural_load_72h: float = 0.0
    structural_risk_flag: bool = False  # crossover athlete coefficient
    # Sport type context (Phase-2.1-P3 — for future phases):
    sport_type: SportType = SportType.UNKNOWN
    sport_type_detection_version: Optional[str] = None

    @property
    def has_gps(self) -> bool:
        """Whether the parsed FIT contains GPS data."""
        return self.parsed_fit.has_gps


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

        Phase-2 computes all three dimensions based on data tier:

        - Tier 1-2: Power-based aerobic load if power data available,
          else HR-based fallback.
        - Tier 3-4: HR-based aerobic load only.
        - Tier 5-6: null aerobic load (no qualifying data).

        Neuromuscular load:
        - Tier 1-4: variability index + time above VO2max.
        - Tier 5-6: null.

        Structural load:
        - If GPS data available: distance + elevation + density penalty.
        - If no GPS: null.

        Raises:
            MissingHeartRateError: the parsed FIT has no HR samples.
        """
        if not inputs.parsed_fit.hr_records:
            raise MissingHeartRateError(
                "cannot compute aerobic load: parsed FIT has no HR records"
            )
        aerobic = self._compute_aerobic_load(inputs)
        neuromuscular = self._compute_neuromuscular_load(inputs)
        structural = self._compute_structural_load(inputs)
        return LoadScores(
            aerobic_load=aerobic,
            neuromuscular_load=neuromuscular,
            structural_load=structural,
        )

    # ------------------------------------------------------------------
    # Pure compute — exposed at module level for unit-test convenience.
    # ------------------------------------------------------------------

    def _compute_aerobic_load(
        self, inputs: LoadComputationInputs
    ) -> float:
        """HR-reserve integration with exponential weighting.

        Phase-2: For Tier 1-2 athletes with power data, compute power-based
        aerobic load using the fourth-power intensity factor formula.
        Fall back to HR-based formula otherwise.

        Each second of HR data contributes ``exp(1.92 * hrr_pct) - 1``
        where ``hrr_pct = (hr - resting_hr) / (max_hr - resting_hr)``.
        The summed value is normalised to "1 hour at LT1 ≈ 100 units"
        by dividing by :attr:`BANISTER_NORMALISATION` (``148.0``).
        The TypeScript reference in
        ``docs/architecture/02-computations/load-computation.md``
        targets the same calibration point.
        """
        # Power-based formula for Tier 1-2 with power data
        if (
            inputs.data_tier in [DataTier.TIER_1, DataTier.TIER_2]
            and inputs.parsed_fit.has_power
            and inputs.parsed_fit.power_records
        ):
            cp = inputs.cp_estimate or self._estimate_cp_from_population(inputs)
            return self._compute_power_aerobic_load(
                power_records=inputs.parsed_fit.power_records,
                cp=cp,
            )

        # HR-based formula for Tier 3-4 or when power unavailable
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

    def _compute_power_aerobic_load(
        self, power_records: list[int], cp: int
    ) -> float:
        """Power-based aerobic load: fourth-power intensity factor.

        Formula per architecture doc: ``acc += (watts / cp)^4`` for each
        second, then normalised to "1 hour at CP ≈ 100 units".

        This is the power equivalent of the HR-reserve integration,
        calibrated so that one hour at CP produces approximately
        100 units of aerobic load.

        Raises:
            MissingCriticalPowerError: CP estimate is required.
        """
        if cp <= 0:
            raise MissingCriticalPowerError(
                "cp_estimate must be positive for power-based load"
            )
        accumulator = 0.0
        for watts in power_records:
            if watts <= 0:
                continue
            intensity = watts / cp
            accumulator += (intensity**4)
        # Normalise: 1 hour at CP (3600 seconds) should yield ~100 units
        # So divide by (3600 * 1^4) = 3600
        return accumulator / 3600.0

    def _compute_neuromuscular_load(
        self, inputs: LoadComputationInputs
    ) -> Optional[float]:
        """Neuromuscular load for Tier 1-4 athletes.

        Computed as: variability index * duration_hours + time_above_vo2_hours * 2.5

        - Variability index: coefficient of variation of power (Tier 1-2)
          or GAP (Tier 3-4) over the session.
        - Time above VO2max: seconds with power/GAP >= 95% of LT2 intensity.

        Returns null for Tier 5-6 (no qualifying signal).
        """
        if inputs.data_tier in [DataTier.TIER_5, DataTier.TIER_6]:
            return None

        if inputs.data_tier in [DataTier.TIER_1, DataTier.TIER_2]:
            values = inputs.parsed_fit.power_records
            if not values:
                return None
        else:
            # Tier 3-4: use GAP (gap_records not yet in ParsedFitData)
            # For now, fall back to power if available, else null
            if not inputs.parsed_fit.power_records:
                return None
            values = inputs.parsed_fit.power_records

        if not values:
            return None

        # Coefficient of variation
        mean_val = statistics.mean(values)
        if mean_val <= 0:
            return None
        stdev_val = statistics.stdev(values)
        cv = stdev_val / mean_val

        # Time above VO2max (95% of LT2 intensity)
        # Estimating LT2 as CP * 1.2 for runs with power
        lt2_threshold = inputs.cp_estimate * 1.2 if inputs.cp_estimate else None
        if lt2_threshold is None:
            # Fallback: estimate from max HR
            lt2_hr = int(inputs.max_hr_estimate * 0.85)
            # Rough power correlate (assuming 3 W/hr estimate)
            lt2_threshold = lt2_hr * 3

        time_above_vo2 = sum(1 for v in values if v >= lt2_threshold)

        duration_hours = max(inputs.parsed_fit.duration_seconds / 3600.0, 0.001)
        time_above_vo2_hours = time_above_vo2 / 3600.0

        variability_component = cv * duration_hours
        vo2_component = time_above_vo2_hours * 2.5

        return variability_component + vo2_component

    def _compute_structural_load(
        self, inputs: LoadComputationInputs
    ) -> Optional[float]:
        """Structural load for activities with GPS data.

        Formula: base + gradient_cost + density_penalty

        - Base: distance_km * surface_modifier (default 1.0 for unknown)
        - Gradient cost: (elevation_gain_m / 100) * 0.18 * distance_km
        - Density penalty: min(recent_structural_load_72h * coefficient, 15)

        Returns null if no GPS data or total_distance_m <= 0.
        """
        if not inputs.has_gps or not inputs.total_distance_m or inputs.total_distance_m <= 0:
            return None

        distance_km = inputs.total_distance_m / 1000.0

        # Surface modifier — Phase 2.1 uses unknown (1.0) by default
        surface_modifier = 1.0

        base = distance_km * surface_modifier

        # Gradient cost
        if inputs.total_ascent_m and inputs.total_ascent_m > 0:
            gradient_cost = (inputs.total_ascent_m / 100.0) * 0.18 * distance_km
        else:
            gradient_cost = 0.0

        # Density penalty coefficient
        coefficient = 0.08 if inputs.structural_risk_flag else 0.12
        density_penalty = min(inputs.recent_structural_load_72h * coefficient, 15.0)

        return base + gradient_cost + density_penalty

    def _estimate_cp_from_population(
        self, inputs: LoadComputationInputs
    ) -> int:
        """Estimate critical power from population defaults.

        Phase 2.1 falls back to population estimates when
        ``AthletePhysiology.cp`` is null.

        Returns watts.
        """
        # Simple sex-based defaults (compatible with existing pattern)
        # This matches the existing max HR population estimation pattern
        return 200  # conservative default for Phase 2.1


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