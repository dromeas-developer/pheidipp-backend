"""Unit tests for TwinRecalibrationService — Banister update + append-only TwinState.

Phase-1.6: Only aggregate block populated. Threshold values stay latest snapshot.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
docs/architecture/02-computations/banister-update.md
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.athlete_fitness import AthleteFitness
from app.models.enums import (
    DataTier,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.services.twin_recalibration_service import (
    BanisterUpdateResult,
    TwinRecalibrationService,
    _days_since,
    _read_time_constants,
    POPULATION_TIME_CONSTANTS,
)


class TestBanisterUpdate:
    """Pure-compute _apply_banister_update static method."""

    @staticmethod
    def _fitness_row(
        aggregate: dict | None = None,
        time_constants: dict | None = None,
        last_activity_id: uuid.UUID | None = None,
    ) -> MagicMock:
        """Create a mock AthleteFitness row with JSONB aggregate."""
        row = MagicMock(spec=AthleteFitness)
        row.aggregate = aggregate or {"fitness": 0.0, "fatigue": 0.0, "form": 0.0}
        row.time_constants = time_constants
        row.last_activity_id = last_activity_id
        return row

    def test_first_update_with_zero_load(self) -> None:
        """Zero load on first update: fitness and fatigue decay to 0."""
        row = self._fitness_row(
            aggregate={"fitness": 0.0, "fatigue": 0.0, "form": 0.0}
        )
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=0.0,
        )
        assert result.fitness == 0.0
        assert result.fatigue == 0.0
        assert result.form == 0.0

    def test_first_update_with_positive_load(self) -> None:
        """Positive load adds to both fitness and fatigue."""
        row = self._fitness_row(
            aggregate={"fitness": 0.0, "fatigue": 0.0, "form": 0.0}
        )
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=100.0,
        )
        # No decay on first update (days_since=1, e^0=1)
        assert result.fitness == 100.0
        assert result.fatigue == 100.0
        assert result.form == 0.0

    def test_decay_applied_on_subsequent_update(self) -> None:
        """Subsequent update: existing fitness/fatigue decay before adding new load."""
        row = self._fitness_row(
            aggregate={"fitness": 50.0, "fatigue": 30.0, "form": 20.0}
        )
        # days_since=1 for single-day spacing (Phase 1.6 simplification)
        # fitness_decay = exp(-1/42) ≈ 0.976
        # fatigue_decay = exp(-1/7) ≈ 0.860
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=50.0,
        )
        # Decayed fitness: 50 * 0.976 + 50 = 48.8 + 50 = 98.8
        expected_fitness = 50.0 * math.exp(-1 / 42) + 50.0
        # Decayed fatigue: 30 * 0.860 + 50 = 25.8 + 50 = 75.8
        expected_fatigue = 30.0 * math.exp(-1 / 7) + 50.0
        assert abs(result.fitness - expected_fitness) < 0.5
        assert abs(result.fatigue - expected_fatigue) < 0.5
        assert abs(result.form - (expected_fitness - expected_fatigue)) < 0.5

    def test_form_equals_fitness_minus_fatigue(self) -> None:
        """Form is always fitness - fatigue (Banister definition)."""
        row = self._fitness_row(
            aggregate={"fitness": 80.0, "fatigue": 30.0, "form": 50.0}
        )
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=20.0,
        )
        assert abs(result.form - (result.fitness - result.fatigue)) < 0.01

    def test_negative_load_treated_as_zero(self) -> None:
        """Negative aerobic_load is treated as 0 (no negative impulse)."""
        row = self._fitness_row(
            aggregate={"fitness": 50.0, "fatigue": 30.0, "form": 20.0}
        )
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=-50.0,  # negative load
        )
        # Only decay, no negative contribution
        expected_fitness = 50.0 * math.exp(-1 / 42)
        expected_fatigue = 30.0 * math.exp(-1 / 7)
        assert result.fitness == pytest.approx(expected_fitness, abs=0.01)
        assert result.fatigue == pytest.approx(expected_fatigue, abs=0.01)

    def test_null_aggregate_defaults_to_zero(self) -> None:
        """Missing aggregate keys default to 0.0."""
        row = self._fitness_row(aggregate={})
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=50.0,
        )
        # Fitness and fatigue start at 0 and receive load with no decay
        assert result.fitness == 50.0
        assert result.fatigue == 50.0

    def test_row_aggregate_updated_in_place(self) -> None:
        """The Banister update writes back to fitness_row.aggregate in place."""
        row = self._fitness_row(
            aggregate={"fitness": 0.0, "fatigue": 0.0, "form": 0.0}
        )
        TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=100.0,
        )
        # The aggregate dict should be mutated
        assert "fitness" in row.aggregate
        assert row.aggregate["fitness"] == 100.0

    def test_custom_time_constants_used(self) -> None:
        """Custom time constants from fitness_row.time_constants override defaults."""
        row = self._fitness_row(
            aggregate={"fitness": 50.0, "fatigue": 30.0, "form": 20.0},
            time_constants={"fitness_tau_days": 21, "fatigue_tau_days": 3},
        )
        result = TwinRecalibrationService._apply_banister_update(
            fitness_row=row,
            aerobic_load=50.0,
        )
        # With shorter time constants, decay is faster
        # fitness_decay = exp(-1/21) ≈ 0.953
        # fatigue_decay = exp(-1/3) ≈ 0.717
        expected_fitness = 50.0 * math.exp(-1 / 21) + 50.0
        expected_fatigue = 30.0 * math.exp(-1 / 3) + 50.0
        assert abs(result.fitness - expected_fitness) < 0.5
        assert abs(result.fatigue - expected_fatigue) < 0.5


class TestReadTimeConstants:
    """_read_time_constants helper."""

    def test_returns_population_defaults_when_time_constants_none(self) -> None:
        row = MagicMock(spec=AthleteFitness)
        row.time_constants = None
        result = _read_time_constants(row)
        assert result["fitness_tau_days"] == 42
        assert result["fatigue_tau_days"] == 7
        assert result["source"] == "population_default"

    def test_returns_population_defaults_when_time_constants_empty(self) -> None:
        row = MagicMock(spec=AthleteFitness)
        row.time_constants = {}
        result = _read_time_constants(row)
        assert result["fitness_tau_days"] == 42
        assert result["fatigue_tau_days"] == 7

    def test_uses_custom_time_constants(self) -> None:
        row = MagicMock(spec=AthleteFitness)
        row.time_constants = {"fitness_tau_days": 30, "fatigue_tau_days": 5}
        result = _read_time_constants(row)
        assert result["fitness_tau_days"] == 30
        assert result["fatigue_tau_days"] == 5

    def test_missing_keys_fallback_to_defaults(self) -> None:
        row = MagicMock(spec=AthleteFitness)
        row.time_constants = {"fitness_tau_days": 30}  # missing fatigue_tau_days
        result = _read_time_constants(row)
        assert result["fitness_tau_days"] == 30
        assert result["fatigue_tau_days"] == 7  # default

    def test_source_field_included(self) -> None:
        row = MagicMock(spec=AthleteFitness)
        row.time_constants = {"source": "custom_source"}
        result = _read_time_constants(row)
        assert result["source"] == "custom_source"


class TestDaysSince:
    """_days_since helper — Phase 1.6 simplification returns 1."""

    def test_returns_1_when_last_activity_id_is_none(self) -> None:
        """Phase 1.6: returns 1 regardless of reference."""
        result = _days_since(last_activity_id=None, reference=None)
        assert result == 1

    def test_returns_1_when_last_activity_id_provided(self) -> None:
        """Phase 1.6 simplification: days_since always 1."""
        result = _days_since(
            last_activity_id=uuid.uuid4(),
            reference=datetime.now(timezone.utc),
        )
        assert result == 1


class TestBanisterUpdateResult:
    """BanisterUpdateResult is a frozen dataclass."""

    def test_frozen(self) -> None:
        result = BanisterUpdateResult(fitness=100.0, fatigue=50.0, form=50.0)
        with pytest.raises(AttributeError):
            result.fitness = 200.0  # type: ignore

    def test_equality(self) -> None:
        a = BanisterUpdateResult(fitness=100.0, fatigue=50.0, form=50.0)
        b = BanisterUpdateResult(fitness=100.0, fatigue=50.0, form=50.0)
        assert a == b


class TestPopulationConstants:
    """POPULATION_TIME_CONSTANTS — architecture-specified defaults."""

    def test_fitness_tau_is_42_days(self) -> None:
        assert POPULATION_TIME_CONSTANTS["fitness_tau_days"] == 42

    def test_fatigue_tau_is_7_days(self) -> None:
        assert POPULATION_TIME_CONSTANTS["fatigue_tau_days"] == 7

    def test_source_is_population_default(self) -> None:
        assert POPULATION_TIME_CONSTANTS["source"] == "population_default"