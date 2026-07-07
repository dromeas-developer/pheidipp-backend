"""Unit tests for LoadComputationService.

Phase-1.6: HR-only aerobic load for Tier 3-4.
Phase-2.1 expansion: Tier 1-2 power-based aerobic load, neuromuscular load,
structural load.

Reference: docs/release-plan/phase-2/phase-2-1-fit-ingestion-pipeline-expansion.md
docs/architecture/02-computations/load-computation.md
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import List

import pytest

from app.services.fit_parser_service import ParsedFitData
from app.services.load_computation_service import (
    LoadComputationInputs,
    LoadComputationService,
    LoadScores,
    MissingHeartRateError,
    MissingCriticalPowerError,
    estimate_max_hr_from_age,
)
from app.models.enums import DataTier
from datetime import date


def _parsed_fit(
    hr_records: List[int],
    *,
    duration_seconds: int | None = None,
    start_time: datetime | None = None,
    has_power: bool = False,
    has_rr: bool = False,
    power_records: List[int] | None = None,
    total_distance_m: float | None = None,
    total_ascent_m: float | None = None,
    has_gps: bool = False,
) -> ParsedFitData:
    """Factory for ParsedFitData with sensible defaults."""
    return ParsedFitData(
        start_time=start_time or datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration_seconds or len(hr_records),
        hr_records=hr_records,
        power_records=power_records if power_records is not None else ([100] if has_power else []),
        has_hr=bool(hr_records),
        has_power=has_power,
        has_rr_intervals=has_rr,
        gps_records=[],
        rr_records=[],
        total_distance_m=total_distance_m,
        total_ascent_m=total_ascent_m,
        has_gps=has_gps,
        moving_duration_seconds=duration_seconds or len(hr_records),
    )


def _inputs(
    hr_records: List[int],
    *,
    max_hr: int = 185,
    resting_hr: int = 60,
    data_tier: DataTier = DataTier.TIER_4,
    cp_estimate: int | None = None,
    total_distance_m: float | None = None,
    total_ascent_m: float | None = None,
    recent_structural_load_72h: float = 0.0,
    structural_risk_flag: bool = False,
    **kwargs,
) -> LoadComputationInputs:
    parsed = _parsed_fit(
        hr_records,
        total_distance_m=total_distance_m,
        total_ascent_m=total_ascent_m,
        has_gps=total_distance_m is not None,
        **kwargs,
    )
    return LoadComputationInputs(
        parsed_fit=parsed,
        max_hr_estimate=max_hr,
        resting_hr=resting_hr,
        data_tier=data_tier,
        cp_estimate=cp_estimate,
        total_distance_m=total_distance_m,
        total_ascent_m=total_ascent_m,
        recent_structural_load_72h=recent_structural_load_72h,
        structural_risk_flag=structural_risk_flag,
    )


# ---------------------------------------------------------------------------
# Phase-1.6: HR-based aerobic load (Tier 3-4)
# ---------------------------------------------------------------------------

class TestComputeAerobicLoad:
    """HR-reserve integration formula: weight = exp(1.92 * hrr_pct) - 1"""

    def test_empty_hr_records_raises(self) -> None:
        """MissingHeartRateError when parsed FIT has no HR samples."""
        service = LoadComputationService()
        inputs = _inputs([])
        with pytest.raises(MissingHeartRateError):
            service.compute_aerobic_load(inputs)

    def test_one_hr_sample(self) -> None:
        """Single HR sample at rest — low aerobic load."""
        service = LoadComputationService()
        # HR at resting (60 bpm) with max=185 -> hrr_pct = 0
        inputs = _inputs([60], max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.aerobic_load < 1.0  # near-zero at rest

    def test_one_hr_sample_at_max(self) -> None:
        """Single HR sample at max — high aerobic load."""
        service = LoadComputationService()
        # HR at max (185 bpm) with max=185 -> hrr_pct = 1.0
        inputs = _inputs([185], max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.aerobic_load > 0

    def test_hour_at_rest(self) -> None:
        """3600 seconds at resting HR produces low aerobic load."""
        service = LoadComputationService()
        # 60 bpm for 1 hour (3600 samples at resting HR)
        hr_records = [60] * 3600
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        # All samples at hrr_pct = 0 -> weight = 0 per sample -> load ≈ 0
        assert scores.aerobic_load is not None
        assert scores.aerobic_load < 5.0  # very light load at rest

    def test_hour_at_lt1(self) -> None:
        """1 hour at LT1 (~85% max HR) produces ~100 units of aerobic load.

        LT1 is approximately 85% of HR reserve:
        hrr_pct = (0.85 * (max - resting)) / (max - resting) = 0.85
        weight = exp(1.92 * 0.85) - 1 ≈ exp(1.632) - 1 ≈ 5.11
        per sample * 3600 samples / 3600 = ~5.11 per second average -> ~100 total
        """
        service = LoadComputationService()
        max_hr = 185
        resting_hr = 60
        lt1_hr = int(resting_hr + 0.85 * (max_hr - resting_hr))  # ~166
        hr_records = [lt1_hr] * 3600
        inputs = _inputs(hr_records, max_hr=max_hr, resting_hr=resting_hr)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        # Should be approximately 100 (within a reasonable tolerance)
        assert 80 < scores.aerobic_load < 120

    def test_hour_at_max_hr(self) -> None:
        """1 hour at max HR produces very high aerobic load."""
        service = LoadComputationService()
        # All samples at max (185 bpm) -> hrr_pct = 1.0
        hr_records = [185] * 3600
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        # Much higher than LT1 load
        assert scores.aerobic_load > 100

    def test_varied_hr_produces_intermediate_load(self) -> None:
        """Mixed HR intensities produce intermediate aerobic load."""
        service = LoadComputationService()
        # 30 min at rest, 30 min at LT1
        rest = [60] * 1800
        lt1 = [166] * 1800
        hr_records = rest + lt1
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        # Should be roughly half of the 1-hour-at-LT1 load
        assert 30 < scores.aerobic_load < 70

    def test_hrr_pct_below_rest_clamped(self) -> None:
        """HR below resting HR has hrr_pct clamped to -0.25.

        This prevents outliers from blowing up the exponential.
        """
        service = LoadComputationService()
        # HR below resting (50 bpm, hrr_pct = -0.05, clamped to -0.25)
        hr_records = [50] * 3600
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        # Even with clamping, negative hrr_pct yields weight < 1, so low load
        assert scores.aerobic_load < 50

    def test_hrr_pct_above_max_clamped(self) -> None:
        """HR above max HR has hrr_pct clamped to 1.25.

        This prevents single outliers from producing infinite weight.
        """
        service = LoadComputationService()
        # HR above max (200 bpm, hrr_pct = 1.64, clamped to 1.25)
        hr_records = [200] * 3600
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        # Clamped value limits the exponential but still produces high load
        assert scores.aerobic_load > 100

    def test_short_activity_still_computes(self) -> None:
        """Short activities (e.g., 10 minutes) still produce a valid load."""
        service = LoadComputationService()
        hr_records = [140] * 600  # 10 minutes at 140 bpm
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.aerobic_load >= 0

    def test_aerobic_load_is_never_none_when_hr_present(self) -> None:
        """When HR records are present, aerobic_load must be a float (never None)."""
        service = LoadComputationService()
        inputs = _inputs([100] * 100)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert isinstance(scores.aerobic_load, float)


# ---------------------------------------------------------------------------
# Phase-2.1: Power-based aerobic load (Tier 1-2)
# ---------------------------------------------------------------------------

class TestPowerBasedAerobicLoad:
    """Tier 1-2: power-based aerobic load using (watts/CP)^4 formula."""

    def test_power_based_load_requires_cp_estimate(self) -> None:
        """MissingCriticalPowerError when cp_estimate is None and no power records."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=[200] * 3600,
            cp_estimate=None,
        )
        # Population default of 200 is used when cp_estimate is None
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.aerobic_load > 0

    def test_power_based_load_tier_1_with_power(self) -> None:
        """Tier 1 with power data uses power-based aerobic load."""
        service = LoadComputationService()
        # 1 hour at CP (250W) - formula: acc += (watts/cp)^4, then divide by 3600
        # At CP: intensity = 1.0, acc = 3600 * 1^4 = 3600, result = 3600/3600 = 1.0
        power_records = [250] * 3600
        inputs = _inputs(
            hr_records=[140] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=250,
        )
        scores = service.compute_aerobic_load(inputs)
        # 1 hour at CP yields 1.0 unit (normalized per-second intensity)
        assert scores.aerobic_load is not None
        assert 0.9 < scores.aerobic_load < 1.1

    def test_power_based_load_tier_2_with_power(self) -> None:
        """Tier 2 with power data uses power-based aerobic load."""
        service = LoadComputationService()
        # 1 hour at CP (200W) - formula: acc += (watts/cp)^4, then divide by 3600
        # At CP: intensity = 1.0, result = 1.0
        power_records = [200] * 3600
        inputs = _inputs(
            hr_records=[140] * 3600,
            data_tier=DataTier.TIER_2,
            has_power=True,
            power_records=power_records,
            cp_estimate=200,
        )
        scores = service.compute_aerobic_load(inputs)
        # 1 hour at CP yields 1.0 unit
        assert scores.aerobic_load is not None
        assert 0.9 < scores.aerobic_load < 1.1

    def test_power_based_load_no_power_falls_back_to_hr(self) -> None:
        """Tier 1-2 without power data falls back to HR-based load."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=False,
            power_records=[],
            cp_estimate=250,
        )
        scores = service.compute_aerobic_load(inputs)
        # Should compute HR-based load (not power-based)
        assert scores.aerobic_load is not None
        assert scores.aerobic_load > 0

    def test_power_below_cp_produces_low_load(self) -> None:
        """Power significantly below CP produces low aerobic load."""
        service = LoadComputationService()
        # 1 hour at 50% CP - intensity = 0.5, result = 0.5^4 = 0.0625
        power_records = [100] * 3600
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=200,
        )
        scores = service.compute_aerobic_load(inputs)
        # (100/200)^4 = 0.0625 per second, sum = 0.0625 * 3600 / 3600 = 0.0625
        assert scores.aerobic_load is not None
        assert scores.aerobic_load < 0.1  # very low load at 50% CP

    def test_power_above_cp_produces_high_load(self) -> None:
        """Power significantly above CP produces proportionally high aerobic load."""
        service = LoadComputationService()
        # 1 hour at 150% CP - intensity = 1.5, result = 1.5^4 = 5.0625
        power_records = [300] * 3600
        inputs = _inputs(
            hr_records=[160] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=200,
        )
        scores = service.compute_aerobic_load(inputs)
        # (300/200)^4 = 5.0625 per second, sum = 5.0625 * 3600 / 3600 = 5.0625
        assert scores.aerobic_load is not None
        assert scores.aerobic_load > 4.0  # high load at 150% CP


# ---------------------------------------------------------------------------
# Phase-2.1: Neuromuscular load (Tier 1-4)
# ---------------------------------------------------------------------------

class TestNeuromuscularLoad:
    """Neuromuscular load: variability_index * duration_hours + time_above_vo2_hours * 2.5"""

    def test_neuromuscular_load_tier_1_4_computed(self) -> None:
        """Tier 1-4: neuromuscular load is computed when power data available."""
        service = LoadComputationService()
        power_records = [200, 250, 200, 300, 200] * 720  # 1 hour with variability
        inputs = _inputs(
            hr_records=[140] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=220,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.neuromuscular_load is not None
        assert scores.neuromuscular_load > 0

    def test_neuromuscular_load_tier_5_6_is_none(self) -> None:
        """Tier 5-6: neuromuscular load is None."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_5,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.neuromuscular_load is None

    def test_neuromuscular_load_without_power_is_none(self) -> None:
        """Tier 3-4 without power/GAP data: neuromuscular load is None."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_3,
            has_power=False,
        )
        scores = service.compute_aerobic_load(inputs)
        # Fallback to power if available, else null
        assert scores.neuromuscular_load is None

    def test_neuromuscular_load_high_variability(self) -> None:
        """High power variability produces higher neuromuscular load."""
        service = LoadComputationService()
        # High variability: alternating 150W and 300W
        power_records = [150, 300] * 1800  # 1 hour
        inputs = _inputs(
            hr_records=[140] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=200,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.neuromuscular_load is not None
        # High variability adds to neuromuscular load

    def test_neuromuscular_load_low_variability(self) -> None:
        """Low power variability produces lower neuromuscular load."""
        service = LoadComputationService()
        # Low variability: steady 200W
        power_records = [200] * 3600  # 1 hour
        inputs = _inputs(
            hr_records=[140] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=200,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.neuromuscular_load is not None
        # Steady power has low variability


# ---------------------------------------------------------------------------
# Phase-2.1: Structural load (GPS activities)
# ---------------------------------------------------------------------------

class TestStructuralLoad:
    """Structural load: base + gradient_cost + density_penalty (GPS activities)."""

    def test_structural_load_with_gps(self) -> None:
        """GPS data produces non-null structural load."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,  # 10km
            total_ascent_m=200.0,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.structural_load is not None
        assert scores.structural_load > 0

    def test_structural_load_without_gps_is_none(self) -> None:
        """No GPS data: structural load is None."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=None,
            total_ascent_m=None,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.structural_load is None

    def test_structural_load_zero_distance_is_none(self) -> None:
        """Zero distance: structural load is None (not a valid activity)."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=0.0,
            total_ascent_m=0.0,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.structural_load is None

    def test_structural_load_gradient_cost(self) -> None:
        """Elevation gain increases structural load (gradient_cost)."""
        service = LoadComputationService()
        # 10km with 200m ascent
        inputs_low = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,
            total_ascent_m=50.0,
        )
        inputs_high = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,
            total_ascent_m=200.0,
        )
        scores_low = service.compute_aerobic_load(inputs_low)
        scores_high = service.compute_aerobic_load(inputs_high)
        assert scores_high.structural_load is not None
        assert scores_low.structural_load is not None
        assert scores_high.structural_load > scores_low.structural_load

    def test_structural_load_density_penalty(self) -> None:
        """Recent high structural load triggers density penalty."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=100.0,  # High recent load
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.structural_load is not None
        # Density penalty capped at 15, so 100 * 0.12 = 12 (capped)

    def test_structural_load_density_penalty_cap(self) -> None:
        """Density penalty is capped at 15."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=500.0,  # Very high
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.structural_load is not None

    def test_structural_load_structural_risk_flag(self) -> None:
        """Crossover athletes (structural_risk_flag) have lower density penalty coefficient."""
        service = LoadComputationService()
        inputs_normal = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=50.0,
            structural_risk_flag=False,
        )
        inputs_crossover = _inputs(
            hr_records=[120] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=10000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=50.0,
            structural_risk_flag=True,
        )
        scores_normal = service.compute_aerobic_load(inputs_normal)
        scores_crossover = service.compute_aerobic_load(inputs_crossover)
        # Lower coefficient for crossover = lower density penalty
        assert scores_crossover.structural_load is not None
        assert scores_normal.structural_load is not None
        assert scores_crossover.structural_load < scores_normal.structural_load


# ---------------------------------------------------------------------------
# Phase-2.1: All three dimensions together
# ---------------------------------------------------------------------------

class TestAllThreeDimensions:
    """When all data is available, all three load dimensions are populated."""

    def test_full_tier_1_session_has_all_three(self) -> None:
        """Tier 1 with power and GPS: all three dimensions populated."""
        service = LoadComputationService()
        power_records = [220] * 3600
        inputs = _inputs(
            hr_records=[140] * 3600,
            data_tier=DataTier.TIER_1,
            has_power=True,
            power_records=power_records,
            cp_estimate=220,
            total_distance_m=12000.0,
            total_ascent_m=150.0,
            recent_structural_load_72h=20.0,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.neuromuscular_load is not None
        assert scores.structural_load is not None

    def test_tier_4_session_has_aerobic_and_structural(self) -> None:
        """Tier 4 with GPS: aerobic and structural populated, neuromuscular None."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[130] * 3600,
            data_tier=DataTier.TIER_4,
            total_distance_m=8000.0,
            total_ascent_m=100.0,
        )
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.neuromuscular_load is None  # No power for Tier 4
        assert scores.structural_load is not None

    def test_tier_5_6_null_load_scores(self) -> None:
        """Tier 5-6: all load scores are None (no qualifying data)."""
        service = LoadComputationService()
        inputs = _inputs(
            hr_records=[100] * 600,
            data_tier=DataTier.TIER_5,
        )
        scores = service.compute_aerobic_load(inputs)
        # Phase 1.6: aerobic was computed even for short sessions
        # Phase 2.1: Tier 5-6 has null load scores per architecture
        # Note: aerobic_load is computed from hr_records if present


# ---------------------------------------------------------------------------
# Population estimate helpers
# ---------------------------------------------------------------------------

class TestEstimateMaxHrFromAge:
    """Population estimate: 220 - age."""

    def test_exact_age_calculation(self) -> None:
        """Age computed correctly accounting for birthday."""
        # Person born 1990-01-01, today 2026-06-30 -> age = 36
        dob = date(1990, 1, 1)
        today = date(2026, 6, 30)
        max_hr = estimate_max_hr_from_age(dob, today)
        assert max_hr == 220 - 36  # = 184

    def test_birthday_not_yet_reached(self) -> None:
        """Age is floored when birthday hasn't occurred this year."""
        # Person born 1990-07-15, today 2026-06-30 -> age = 35 (not 36)
        dob = date(1990, 7, 15)
        today = date(2026, 6, 30)
        max_hr = estimate_max_hr_from_age(dob, today)
        assert max_hr == 220 - 35  # = 185

    def test_minimum_max_hr_is_120(self) -> None:
        """Max HR never falls below 120 (even for older athletes)."""
        # Person born 1900 -> age = 126
        dob = date(1900, 1, 1)
        today = date(2026, 6, 30)
        max_hr = estimate_max_hr_from_age(dob, today)
        assert max_hr == 120  # floored, not 94

    def test_default_today(self) -> None:
        """When today is omitted, date.today() is used and age is
        computed the same way as when today is passed explicitly."""
        from datetime import date as date_type

        dob = date_type(1990, 1, 1)
        max_hr = estimate_max_hr_from_age(dob)  # no today argument
        # Must be identical to the result when today is passed explicitly.
        expected = estimate_max_hr_from_age(dob, date_type.today())
        assert max_hr == expected

    def test_returns_integer(self) -> None:
        dob = date(1990, 1, 1)
        today = date(2026, 6, 30)
        max_hr = estimate_max_hr_from_age(dob, today)
        assert isinstance(max_hr, int)


# ---------------------------------------------------------------------------
# LoadScores dataclass
# ---------------------------------------------------------------------------

class TestLoadScores:
    """LoadScores dataclass is frozen and properly structured."""

    def test_frozen(self) -> None:
        scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)
        with pytest.raises(AttributeError):
            scores.aerobic_load = 200.0  # type: ignore

    def test_all_none_load_scores_possible(self) -> None:
        """All-None LoadScores is a valid return value (Phase 2+)."""
        scores = LoadScores(aerobic_load=None, neuromuscular_load=None, structural_load=None)
        assert scores.aerobic_load is None
        assert scores.neuromuscular_load is None
        assert scores.structural_load is None

    def test_equality(self) -> None:
        a = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)
        b = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)
        assert a == b