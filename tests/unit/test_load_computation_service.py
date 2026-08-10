"""Unit tests for LoadComputationService — pure formula logic, no DB.

Covers aerobic load (HR-reserve and power-based), structural load,
neuromuscular load, error branches, and tier-based null handling.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

import pytest

from app.models.enums import DataTier, SportType
from app.services.load_computation_service import (
    LoadComputationInputs,
    LoadComputationService,
    LoadScores,
    MissingCriticalPowerError,
    MissingHeartRateError,
)
from app.services.fit_parser_service import ParsedFitData


def _build_parsed_fit(
    *,
    hr_records: Optional[Sequence[Optional[float]]] = None,
    power_records: Optional[Sequence[Optional[float]]] = None,
    has_hr: bool = False,
    has_power: bool = False,
    has_gps: bool = False,
    total_distance_m: Optional[float] = None,
    total_ascent_m: Optional[float] = None,
    duration_seconds: int = 3600,
    sport_type: SportType = SportType.RUNNING,
) -> ParsedFitData:
    return ParsedFitData(
        start_time=datetime(2026, 1, 1, 8, 0, 0),
        duration_seconds=duration_seconds,
        hr_records=list(hr_records) if hr_records else [],
        power_records=list(power_records) if power_records else [],
        has_hr=has_hr,
        has_power=has_power,
        has_rr_intervals=False,
        gps_records=[],
        rr_records=[],
        total_distance_m=total_distance_m,
        total_ascent_m=total_ascent_m,
        has_gps=has_gps,
        moving_duration_seconds=duration_seconds - 50,
        sport_type=sport_type,
        detection_confidence="high",
        detection_version="v1",
    )


@pytest.fixture
def service() -> LoadComputationService:
    return LoadComputationService()


class TestAerobicLoadHrReserve:
    def test_lt1_intensity_produces_around_100_units_for_one_hour(
        self,
        service: LoadComputationService,
    ) -> None:
        hr_records = [169.0] * 3600
        parsed_fit = _build_parsed_fit(
            hr_records=hr_records, has_hr=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.aerobic_load is not None
        assert 80.0 <= scores.aerobic_load <= 120.0

    def test_hr_reserve_formula_applied_to_raw_samples_not_averaged(
        self,
        service: LoadComputationService,
    ) -> None:
        hr_records = [169.0] * 3600
        parsed_fit = _build_parsed_fit(
            hr_records=hr_records, has_hr=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        one_hour_load = service.compute_aerobic_load(inputs).aerobic_load

        half_hr_records = [169.0] * 1800
        parsed_fit_half = _build_parsed_fit(
            hr_records=half_hr_records, has_hr=True, duration_seconds=1800
        )
        inputs_half = LoadComputationInputs(
            parsed_fit=parsed_fit_half,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        half_hour_load = service.compute_aerobic_load(inputs_half).aerobic_load

        assert one_hour_load is not None
        assert half_hour_load is not None
        ratio = one_hour_load / half_hour_load
        assert 1.85 <= ratio <= 2.15

    def test_output_monotonic_with_hrr_pct(
        self,
        service: LoadComputationService,
    ) -> None:
        low_intensity_hr = [120.0] * 3600
        high_intensity_hr = [169.0] * 3600
        low_parsed = _build_parsed_fit(
            hr_records=low_intensity_hr, has_hr=True, duration_seconds=3600
        )
        high_parsed = _build_parsed_fit(
            hr_records=high_intensity_hr, has_hr=True, duration_seconds=3600
        )

        low_inputs = LoadComputationInputs(
            parsed_fit=low_parsed,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )
        high_inputs = LoadComputationInputs(
            parsed_fit=high_parsed,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        low_load = service.compute_aerobic_load(low_inputs).aerobic_load
        high_load = service.compute_aerobic_load(high_inputs).aerobic_load

        assert low_load is not None
        assert high_load is not None
        assert low_load < high_load
        assert high_load > 50.0

    def test_hrr_pct_zero_contributes_zero(
        self,
        service: LoadComputationService,
    ) -> None:
        hr_records = [50.0] * 3600
        parsed_fit = _build_parsed_fit(
            hr_records=hr_records, has_hr=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        score = service.compute_aerobic_load(inputs).aerobic_load

        assert score == pytest.approx(0.0, abs=0.001)


class TestAerobicLoadHrReserveErrors:
    def test_empty_hr_records_raises_missing_heart_rate_error(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[], has_hr=False, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        with pytest.raises(MissingHeartRateError):
            service.compute_aerobic_load(inputs)


class TestAerobicLoadPower:
    def test_power_at_cp_yields_unit_load_for_one_hour(
        self,
        service: LoadComputationService,
    ) -> None:
        power_records = [300.0] * 3600
        parsed_fit = _build_parsed_fit(
            power_records=power_records, has_power=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_1,
            cp_estimate=300,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.aerobic_load == pytest.approx(1.0, abs=0.001)

    def test_half_intensity_yields_one_sixteenth(
        self,
        service: LoadComputationService,
    ) -> None:
        power_records = [150.0] * 3600
        parsed_fit = _build_parsed_fit(
            power_records=power_records, has_power=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_1,
            cp_estimate=300,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.aerobic_load == pytest.approx(0.0625, abs=0.001)

    def test_missing_cp_uses_population_estimate(
        self,
        service: LoadComputationService,
    ) -> None:
        power_records = [180.0] * 3600
        parsed_fit = _build_parsed_fit(
            power_records=power_records, has_power=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_1,
            cp_estimate=None,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.aerobic_load is not None
        assert scores.aerobic_load >= 0.0

    def test_cp_zero_raises_missing_critical_power_error(
        self,
        service: LoadComputationService,
    ) -> None:
        power_records = [300.0] * 3600
        parsed_fit = _build_parsed_fit(
            power_records=power_records, has_power=True, duration_seconds=3600
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_1,
            cp_estimate=0,
        )

        with pytest.raises(MissingCriticalPowerError):
            service.compute_aerobic_load(inputs)


class TestStructuralLoad:
    def test_full_formula_with_gradient_and_density(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=True,
            total_distance_m=10_000.0,
            total_ascent_m=100.0,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
            total_distance_m=10_000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=50.0,
            structural_risk_flag=False,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.structural_load == pytest.approx(17.8, abs=0.01)

    def test_risk_flag_lowers_density_coefficient(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=True,
            total_distance_m=10_000.0,
            total_ascent_m=100.0,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
            total_distance_m=10_000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=50.0,
            structural_risk_flag=True,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.structural_load == pytest.approx(15.8, abs=0.01)

    def test_density_capped_at_15(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=True,
            total_distance_m=10_000.0,
            total_ascent_m=0.0,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
            total_distance_m=10_000.0,
            total_ascent_m=0.0,
            recent_structural_load_72h=200.0,
            structural_risk_flag=False,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.structural_load == pytest.approx(25.0, abs=0.01)

    def test_no_gps_returns_null_structural_load(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=False,
            total_distance_m=None,
            total_ascent_m=None,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.structural_load is None

    def test_zero_distance_returns_null_structural_load(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=True,
            total_distance_m=0.0,
            total_ascent_m=100.0,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.structural_load is None

    def test_no_ascent_yields_zero_gradient_cost(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=True,
            total_distance_m=10_000.0,
            total_ascent_m=0.0,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
            total_distance_m=10_000.0,
            total_ascent_m=0.0,
            recent_structural_load_72h=50.0,
            structural_risk_flag=False,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.structural_load == pytest.approx(16.0, abs=0.01)


class TestNeuromuscularLoad:
    def test_tier_5_returns_null(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            power_records=[300.0] * 3600,
            has_hr=True,
            has_power=True,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_5,
            cp_estimate=300,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.neuromuscular_load is None

    def test_tier_6_returns_null(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            power_records=[300.0] * 3600,
            has_hr=True,
            has_power=True,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_6,
            cp_estimate=300,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.neuromuscular_load is None

    def test_tier_1_with_varied_power_produces_load(
        self,
        service: LoadComputationService,
    ) -> None:
        varying_power = [250.0 + (i % 100) for i in range(3600)]
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            power_records=varying_power,
            has_hr=True,
            has_power=True,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_1,
            cp_estimate=300,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.neuromuscular_load is not None
        assert scores.neuromuscular_load > 0.0

    def test_no_power_records_returns_null(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            power_records=[],
            has_hr=True,
            has_power=False,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_3,
        )

        scores = service.compute_aerobic_load(inputs)

        assert scores.neuromuscular_load is None


class TestComputeReturnsLoadScores:
    def test_returns_three_load_fields(
        self,
        service: LoadComputationService,
    ) -> None:
        parsed_fit = _build_parsed_fit(
            hr_records=[150.0] * 3600,
            has_hr=True,
            has_gps=True,
            total_distance_m=10_000.0,
            total_ascent_m=100.0,
            duration_seconds=3600,
        )
        inputs = LoadComputationInputs(
            parsed_fit=parsed_fit,
            max_hr_estimate=190,
            resting_hr=50,
            data_tier=DataTier.TIER_4,
            total_distance_m=10_000.0,
            total_ascent_m=100.0,
            recent_structural_load_72h=50.0,
            structural_risk_flag=False,
        )

        scores = service.compute_aerobic_load(inputs)

        assert isinstance(scores, LoadScores)
        assert scores.aerobic_load is not None
        assert scores.structural_load is not None
