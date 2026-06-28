"""Unit tests for ``TwinContextAssembler``.

Tests the deterministic translation of TwinState into coaching language:
- readiness_descriptor mapping
- confidence_descriptor mapping
- fitness_form_descriptor computation
- compute_observations for structural risk flag

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    SportBackground,
    TwinConfidenceLevel,
)
from app.models.twin_state import TwinState
from app.services.twin_context_assembler import (
    AthleteTwinContext,
    ComputedObservations,
    TwinContextAssembler,
    TwinContextSummary,
)


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def assembler() -> TwinContextAssembler:
    return TwinContextAssembler()


def _make_twin_state(
    readiness: RecoveryModifierLevel = RecoveryModifierLevel.GREEN,
    confidence: TwinConfidenceLevel = TwinConfidenceLevel.LOW,
    form: float = 0.0,
    data_tier: int = 5,
) -> MagicMock:
    ts = MagicMock(spec=TwinState)
    ts.id = uuid.uuid4()
    ts.readiness_level = readiness
    ts.confidence_level = confidence
    ts.form = form
    ts.data_tier = data_tier
    return ts


# ---------------------------------------------------------------------------
# readiness_descriptor mapping.
# ---------------------------------------------------------------------------


class TestReadinessDescriptor:
    """``readiness_level`` is mapped to a coaching-friendly descriptor."""

    def test_green_maps_to_full_load(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(readiness=RecoveryModifierLevel.GREEN)
        result = assembler.assemble_twin_context(ts)
        assert result.readiness_descriptor == "ready for full training load"

    def test_amber_maps_to_partial_recovery(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(readiness=RecoveryModifierLevel.AMBER)
        result = assembler.assemble_twin_context(ts)
        assert result.readiness_descriptor == "navigating a partially recovered state"

    def test_red_maps_to_recovery_window(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(readiness=RecoveryModifierLevel.RED)
        result = assembler.assemble_twin_context(ts)
        assert result.readiness_descriptor == "in a recovery window"


# ---------------------------------------------------------------------------
# confidence_descriptor mapping.
# ---------------------------------------------------------------------------


class TestConfidenceDescriptor:
    """``confidence_level`` is mapped to Tier-3 language per architecture."""

    def test_low_maps_to_population_based_estimate(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(confidence=TwinConfidenceLevel.LOW)
        result = assembler.assemble_twin_context(ts)
        assert "population-based estimates" in result.confidence_descriptor
        assert "still learning your training history" in result.confidence_descriptor

    def test_medium_maps_to_building_confidence(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(confidence=TwinConfidenceLevel.MEDIUM)
        result = assembler.assemble_twin_context(ts)
        assert "building confidence in your personal thresholds" in result.confidence_descriptor

    def test_high_maps_to_high_confidence(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(confidence=TwinConfidenceLevel.HIGH)
        result = assembler.assemble_twin_context(ts)
        assert "high confidence in your thresholds" in result.confidence_descriptor


# ---------------------------------------------------------------------------
# fitness_form_descriptor — Banister form score translation.
# ---------------------------------------------------------------------------


class TestFitnessFormDescriptor:
    """The fitness_form_descriptor is a narrative translation of the
    Banister ``form`` score (fitness - fatigue)."""

    def test_negative_form_exceeds_capacity(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(form=-10.0)
        result = assembler.assemble_twin_context(ts)
        assert "exceeds your aerobic capacity" in result.fitness_form_descriptor

    def test_low_positive_form_balanced(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(form=2.0)
        result = assembler.assemble_twin_context(ts)
        assert "balanced" in result.fitness_form_descriptor

    def test_moderate_form_manageable_load(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(form=10.0)
        result = assembler.assemble_twin_context(ts)
        assert "manageable" in result.fitness_form_descriptor

    def test_high_form_fresh_and_well_rested(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(form=25.0)
        result = assembler.assemble_twin_context(ts)
        assert "fresh" in result.fitness_form_descriptor
        assert "well-rested" in result.fitness_form_descriptor


# ---------------------------------------------------------------------------
# assemble_twin_context output shape.
# ---------------------------------------------------------------------------


class TestAssembleTwinContext:
    def test_returns_twin_context_summary(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.assemble_twin_context(ts)
        assert isinstance(result, TwinContextSummary)

    def test_preserves_readiness_level(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(readiness=RecoveryModifierLevel.AMBER)
        result = assembler.assemble_twin_context(ts)
        assert result.readiness_level == RecoveryModifierLevel.AMBER

    def test_preserves_confidence_level(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(confidence=TwinConfidenceLevel.MEDIUM)
        result = assembler.assemble_twin_context(ts)
        assert result.confidence_level == TwinConfidenceLevel.MEDIUM

    def test_preserves_data_tier(self, assembler: TwinContextAssembler) -> None:
        ts = _make_twin_state(data_tier=DataTier.TIER_3)
        result = assembler.assemble_twin_context(ts)
        assert result.data_tier == DataTier.TIER_3


# ---------------------------------------------------------------------------
# compute_observations — structural risk flag.
# ---------------------------------------------------------------------------


class TestComputeObservations:
    def test_structural_risk_flag_true_for_cycling_primary(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.CYCLING_PRIMARY,
            years_structured_training=5,
        )
        assert result.structural_risk_flag is True
        assert result.structural_risk_reason == "non-running primary sport background"

    def test_structural_risk_flag_true_for_swimming_primary(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.SWIMMING_PRIMARY,
            years_structured_training=3,
        )
        assert result.structural_risk_flag is True

    def test_structural_risk_flag_false_for_running_primary(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=5,
        )
        assert result.structural_risk_flag is False
        assert result.structural_risk_reason is None

    def test_training_consistency_signal_when_years_gt_zero(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=3,
        )
        assert "3 year(s) of structured training on record" == result.training_consistency_signal

    def test_training_consistency_signal_none_when_no_years(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=0,
        )
        assert result.training_consistency_signal is None

    def test_aerobic_base_assessment_low_confidence(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(confidence=TwinConfidenceLevel.LOW)
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=1,
        )
        assert "limited running history" in result.aerobic_base_assessment

    def test_aerobic_base_assessment_high_confidence(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state(confidence=TwinConfidenceLevel.HIGH)
        result = assembler.compute_observations(
            twin_state=ts,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=5,
        )
        assert "above-average for age group" in result.aerobic_base_assessment


# ---------------------------------------------------------------------------
# assemble — one-shot bundle.
# ---------------------------------------------------------------------------


class TestAssemble:
    def test_returns_athlete_twin_context(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.assemble(
            twin_state=ts,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=3,
        )
        assert isinstance(result, AthleteTwinContext)
        assert isinstance(result.twin_context, TwinContextSummary)
        assert isinstance(result.computed_observations, ComputedObservations)

    def test_computed_observations_match_compute_observations(
        self, assembler: TwinContextAssembler
    ) -> None:
        ts = _make_twin_state()
        result = assembler.assemble(
            twin_state=ts,
            sport_background=SportBackground.CYCLING_PRIMARY,
            years_structured_training=5,
        )
        assert result.computed_observations.structural_risk_flag is True
        assert result.computed_observations.structural_risk_reason == "non-running primary sport background"