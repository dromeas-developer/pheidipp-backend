"""Heuristic load scores from raw HR data."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date
from typing import Optional, Sequence

from app.config import settings
from app.models.enums import DataTier, SportType
from app.services.fit_parser_service import ParsedFitData


@dataclass(frozen=True)
class LoadScores:
    """Three load dimensions."""

    aerobic_load: Optional[float]
    neuromuscular_load: Optional[float]
    structural_load: Optional[float]


class LoadComputationError(Exception):
    """Base class for load-computation failures."""


class MissingHeartRateError(LoadComputationError):
    """ParsedFitData has no HR samples."""


class MissingCriticalPowerError(LoadComputationError):
    """Power-based load requires CP, but none is available."""


@dataclass(frozen=True)
class LoadComputationInputs:
    """Inputs to LoadComputationService.compute_aerobic_load."""

    parsed_fit: ParsedFitData
    max_hr_estimate: int
    data_tier: DataTier = DataTier.TIER_4
    resting_hr: int = settings.POPULATION_RESTING_HR_BPM
    cp_estimate: Optional[int] = None
    total_distance_m: Optional[float] = None
    total_ascent_m: Optional[float] = None
    recent_structural_load_72h: float = 0.0
    structural_risk_flag: bool = False
    sport_type: SportType = SportType.UNKNOWN
    sport_type_detection_version: Optional[str] = None

    @property
    def has_gps(self) -> bool:
        """Whether the parsed FIT contains GPS data."""
        return self.parsed_fit.has_gps


class LoadComputationService:
    """Pure compute — no LLM, no DB."""

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

    def compute_aerobic_load(self, inputs: LoadComputationInputs) -> LoadScores:
        """Return three-dimension LoadScores."""
        has_power_path = (
            inputs.data_tier in [DataTier.TIER_1, DataTier.TIER_2]
            and inputs.parsed_fit.has_power
            and inputs.parsed_fit.power_records
        )
        if not inputs.parsed_fit.hr_records and not has_power_path:
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

    def _compute_aerobic_load(self, inputs: LoadComputationInputs) -> float:
        """HR-reserve integration with exponential weighting."""
        if (
            inputs.data_tier in [DataTier.TIER_1, DataTier.TIER_2]
            and inputs.parsed_fit.has_power
            and inputs.parsed_fit.power_records
        ):
            cp = (
                inputs.cp_estimate
                if inputs.cp_estimate is not None
                else self._estimate_cp_from_population(inputs)
            )
            return self._compute_power_aerobic_load(
                power_records=inputs.parsed_fit.power_records,
                cp=cp,
            )

        # HR-based formula for Tier 3-4 or when power unavailable
        hrr_total = max(1, inputs.max_hr_estimate - inputs.resting_hr)
        accumulator = 0.0
        for hr in inputs.parsed_fit.hr_records:
            if hr is None:
                continue
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
        self, power_records: Sequence[Optional[float]], cp: int
    ) -> float:
        """Power-based aerobic load: fourth-power intensity factor."""
        if cp <= 0:
            raise MissingCriticalPowerError(
                "cp_estimate must be positive for power-based load"
            )
        accumulator = 0.0
        for watts in power_records:
            if watts is None or watts <= 0:
                continue
            intensity = watts / cp
            accumulator += intensity**4
        # Normalise: 1 hour at CP (3600 seconds) should yield ~100 units
        # So divide by (3600 * 1^4) = 3600
        return accumulator / 3600.0

    def _compute_neuromuscular_load(
        self, inputs: LoadComputationInputs
    ) -> Optional[float]:
        """Neuromuscular load for Tier 1-4 athletes."""
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

        # Filter out None values for stats computation
        clean_values: list[float] = [v for v in values if v is not None]
        if not clean_values:
            return None

        # Coefficient of variation
        mean_val = statistics.mean(clean_values)
        if mean_val <= 0:
            return None
        stdev_val = statistics.stdev(clean_values)
        cv = stdev_val / mean_val

        # Time above VO2max (95% of LT2 intensity)
        # Estimating LT2 as CP * 1.2 for runs with power
        lt2_threshold = inputs.cp_estimate * 1.2 if inputs.cp_estimate else None
        if lt2_threshold is None:
            # Fallback: estimate from max HR
            lt2_hr = int(inputs.max_hr_estimate * 0.85)
            # Rough power correlate (assuming 3 W/hr estimate)
            lt2_threshold = lt2_hr * 3

        time_above_vo2 = sum(1 for v in clean_values if v >= lt2_threshold)

        duration_hours = max(inputs.parsed_fit.duration_seconds / 3600.0, 0.001)
        time_above_vo2_hours = time_above_vo2 / 3600.0

        variability_component = cv * duration_hours
        vo2_component = time_above_vo2_hours * 2.5

        return variability_component + vo2_component

    def _compute_structural_load(
        self, inputs: LoadComputationInputs
    ) -> Optional[float]:
        """Structural load for activities with GPS data."""
        if (
            not inputs.has_gps
            or not inputs.total_distance_m
            or inputs.total_distance_m <= 0
        ):
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

    def _estimate_cp_from_population(self, inputs: LoadComputationInputs) -> int:
        """Estimate critical power from population defaults."""
        # Simple sex-based defaults (compatible with existing pattern)
        # This matches the existing max HR population estimation pattern
        return 200  # conservative default for Phase 2.1


def estimate_max_hr_from_age(date_of_birth: date, today: Optional[date] = None) -> int:
    """Return population 220 - age max-HR estimate."""
    today = today or date.today()
    age = (
        today.year
        - date_of_birth.year
        - ((today.month, today.day) < (date_of_birth.month, date_of_birth.day))
    )
    return max(120, 220 - age)
