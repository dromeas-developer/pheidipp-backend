"""Unit tests for LoadComputationService.

Phase-1.6: HR-only heuristic formula. Only aerobic_load is computed;
neuromuscular_load and structural_load are always None.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
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
    estimate_max_hr_from_age,
)
from datetime import date


def _parsed_fit(
    hr_records: List[int],
    *,
    duration_seconds: int | None = None,
    start_time: datetime | None = None,
    has_power: bool = False,
    has_rr: bool = False,
) -> ParsedFitData:
    """Factory for ParsedFitData with sensible defaults."""
    return ParsedFitData(
        start_time=start_time or datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration_seconds or len(hr_records),
        hr_records=hr_records,
        power_records=[100] if has_power else [],
        has_hr=bool(hr_records),
        has_power=has_power,
        has_rr_intervals=has_rr,
    )


def _inputs(
    hr_records: List[int],
    *,
    max_hr: int = 185,
    resting_hr: int = 60,
) -> LoadComputationInputs:
    return LoadComputationInputs(
        parsed_fit=_parsed_fit(hr_records),
        max_hr_estimate=max_hr,
        resting_hr=resting_hr,
    )


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
        # exp(1.92 * 1) - 1 = ~5.82 per second
        # After dividing by 3600: ~0.0016 per sample
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

    def test_neuromuscular_load_is_none(self) -> None:
        """Phase 1.6: neuromuscular_load is always None."""
        service = LoadComputationService()
        inputs = _inputs([100] * 3600, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.neuromuscular_load is None

    def test_structural_load_is_none(self) -> None:
        """Phase 1.6: structural_load is always None."""
        service = LoadComputationService()
        inputs = _inputs([100] * 3600, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.structural_load is None

    def test_aerobic_load_is_never_none_when_hr_present(self) -> None:
        """When HR records are present, aerobic_load must be a float (never None)."""
        service = LoadComputationService()
        inputs = _inputs([100] * 100)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert isinstance(scores.aerobic_load, float)

    def test_short_activity_still_computes(self) -> None:
        """Short activities (e.g., 10 minutes) still produce a valid load."""
        service = LoadComputationService()
        hr_records = [140] * 600  # 10 minutes at 140 bpm
        inputs = _inputs(hr_records, max_hr=185, resting_hr=60)
        scores = service.compute_aerobic_load(inputs)
        assert scores.aerobic_load is not None
        assert scores.aerobic_load >= 0


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