"""Unit tests for the pure helpers in ``PhysiologyUpdateService``.

Phase-2.3-P2 introduces several module-level pure helpers in
``app/services/physiology_update_service.py`` that derive per-metric
confidence levels and detect monotonic confidence transitions:

* ``confidence_level(prior_weight)`` — maps a prior weight to a
  ``TwinConfidenceLevel`` value string using the 4.0 / 8.0 thresholds.
* ``state_prior_weight(state)`` — extracts the prior weight from a
  ``PhysiologyParameterState`` dict.
* ``compute_metric_confidence(physiology)`` — returns the per-metric
  confidence dict in ``TwinState`` shape.
* ``detect_confidence_transitions(old, new)`` — returns the
  monotonic LOW→MEDIUM and MEDIUM→HIGH transitions between two
  per-metric confidence snapshots.
* ``parse_iso_date(value)`` — parses the JSONB
  ``last_observation_date`` string.
* ``coerce_observation_date(value)`` — coerces an observation date
  to ``datetime.date``.
* ``source_value(source)`` — returns the ``MeasurementSource.value``
  string.

These helpers are private (underscore-prefixed) but module-level and
directly importable for unit testing.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/00-foundations/confidence-model.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

import pytest

from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import (
    MeasurementSource,
    TwinConfidenceLevel,
)
from app.services.physiology_update_service import (
    coerce_observation_date,
    compute_metric_confidence,
    confidence_level,
    detect_confidence_transitions,
    parse_iso_date,
    source_value,
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
# confidence_level — prior weight → TwinConfidenceLevel mapping.
# ---------------------------------------------------------------------------


class TestConfidenceLevel:
    """``confidence_level`` maps a prior weight to LOW / MEDIUM / HIGH
    using the 4.0 / 8.0 thresholds from the confidence model."""

    def test_prior_weight_above_eight_returns_high(self) -> None:
        """``prior_weight >= 8.0`` → ``"high"``."""
        assert confidence_level(8.0) == TwinConfidenceLevel.HIGH.value
        assert confidence_level(10.0) == TwinConfidenceLevel.HIGH.value
        assert confidence_level(100.0) == TwinConfidenceLevel.HIGH.value

    def test_prior_weight_between_four_and_eight_returns_medium(self) -> None:
        """``4.0 <= prior_weight < 8.0`` → ``"medium"``."""
        assert confidence_level(4.0) == TwinConfidenceLevel.MEDIUM.value
        assert confidence_level(5.0) == TwinConfidenceLevel.MEDIUM.value
        assert confidence_level(7.99) == TwinConfidenceLevel.MEDIUM.value

    def test_prior_weight_below_four_returns_low(self) -> None:
        """``prior_weight < 4.0`` → ``"low"``."""
        assert confidence_level(0.0) == TwinConfidenceLevel.LOW.value
        assert confidence_level(1.0) == TwinConfidenceLevel.LOW.value
        assert confidence_level(3.99) == TwinConfidenceLevel.LOW.value

    def test_none_prior_weight_returns_low(self) -> None:
        """``None`` prior weight (no evidence yet) → ``"low"``."""
        assert confidence_level(None) == TwinConfidenceLevel.LOW.value

    def test_exact_threshold_eight_is_high(self) -> None:
        """The 8.0 threshold is inclusive (``>=``) — exactly 8.0 is HIGH."""
        assert confidence_level(8.0) == "high"

    def test_exact_threshold_four_is_medium(self) -> None:
        """The 4.0 threshold is inclusive (``>=``) — exactly 4.0 is MEDIUM."""
        assert confidence_level(4.0) == "medium"


# ---------------------------------------------------------------------------
# state_prior_weight — extract prior weight from a state dict.
# ---------------------------------------------------------------------------


class TestStatePriorWeight:
    """``state_prior_weight`` extracts the ``prior_weight`` from a
    ``PhysiologyParameterState`` dict, returning ``None`` for missing
    or null states."""

    def test_returns_prior_weight_from_state(self) -> None:
        """A state with a prior_weight returns it as a float."""
        state = _state(prior_weight=3.5)
        assert state_prior_weight(state) == 3.5

    def test_returns_none_for_none_state(self) -> None:
        """A ``None`` state returns ``None``."""
        assert state_prior_weight(None) is None

    def test_returns_none_when_prior_weight_key_missing(self) -> None:
        """A state dict missing the ``prior_weight`` key returns ``None``."""
        state = {"value": 165.0, "uncertainty": 1.0}
        assert state_prior_weight(state) is None

    def test_returns_none_when_prior_weight_is_none(self) -> None:
        """A state dict with ``prior_weight=None`` returns ``None``."""
        state = _state()
        state["prior_weight"] = None
        assert state_prior_weight(state) is None

    def test_returns_float_for_integer_prior_weight(self) -> None:
        """An integer prior_weight is returned as a float."""
        state = _state()
        state["prior_weight"] = 4  # int, not float
        result = state_prior_weight(state)
        assert result == 4.0
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# compute_metric_confidence — per-metric confidence dict.
# ---------------------------------------------------------------------------


class TestComputeMetricConfidence:
    """``compute_metric_confidence`` returns a per-metric dict in
    ``TwinState`` shape, mapping prior weights to LOW / MEDIUM / HIGH."""

    def test_returns_seven_keys(self) -> None:
        """The returned dict has exactly seven keys — the per-signal
        LT1 / LT2 sub-states plus CP."""
        physiology = _physiology_row()
        result = compute_metric_confidence(physiology)
        assert set(result.keys()) == {
            "lt1_hr",
            "lt1_power",
            "lt1_pace",
            "lt2_hr",
            "lt2_power",
            "lt2_pace",
            "cp",
        }

    def test_all_null_states_return_low(self) -> None:
        """When every parameter state is null, every metric is LOW."""
        physiology = _physiology_row()
        result = compute_metric_confidence(physiology)
        for level in result.values():
            assert level == TwinConfidenceLevel.LOW.value

    def test_lt1_hr_high_when_prior_weight_above_eight(self) -> None:
        """``lt1_hr`` is HIGH when its prior_weight >= 8.0."""
        physiology = _physiology_row(
            lt1={
                "hr": _state(prior_weight=10.0),
                "power": None,
                "pace": None,
            },
        )
        result = compute_metric_confidence(physiology)
        assert result["lt1_hr"] == "high"

    def test_lt2_hr_medium_when_prior_weight_between_four_and_eight(
        self,
    ) -> None:
        """``lt2_hr`` is MEDIUM when its prior_weight is in [4.0, 8.0)."""
        physiology = _physiology_row(
            lt2={
                "hr": _state(prior_weight=5.0),
                "power": None,
                "pace": None,
            },
        )
        result = compute_metric_confidence(physiology)
        assert result["lt2_hr"] == "medium"

    def test_cp_low_when_null(self) -> None:
        """``cp`` is LOW when ``physiology.cp`` is null (no qualifying
        observation yet)."""
        physiology = _physiology_row(cp=None)
        result = compute_metric_confidence(physiology)
        assert result["cp"] == "low"

    def test_cp_high_when_prior_weight_above_eight(self) -> None:
        """``cp`` is HIGH when its prior_weight >= 8.0."""
        physiology = _physiology_row(cp=_state(prior_weight=12.0))
        result = compute_metric_confidence(physiology)
        assert result["cp"] == "high"

    def test_per_signal_sub_states_read_independently(self) -> None:
        """Each LT1 / LT2 sub-state (hr / power / pace) is read
        independently — a high HR state does not bleed into the
        power or pace levels."""
        physiology = _physiology_row(
            lt1={
                "hr": _state(prior_weight=10.0),  # HIGH
                "power": _state(prior_weight=0.5),  # LOW
                "pace": _state(prior_weight=5.0),  # MEDIUM
            },
        )
        result = compute_metric_confidence(physiology)
        assert result["lt1_hr"] == "high"
        assert result["lt1_power"] == "low"
        assert result["lt1_pace"] == "medium"

    def test_null_lt1_container_returns_low_for_all_sub_states(self) -> None:
        """A null ``lt1`` container (defensive — non-nullable in
        practice) returns LOW for every sub-state."""
        physiology = _physiology_row(lt1=None)
        result = compute_metric_confidence(physiology)
        assert result["lt1_hr"] == "low"
        assert result["lt1_power"] == "low"
        assert result["lt1_pace"] == "low"


# ---------------------------------------------------------------------------
# detect_confidence_transitions — monotonic upward transitions.
# ---------------------------------------------------------------------------


class TestDetectConfidenceTransitions:
    """``detect_confidence_transitions`` returns a per-metric dict of
    ``(from_level, to_level)`` tuples for monotonic LOW→MEDIUM and
    MEDIUM→HIGH transitions. Downward changes are never transitions."""

    def test_low_to_medium_reported(self) -> None:
        """A LOW→MEDIUM transition is reported."""
        old = {"lt2_hr": "low"}
        new = {"lt2_hr": "medium"}
        result = detect_confidence_transitions(old, new)
        assert result == {"lt2_hr": ("low", "medium")}

    def test_medium_to_high_reported(self) -> None:
        """A MEDIUM→HIGH transition is reported."""
        old = {"lt2_hr": "medium"}
        new = {"lt2_hr": "high"}
        result = detect_confidence_transitions(old, new)
        assert result == {"lt2_hr": ("medium", "high")}

    def test_low_to_high_reported_as_single_transition(self) -> None:
        """A LOW→HIGH transition is reported as a single entry
        (not two separate transitions)."""
        old = {"lt2_hr": "low"}
        new = {"lt2_hr": "high"}
        result = detect_confidence_transitions(old, new)
        assert result == {"lt2_hr": ("low", "high")}

    def test_no_change_returns_empty_dict(self) -> None:
        """Equal levels (LOW→LOW, MEDIUM→MEDIUM, HIGH→HIGH) produce
        no transitions."""
        old = {"lt2_hr": "medium", "cp": "high"}
        new = {"lt2_hr": "medium", "cp": "high"}
        result = detect_confidence_transitions(old, new)
        assert result == {}

    def test_high_to_low_not_reported(self) -> None:
        """A HIGH→LOW downward change is NOT a transition — confidence
        is ratcheting and never decreases."""
        old = {"lt2_hr": "high"}
        new = {"lt2_hr": "low"}
        result = detect_confidence_transitions(old, new)
        assert result == {}

    def test_medium_to_low_not_reported(self) -> None:
        """A MEDIUM→LOW downward change is NOT a transition."""
        old = {"lt2_hr": "medium"}
        new = {"lt2_hr": "low"}
        result = detect_confidence_transitions(old, new)
        assert result == {}

    def test_none_old_level_normalised_to_low(self) -> None:
        """A ``None`` old level is normalised to LOW for the
        comparison — a metric going from ``None`` (no observation)
        to MEDIUM on first observation counts as a transition."""
        old: Dict[str, Optional[str]] = {"lt2_hr": None}
        new = {"lt2_hr": "medium"}
        result = detect_confidence_transitions(old, new)
        assert result == {"lt2_hr": (None, "medium")}

    def test_missing_metric_in_old_treated_as_none(self) -> None:
        """A metric present in ``new`` but missing from ``old`` is
        treated as ``None`` (normalised to LOW for the comparison)."""
        old: Dict[str, Optional[str]] = {}
        new = {"lt2_hr": "medium"}
        result = detect_confidence_transitions(old, new)
        assert result == {"lt2_hr": (None, "medium")}

    def test_multiple_transitions_reported_independently(self) -> None:
        """Multiple metrics transitioning in the same call are all
        reported, each with its own (from, to) tuple."""
        old = {"lt1_hr": "low", "lt2_hr": "medium", "cp": "low"}
        new = {"lt1_hr": "medium", "lt2_hr": "high", "cp": "low"}
        result = detect_confidence_transitions(old, new)
        assert result == {
            "lt1_hr": ("low", "medium"),
            "lt2_hr": ("medium", "high"),
        }

    def test_unknown_level_string_skipped(self) -> None:
        """An unknown level string (not in LOW / MEDIUM / HIGH) is
        skipped defensively — the surrounding pipeline does not
        crash on a malformed JSONB value."""
        old = {"lt2_hr": "very_high"}  # not in _CONFIDENCE_LEVEL_ORDER
        new = {"lt2_hr": "high"}
        result = detect_confidence_transitions(old, new)
        assert result == {}


# ---------------------------------------------------------------------------
# parse_iso_date — JSONB last_observation_date parsing.
# ---------------------------------------------------------------------------


class TestParseIsoDate:
    """``parse_iso_date`` parses the JSONB ``last_observation_date``
    string into a ``datetime.date``."""

    def test_bare_date_string(self) -> None:
        """A bare ``YYYY-MM-DD`` string parses to a date."""
        result = parse_iso_date("2026-05-12")
        assert result == date(2026, 5, 12)
        assert isinstance(result, date)

    def test_iso_datetime_string(self) -> None:
        """A full ISO-8601 datetime string parses to its date component."""
        result = parse_iso_date("2026-05-12T08:30:00+00:00")
        assert result == date(2026, 5, 12)

    def test_iso_datetime_string_no_timezone(self) -> None:
        """An ISO datetime string without a timezone parses to its
        date component."""
        result = parse_iso_date("2026-05-12T08:30:00")
        assert result == date(2026, 5, 12)

    def test_date_instance_returned_as_is(self) -> None:
        """A ``date`` instance is returned as-is (not re-parsed)."""
        d = date(2026, 5, 12)
        result = parse_iso_date(d)
        assert result is d

    def test_datetime_instance_truncated_to_date(self) -> None:
        """A ``datetime`` instance is truncated to its date component."""
        dt = datetime(2026, 5, 12, 8, 30, tzinfo=timezone.utc)
        result = parse_iso_date(dt)
        assert result == date(2026, 5, 12)
        assert isinstance(result, date)

    def test_unsupported_type_raises_type_error(self) -> None:
        """A non-date / non-datetime / non-string value raises
        ``TypeError``."""
        with pytest.raises(TypeError, match="unsupported last_observation_date"):
            parse_iso_date(12345)


# ---------------------------------------------------------------------------
# coerce_observation_date — observation date coercion.
# ---------------------------------------------------------------------------


class TestCoerceObservationDate:
    """``coerce_observation_date`` coerces an observation date value
    to ``datetime.date``."""

    def test_date_instance_returned_as_is(self) -> None:
        """A ``date`` instance is returned as-is."""
        d = date(2026, 6, 15)
        result = coerce_observation_date(d)
        assert result is d

    def test_datetime_instance_truncated_to_date(self) -> None:
        """A ``datetime`` instance is truncated to its date component."""
        dt = datetime(2026, 6, 15, 14, 30, tzinfo=timezone.utc)
        result = coerce_observation_date(dt)
        assert result == date(2026, 6, 15)
        assert isinstance(result, date)

    def test_unsupported_type_raises_type_error(self) -> None:
        """A non-date / non-datetime value raises ``TypeError``."""
        with pytest.raises(TypeError, match="unsupported observation date"):
            coerce_observation_date("2026-06-15")


# ---------------------------------------------------------------------------
# source_value — MeasurementSource.value extraction.
# ---------------------------------------------------------------------------


class TestSourceValue:
    """``source_value`` returns the ``MeasurementSource.value`` string
    for a source value."""

    def test_enum_member_returns_value_string(self) -> None:
        """A ``MeasurementSource`` enum member returns its ``.value``."""
        result = source_value(MeasurementSource.TRAINING_HR_DEFLECTION)
        assert result == "training_hr_deflection"

    def test_pre_stringified_value_returned_as_is(self) -> None:
        """A pre-stringified value is returned as-is (defensive —
        JSONB round-trips can hand back plain strings)."""
        result = source_value("training_rr_inflection")
        assert result == "training_rr_inflection"
