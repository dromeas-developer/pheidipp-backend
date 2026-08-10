"""Unit tests for TwinRecalibrationService pure-logic helpers.

Covers Banister update math, time-constants defaulting, confidence
ratchet functions, and confidence level derivation. No DB required.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.models.athlete_fitness import AthleteFitness
from app.models.enums import TwinConfidenceLevel
from app.services.twin_recalibration_service import (
    POPULATION_TIME_CONSTANTS,
    TwinRecalibrationService,
    derive_confidence_level,
    max_confidence_level,
    max_confidence_level_string,
    read_time_constants,
)

apply_banister_update = TwinRecalibrationService.apply_banister_update


def _build_fitness_row(
    *,
    aggregate: dict[str, float] | None = None,
    time_constants: dict[str, Any] | None = None,
    last_activity_id: uuid.UUID | None = None,
) -> AthleteFitness:
    return AthleteFitness(
        id=uuid.uuid4(),
        athlete_id=uuid.uuid4(),
        aggregate=aggregate if aggregate is not None else {"fitness": 0.0, "fatigue": 0.0, "form": 0.0},
        time_constants=time_constants if time_constants is not None else dict(POPULATION_TIME_CONSTANTS),
        last_activity_id=last_activity_id,
    )


class TestBanisterUpdate:
    def test_load_50_applies_one_day_decay(self) -> None:
        row = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )

        result = apply_banister_update(fitness_row=row, aerobic_load=50.0)

        assert result.fitness == pytest.approx(147.643, abs=0.05)
        assert result.fatigue == pytest.approx(84.675, abs=0.05)
        assert result.form == pytest.approx(62.968, abs=0.05)

    def test_zero_days_no_decay(self) -> None:
        row = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )

        result = apply_banister_update(fitness_row=row, aerobic_load=50.0)

        assert result.fitness >= 100.0
        assert result.fatigue >= 40.0

    def test_zero_load_pure_decay(self) -> None:
        row = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )

        result = apply_banister_update(fitness_row=row, aerobic_load=0.0)

        assert result.fitness < 100.0
        assert result.fatigue < 40.0
        assert result.form == pytest.approx(
            result.fitness - result.fatigue, abs=0.001
        )

    def test_negative_load_clamped_to_zero(self) -> None:
        row = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )
        baseline = apply_banister_update(fitness_row=row, aerobic_load=0.0)
        row_zero = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )
        result = apply_banister_update(fitness_row=row_zero, aerobic_load=-10.0)

        assert result.fitness == pytest.approx(baseline.fitness, abs=0.001)
        assert result.fatigue == pytest.approx(baseline.fatigue, abs=0.001)
        assert result.form == pytest.approx(baseline.form, abs=0.001)

    def test_form_equals_fitness_minus_fatigue_after_update(self) -> None:
        row = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )

        result = apply_banister_update(fitness_row=row, aerobic_load=25.0)

        assert result.form == pytest.approx(
            result.fitness - result.fatigue, abs=0.001
        )

    def test_mutates_row_aggregate_in_place(self) -> None:
        row = _build_fitness_row(
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0}
        )

        apply_banister_update(fitness_row=row, aerobic_load=50.0)

        assert "fitness" in row.aggregate
        assert "fatigue" in row.aggregate
        assert "form" in row.aggregate
        assert row.aggregate["form"] == pytest.approx(
            row.aggregate["fitness"] - row.aggregate["fatigue"], abs=0.001
        )


class TestReadTimeConstants:
    def test_none_time_constants_returns_population_defaults(self) -> None:
        row = _build_fitness_row(time_constants=None)

        constants = read_time_constants(row)

        assert constants["fitness_tau_days"] == 42
        assert constants["fatigue_tau_days"] == 7
        assert constants["source"] == "population_default"

    def test_existing_time_constants_passed_through(self) -> None:
        row = _build_fitness_row(
            time_constants={
                "fitness_tau_days": 30,
                "fatigue_tau_days": 5,
                "source": "individual_fitted",
            }
        )

        constants = read_time_constants(row)

        assert constants["fitness_tau_days"] == 30
        assert constants["fatigue_tau_days"] == 5
        assert constants["source"] == "individual_fitted"

    def test_missing_keys_default_to_population_values(self) -> None:
        row = _build_fitness_row(time_constants={"source": "individual_fitted"})

        constants = read_time_constants(row)

        assert constants["fitness_tau_days"] == 42
        assert constants["fatigue_tau_days"] == 7
        assert constants["source"] == "individual_fitted"


class TestMaxConfidenceLevel:
    def test_higher_rank_wins(self) -> None:
        assert (
            max_confidence_level(TwinConfidenceLevel.LOW, TwinConfidenceLevel.HIGH)
            == TwinConfidenceLevel.HIGH
        )

    def test_lower_rank_does_not_decrease(self) -> None:
        assert (
            max_confidence_level(TwinConfidenceLevel.MEDIUM, TwinConfidenceLevel.LOW)
            == TwinConfidenceLevel.MEDIUM
        )

    def test_equal_keeps_first(self) -> None:
        assert (
            max_confidence_level(TwinConfidenceLevel.HIGH, TwinConfidenceLevel.HIGH)
            == TwinConfidenceLevel.HIGH
        )


class TestMaxConfidenceLevelString:
    def test_previous_none_returns_computed(self) -> None:
        assert max_confidence_level_string(None, "high") == "high"

    def test_computed_none_returns_previous(self) -> None:
        assert max_confidence_level_string("medium", None) == "medium"

    def test_both_none_returns_none(self) -> None:
        assert max_confidence_level_string(None, None) is None

    def test_higher_rank_wins(self) -> None:
        assert max_confidence_level_string("low", "high") == "high"

    def test_high_never_drops_to_medium(self) -> None:
        assert max_confidence_level_string("high", "medium") == "high"

    def test_low_can_upgrade_to_medium(self) -> None:
        assert max_confidence_level_string("low", "medium") == "medium"


class TestConfidenceLevelDerivation:
    def _build_physiology(
        self, lt1_hr_weight: float | None, lt2_hr_weight: float | None
    ) -> Any:
        lt1: dict[str, Any] | None = (
            {"hr": {"value": 145.0, "prior_weight": lt1_hr_weight}}
            if lt1_hr_weight is not None
            else None
        )
        lt2: dict[str, Any] | None = (
            {"hr": {"value": 165.0, "prior_weight": lt2_hr_weight}}
            if lt2_hr_weight is not None
            else None
        )
        return type("FakePhysiology", (), {"lt1": lt1, "lt2": lt2})()

    def test_min_weight_3_returns_low(self) -> None:
        physiology = self._build_physiology(lt1_hr_weight=5.0, lt2_hr_weight=3.0)

        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.LOW
        )

    def test_min_weight_4_returns_medium(self) -> None:
        physiology = self._build_physiology(lt1_hr_weight=4.0, lt2_hr_weight=6.0)

        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.MEDIUM
        )

    def test_min_weight_8_returns_high(self) -> None:
        physiology = self._build_physiology(lt1_hr_weight=9.0, lt2_hr_weight=8.0)

        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.HIGH
        )

    def test_no_data_for_lt1_returns_low(self) -> None:
        physiology = self._build_physiology(lt1_hr_weight=None, lt2_hr_weight=5.0)

        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.LOW
        )

    def test_no_data_for_both_returns_low(self) -> None:
        physiology = self._build_physiology(lt1_hr_weight=None, lt2_hr_weight=None)

        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.LOW
        )

    def test_lt1_below_threshold_lt2_above_returns_low(self) -> None:
        physiology = self._build_physiology(lt1_hr_weight=2.0, lt2_hr_weight=10.0)

        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.LOW
        )
