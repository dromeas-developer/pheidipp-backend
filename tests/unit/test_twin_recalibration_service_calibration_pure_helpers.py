"""Unit tests for calibration-trigger pure helpers in ``TwinRecalibrationService``.

Phase-2.3-P3 introduces several module-level pure helpers in
``app/services/twin_recalibration_service.py`` that derive the
``TwinState.confidence_level`` and ``metric_confidence`` from the
updated ``AthletePhysiology`` row, and implement the monotonic
ratchet that prevents confidence from ever decreasing:

* ``_confidence_rank(level)`` — numeric rank of a
  ``TwinConfidenceLevel`` for ordering comparisons.
* ``max_confidence_level(a, b)`` — higher of two
  ``TwinConfidenceLevel`` values.
* ``max_confidence_level_string(previous, computed)`` — higher of
  two confidence-level strings, with ``None`` semantics:
  ``None`` previous + non-null computed resolves to computed
  (null means "no data", not "low confidence").
* ``derive_confidence_level(physiology)`` — global level =
  ``min(lt1.hr.prior_weight, lt2.hr.prior_weight)`` mapped through
  the 4.0 / 8.0 thresholds.
* ``prior_weight_to_level(prior_weight)`` — maps a prior weight
  to a ``TwinConfidenceLevel`` using the 4.0 / 8.0 thresholds.
* ``state_prior_weight(state)`` — extracts the ``prior_weight``
  from a ``PhysiologyParameterState`` dict.
* ``min_prior_weight(a, b)`` — minimum of two prior weights,
  treating ``None`` as 0.
* ``extract_param_value(container, sub_key)`` — extracts the
  ``value`` field of a ``PhysiologyParameterState`` sub-state for
  the inline threshold snapshot on the calibration TwinState.

These helpers are private (underscore-prefixed) but module-level and
directly importable for unit testing. The pure-helper unit tests
do not require a session, repository, or event publisher — they
exercise the formula behaviour directly.

Reference plan: docs/implementation/phase-2/phase-2-3-p3-twin-recalibration-pipeline.md
Reference architecture: docs/architecture/00-foundations/confidence-model.md
Reference ADR: docs/adr/011-confidence-monotonicity-ratchet-location.md
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import TwinConfidenceLevel
from app.services.twin_recalibration_service import (
    confidence_rank,
    derive_confidence_level,
    extract_param_value,
    max_confidence_level,
    max_confidence_level_string,
    min_prior_weight,
    prior_weight_to_level,
    state_prior_weight,
)


# ---------------------------------------------------------------------------
# Helpers — build the JSONB dict shapes the pure helpers consume.
# ---------------------------------------------------------------------------


def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-05-01",
) -> Dict[str, Any]:
    """Build a ``PhysiologyParameterState`` dict."""
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }


def _physiology_row(
    *,
    lt1: Optional[Dict[str, Any]] = None,
    lt2: Optional[Dict[str, Any]] = None,
    cp: Optional[Dict[str, Any]] = None,
    max_hr: Optional[Dict[str, Any]] = None,
) -> AthletePhysiology:
    """Build an in-memory ``AthletePhysiology`` row with the given
    JSONB columns. ``lt1`` and ``lt2`` default to the empty
    three-dimension container so the row is constructible without
    raising on the non-nullable columns."""
    return AthletePhysiology(
        athlete_id=uuid.uuid4(),
        lt1=lt1 if lt1 is not None else {"hr": None, "power": None, "pace": None},
        lt2=lt2 if lt2 is not None else {"hr": None, "power": None, "pace": None},
        cp=cp,
        max_hr=max_hr,
    )


# ---------------------------------------------------------------------------
# _confidence_rank — numeric ordering of TwinConfidenceLevel.
# ---------------------------------------------------------------------------


class TestConfidenceRank:
    """``_confidence_rank`` assigns a numeric rank to each
    ``TwinConfidenceLevel`` so the ratchet can compare levels
    without string comparison."""

    def test_low_is_rank_zero(self) -> None:
        assert confidence_rank(TwinConfidenceLevel.LOW) == 0

    def test_medium_is_rank_one(self) -> None:
        assert confidence_rank(TwinConfidenceLevel.MEDIUM) == 1

    def test_high_is_rank_two(self) -> None:
        assert confidence_rank(TwinConfidenceLevel.HIGH) == 2

    def test_rank_ordering_matches_value_ordering(self) -> None:
        """LOW < MEDIUM < HIGH."""
        assert (
            confidence_rank(TwinConfidenceLevel.LOW)
            < confidence_rank(TwinConfidenceLevel.MEDIUM)
            < confidence_rank(TwinConfidenceLevel.HIGH)
        )


# ---------------------------------------------------------------------------
# max_confidence_level — global confidence ratchet.
# ---------------------------------------------------------------------------


class TestMaxConfidenceLevel:
    """``max_confidence_level`` returns the higher of two levels —
    the global ratchet that prevents ``confidence_level`` from
    ever decreasing across consecutive TwinStates."""

    def test_returns_a_when_a_is_higher(self) -> None:
        result = max_confidence_level(
            TwinConfidenceLevel.HIGH, TwinConfidenceLevel.MEDIUM
        )
        assert result == TwinConfidenceLevel.HIGH

    def test_returns_b_when_b_is_higher(self) -> None:
        result = max_confidence_level(
            TwinConfidenceLevel.MEDIUM, TwinConfidenceLevel.HIGH
        )
        assert result == TwinConfidenceLevel.HIGH

    def test_returns_a_when_both_equal(self) -> None:
        result = max_confidence_level(
            TwinConfidenceLevel.MEDIUM, TwinConfidenceLevel.MEDIUM
        )
        assert result == TwinConfidenceLevel.MEDIUM

    def test_low_and_medium_resolves_to_medium(self) -> None:
        result = max_confidence_level(
            TwinConfidenceLevel.LOW, TwinConfidenceLevel.MEDIUM
        )
        assert result == TwinConfidenceLevel.MEDIUM

    def test_low_and_high_resolves_to_high(self) -> None:
        result = max_confidence_level(
            TwinConfidenceLevel.LOW, TwinConfidenceLevel.HIGH
        )
        assert result == TwinConfidenceLevel.HIGH

    def test_monotonicity_invariant_preserved(self) -> None:
        """The ratchet preserves monotonicity: the returned level is
        never lower than either input."""
        levels = [
            TwinConfidenceLevel.LOW,
            TwinConfidenceLevel.MEDIUM,
            TwinConfidenceLevel.HIGH,
        ]
        for a in levels:
            for b in levels:
                result = max_confidence_level(a, b)
                assert confidence_rank(result) >= confidence_rank(a)
                assert confidence_rank(result) >= confidence_rank(b)


# ---------------------------------------------------------------------------
# max_confidence_level_string — per-metric confidence ratchet (ADR-011).
# ---------------------------------------------------------------------------


class TestMaxConfidenceLevelString:
    """``max_confidence_level_string`` applies the per-metric
    monotonicity ratchet for ``metric_confidence`` values stored
    as strings. The ``None`` semantics are critical: a ``None``
    previous value means "no data before", not "low confidence",
    so a non-null computed value wins in that case."""

    def test_none_previous_returns_computed(self) -> None:
        """No previous data (None) — computed value wins regardless
        of its tier. ``None`` means "no data", not "low confidence"."""
        assert max_confidence_level_string(None, "medium") == "medium"
        assert max_confidence_level_string(None, "low") == "low"
        assert max_confidence_level_string(None, "high") == "high"

    def test_none_computed_returns_previous(self) -> None:
        """No current data (None computed) — previous value is
        preserved so a metric does not drop to "no data" while
        a prior observation still exists."""
        assert max_confidence_level_string("medium", None) == "medium"
        assert max_confidence_level_string("high", None) == "high"
        assert max_confidence_level_string("low", None) == "low"

    def test_both_none_returns_none(self) -> None:
        """No previous and no current data — returns ``None``."""
        assert max_confidence_level_string(None, None) is None

    def test_higher_computed_wins(self) -> None:
        """When computed is higher than previous, computed wins."""
        assert max_confidence_level_string("low", "medium") == "medium"
        assert max_confidence_level_string("medium", "high") == "high"
        assert max_confidence_level_string("low", "high") == "high"

    def test_lower_computed_preserves_previous(self) -> None:
        """When computed is lower than previous, previous wins.
        This is the ratchet: a metric that previously reached
        MEDIUM stays MEDIUM even if prior_weight has decayed."""
        assert max_confidence_level_string("medium", "low") == "medium"
        assert max_confidence_level_string("high", "medium") == "high"
        assert max_confidence_level_string("high", "low") == "high"

    def test_equal_values_preserved(self) -> None:
        """When previous and computed are equal, the previous wins
        (the ratchet prefers to keep the existing snapshot)."""
        assert max_confidence_level_string("medium", "medium") == "medium"
        assert max_confidence_level_string("high", "high") == "high"
        assert max_confidence_level_string("low", "low") == "low"

    def test_metric_with_no_data_then_appears(self) -> None:
        """A metric that had no data before but now has data:
        computed value wins. ``None`` previous + non-null
        computed → computed."""
        # Scenario: lt1_power was null before (no power data),
        # now an observation produced a "medium" confidence.
        assert max_confidence_level_string(None, "medium") == "medium"


# ---------------------------------------------------------------------------
# state_prior_weight — extract prior_weight from a parameter state.
# ---------------------------------------------------------------------------


class TestStatePriorWeight:
    """``state_prior_weight`` defensively extracts the
    ``prior_weight`` field from a ``PhysiologyParameterState`` dict."""

    def test_returns_weight_when_present(self) -> None:
        state = _state(prior_weight=3.5)
        assert state_prior_weight(state) == 3.5

    def test_returns_none_when_state_is_none(self) -> None:
        assert state_prior_weight(None) is None

    def test_returns_none_when_key_missing(self) -> None:
        """A state dict without ``prior_weight`` resolves to
        ``None`` (treated as zero by ``min_prior_weight``)."""
        state = {"value": 165.0, "uncertainty": 1.0}
        assert state_prior_weight(state) is None  # type: ignore[arg-type]

    def test_returns_zero_for_explicit_zero_weight(self) -> None:
        state = _state(prior_weight=0.0)
        assert state_prior_weight(state) == 0.0


# ---------------------------------------------------------------------------
# min_prior_weight — weakest-link drive of global confidence.
# ---------------------------------------------------------------------------


class TestMinPriorWeight:
    """``min_prior_weight`` returns the smaller of two prior
    weights, treating ``None`` as zero. The global
    ``confidence_level`` is the minimum across the HR parameters —
    the weakest link drives the global level."""

    def test_returns_smaller_of_two_values(self) -> None:
        assert min_prior_weight(3.0, 5.0) == 3.0
        assert min_prior_weight(8.5, 2.0) == 2.0

    def test_returns_zero_when_one_is_none(self) -> None:
        """A ``None`` weight means "no data yet" — treated as 0."""
        assert min_prior_weight(None, 5.0) == 0.0
        assert min_prior_weight(5.0, None) == 0.0

    def test_returns_zero_when_both_none(self) -> None:
        assert min_prior_weight(None, None) == 0.0

    def test_returns_value_when_both_equal(self) -> None:
        assert min_prior_weight(4.0, 4.0) == 4.0


# ---------------------------------------------------------------------------
# prior_weight_to_level — 4.0 / 8.0 threshold mapping.
# ---------------------------------------------------------------------------


class TestPriorWeightToLevel:
    """``prior_weight_to_level`` maps a prior weight to a
    ``TwinConfidenceLevel`` using the 4.0 / 8.0 thresholds from
    the confidence model. A ``None`` weight resolves to ``LOW``."""

    def test_zero_weight_is_low(self) -> None:
        assert (
            prior_weight_to_level(0.0) == TwinConfidenceLevel.LOW
        )

    def test_just_below_4_is_low(self) -> None:
        """prior_weight = 3.99 → LOW (strict less than 4.0)."""
        assert (
            prior_weight_to_level(3.99) == TwinConfidenceLevel.LOW
        )

    def test_exactly_4_is_medium(self) -> None:
        """prior_weight = 4.0 → MEDIUM (inclusive boundary)."""
        assert (
            prior_weight_to_level(4.0) == TwinConfidenceLevel.MEDIUM
        )

    def test_between_4_and_8_is_medium(self) -> None:
        assert (
            prior_weight_to_level(5.0) == TwinConfidenceLevel.MEDIUM
        )
        assert (
            prior_weight_to_level(7.99) == TwinConfidenceLevel.MEDIUM
        )

    def test_exactly_8_is_high(self) -> None:
        """prior_weight = 8.0 → HIGH (inclusive boundary)."""
        assert (
            prior_weight_to_level(8.0) == TwinConfidenceLevel.HIGH
        )

    def test_above_8_is_high(self) -> None:
        assert (
            prior_weight_to_level(12.0) == TwinConfidenceLevel.HIGH
        )
        assert (
            prior_weight_to_level(100.0) == TwinConfidenceLevel.HIGH
        )

    def test_none_weight_is_low(self) -> None:
        """A ``None`` prior weight (no data yet) resolves to
        ``LOW`` — the default before any observations."""
        assert (
            prior_weight_to_level(None) == TwinConfidenceLevel.LOW
        )


# ---------------------------------------------------------------------------
# derive_confidence_level — global confidence from physiology state.
# ---------------------------------------------------------------------------


class TestDeriveConfidenceLevel:
    """``derive_confidence_level`` derives the global
    ``confidence_level`` from the updated ``AthletePhysiology``
    row. Global level =
    ``min(lt1.hr.prior_weight, lt2.hr.prior_weight)`` mapped
    through the 4.0 / 8.0 thresholds."""

    def test_below_threshold_resolves_to_low(self) -> None:
        """Both lt1.hr and lt2.hr prior_weight below 4.0 → LOW."""
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=2.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=3.0), "power": None, "pace": None},
        )
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_one_above_4_drives_medium(self) -> None:
        """Min(lt1.hr=2.0, lt2.hr=5.0) = 2.0 → LOW. The
        global level follows the weakest link."""
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=2.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_both_above_4_drives_medium(self) -> None:
        """Min(lt1.hr=5.0, lt2.hr=6.0) = 5.0 → MEDIUM."""
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=6.0), "power": None, "pace": None},
        )
        assert (
            derive_confidence_level(physiology) == TwinConfidenceLevel.MEDIUM
        )

    def test_both_above_8_drives_high(self) -> None:
        """Min(lt1.hr=10.0, lt2.hr=12.0) = 10.0 → HIGH."""
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=12.0), "power": None, "pace": None},
        )
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.HIGH

    def test_one_above_8_drives_medium(self) -> None:
        """Min(lt1.hr=3.0, lt2.hr=10.0) = 3.0 → LOW (weakest link)."""
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=3.0), "power": None, "pace": None},
            lt2={"hr": _state(prior_weight=10.0), "power": None, "pace": None},
        )
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_no_hr_data_resolves_to_low(self) -> None:
        """Both lt1.hr and lt2.hr are ``None`` (no HR data) → LOW."""
        physiology = _physiology_row(
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_lt1_null_outer_resolves_to_low(self) -> None:
        """A ``None`` ``lt1`` outer column (no bootstrap) is
        treated as 0 by the minimum, so the global is LOW."""
        physiology = _physiology_row(lt1=None, lt2=None)
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_only_lt1_hr_drives_global(self) -> None:
        """When lt2 has no HR data, lt1.hr alone drives the
        global — it is the only available HR anchor."""
        physiology = _physiology_row(
            lt1={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
            lt2=None,
        )
        # Min(5.0, 0) = 0 → LOW. The weakest link applies even
        # when only one HR parameter has data.
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_only_lt2_hr_drives_global(self) -> None:
        """When lt1 has no HR data, lt2.hr alone drives the
        global — the min still includes the missing side as 0."""
        physiology = _physiology_row(
            lt1=None,
            lt2={"hr": _state(prior_weight=5.0), "power": None, "pace": None},
        )
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW

    def test_power_and_pace_do_not_drive_global(self) -> None:
        """Only lt1.hr and lt2.hr drive the global — power/pace
        sub-states do not contribute."""
        physiology = _physiology_row(
            lt1={
                "hr": _state(prior_weight=1.0),
                "power": _state(prior_weight=10.0),
                "pace": _state(prior_weight=10.0),
            },
            lt2={
                "hr": _state(prior_weight=1.0),
                "power": _state(prior_weight=10.0),
                "pace": _state(prior_weight=10.0),
            },
        )
        # Min(1.0, 1.0) = 1.0 → LOW (the HR anchors drive it).
        assert derive_confidence_level(physiology) == TwinConfidenceLevel.LOW


# ---------------------------------------------------------------------------
# extract_param_value — inline threshold snapshot field extraction.
# ---------------------------------------------------------------------------


class TestExtractParamValue:
    """``extract_param_value`` returns the ``value`` field of a
    ``PhysiologyParameterState`` sub-state for the inline
    threshold snapshot on the calibration TwinState
    (``lt1_hr_bpm``, ``lt2_hr_bpm``). Returns ``None`` when the
    outer container or sub-state is missing."""

    def test_returns_value_when_present(self) -> None:
        container = {"hr": {"value": 165.0, "prior_weight": 3.0}}
        assert extract_param_value(container, "hr") == 165.0

    def test_returns_none_when_container_is_none(self) -> None:
        assert extract_param_value(None, "hr") is None

    def test_returns_none_when_container_is_empty(self) -> None:
        assert extract_param_value({}, "hr") is None

    def test_returns_none_when_sub_state_is_none(self) -> None:
        container = {"hr": None, "power": None, "pace": None}
        assert extract_param_value(container, "hr") is None

    def test_returns_none_when_sub_state_missing(self) -> None:
        container = {"power": {"value": 200.0}}
        assert extract_param_value(container, "hr") is None

    def test_returns_none_when_value_field_missing(self) -> None:
        container = {"hr": {"prior_weight": 3.0}}  # no "value" key
        assert extract_param_value(container, "hr") is None

    def test_returns_none_when_value_is_none(self) -> None:
        container = {"hr": {"value": None, "prior_weight": 3.0}}
        assert extract_param_value(container, "hr") is None

    def test_extracts_lt1_hr_for_calibration_twin_state(self) -> None:
        """The calibration TwinState uses ``extract_param_value``
        to populate ``lt1_hr_bpm`` from the updated physiology."""
        lt1 = {"hr": {"value": 162.0, "prior_weight": 3.5}}
        assert extract_param_value(lt1, "hr") == 162.0

    def test_extracts_lt2_hr_for_calibration_twin_state(self) -> None:
        """The calibration TwinState uses ``extract_param_value``
        to populate ``lt2_hr_bpm`` from the updated physiology."""
        lt2 = {"hr": {"value": 178.0, "prior_weight": 5.0}}
        assert extract_param_value(lt2, "hr") == 178.0
