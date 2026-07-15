"""Unit tests for the Bayesian update pure function and result dataclass.

Phase-2.3-P2 introduces ``bayesian_update`` and
``init_null_parameter_state`` as module-level pure functions in
``app/services/physiology_update_service.py``. They implement the
posterior-mean / posterior-uncertainty / prior-decay formula from
``docs/architecture/02-computations/physiology-update.md`` and are
the foundation of the ``PhysiologyUpdateService`` orchestration.

This test module covers:

* ``bayesian_update()`` — posterior mean, uncertainty floor,
  dominant-source derivation, prior decay, date parsing.
* ``init_null_parameter_state()`` — first-observation bootstrap.
* ``PhysiologyUpdateResult`` dataclass — fields and defaults.

Reference plan: docs/implementation/phase-2/phase-2-3-p2-physiology-update.md
Reference architecture: docs/architecture/02-computations/physiology-update.md
"""

from __future__ import annotations

import math
import uuid
from dataclasses import fields, is_dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict

import pytest

from app.models.athlete_physiology import AthletePhysiology
from app.models.enums import (
    MeasurementSource,
    PhysiologyParameter,
    TwinConfidenceLevel,
)
from app.services.physiology_update_service import (
    DECAY_TIME_CONSTANT_DAYS,
    INITIAL_UNCERTAINTY,
    PhysiologyUpdateResult,
    UNCERTAINTY_FLOOR,
    bayesian_update,
    init_null_parameter_state,
)


# ---------------------------------------------------------------------------
# Helpers — build the JSONB dict shapes the pure functions consume.
# ---------------------------------------------------------------------------


def _state(
    *,
    value: float = 165.0,
    uncertainty: float = 1.0,
    prior_weight: float = 0.5,
    dominant_source: str = "training_hr_deflection",
    last_observation_date: str = "2026-05-01",
) -> Dict[str, Any]:
    """Build a ``PhysiologyParameterState`` dict for ``bayesian_update``."""
    return {
        "value": value,
        "uncertainty": uncertainty,
        "prior_weight": prior_weight,
        "dominant_source": dominant_source,
        "last_observation_date": last_observation_date,
    }


def _observation(
    *,
    value: float = 170.0,
    weight: float = 1.0,
    obs_date: date | datetime = date(2026, 6, 15),
    source: Any = MeasurementSource.TRAINING_HR_DEFLECTION,
) -> Dict[str, Any]:
    """Build an observation dict for ``bayesian_update`` /
    ``init_null_parameter_state``."""
    return {
        "value": value,
        "weight": weight,
        "date": obs_date,
        "source": source,
    }


# ---------------------------------------------------------------------------
# Constants — sanity-check the architecture values are wired in.
# ---------------------------------------------------------------------------


class TestArchitectureConstants:
    """The pure-function constants must match the architecture contract."""

    def test_decay_time_constant_is_42_days(self) -> None:
        """42-day prior decay time constant — the architecture's
        aerobic-fitness time constant in the Banister model."""
        assert DECAY_TIME_CONSTANT_DAYS == 42.0

    def test_uncertainty_floor_is_half(self) -> None:
        """Posterior uncertainty never drops below 0.5 — irreducible
        measurement noise."""
        assert UNCERTAINTY_FLOOR == 0.5

    def test_initial_uncertainty_is_one(self) -> None:
        """Default uncertainty applied when bootstrapping a parameter
        state from scratch (e.g. first CP observation)."""
        assert INITIAL_UNCERTAINTY == 1.0


# ---------------------------------------------------------------------------
# bayesian_update — posterior mean.
# ---------------------------------------------------------------------------


class TestBayesianUpdatePosteriorMean:
    """``bayesian_update`` returns a posterior mean equal to the
    decayed-prior-weighted blend of current and observation values."""

    def test_posterior_mean_between_current_and_observation(self) -> None:
        """Given current=165, observation=170, weight=1.0, prior_weight=0.5,
        the posterior mean is between 165 and 170 (weighted toward the
        prior due to low observation weight)."""
        current = _state(value=165.0, prior_weight=0.5)
        observation = _observation(value=170.0, weight=1.0)

        result = bayesian_update(current, observation)

        assert 165.0 < result["value"] < 170.0

    def test_posterior_mean_weighted_toward_prior_when_obs_weight_low(
        self,
    ) -> None:
        """A low-weight observation barely moves the posterior from the
        prior value."""
        current = _state(value=165.0, prior_weight=10.0)
        observation = _observation(value=170.0, weight=0.1)

        result = bayesian_update(current, observation)

        # With prior_weight=10 and obs_weight=0.1, the posterior is
        # dominated by the prior (165). The observation nudges it
        # toward 170 but only slightly.
        assert result["value"] < 166.0
        assert result["value"] > 165.0

    def test_posterior_mean_weighted_toward_observation_when_obs_weight_high(
        self,
    ) -> None:
        """A high-weight observation pulls the posterior close to the
        observation value."""
        current = _state(value=165.0, prior_weight=0.1)
        observation = _observation(value=170.0, weight=10.0)

        result = bayesian_update(current, observation)

        # With prior_weight=0.1 and obs_weight=10, the posterior is
        # dominated by the observation (170).
        assert result["value"] > 169.0
        assert result["value"] < 170.0

    def test_posterior_mean_exact_when_weights_equal(self) -> None:
        """When current and observation weights are equal, the posterior
        is the simple arithmetic mean of the two values."""
        # Same-day observation → no decay → posterior is the simple
        # arithmetic mean of the two values. The default
        # ``_state``/``_observation`` fixtures have a 45-day gap
        # which would decayed_weight to 0.34, so the dates must be
        # pinned here for the assertion to hold.
        current = _state(
            value=160.0,
            prior_weight=1.0,
            last_observation_date="2026-06-15",
        )
        observation = _observation(value=180.0, weight=1.0)

        result = bayesian_update(current, observation)

        assert result["value"] == pytest.approx(170.0)

    def test_new_total_weight_is_decayed_plus_observation(self) -> None:
        """``new_total_weight = decayed_weight + observation.weight`` —
        weight conservation across the update."""
        # Same-day observation → decayed_weight = 2.0 * exp(0) = 2.0
        # new_total_weight = 2.0 + 3.0 = 5.0
        current = _state(
            prior_weight=2.0,
            last_observation_date="2026-06-15",
        )
        observation = _observation(weight=3.0)

        result = bayesian_update(current, observation)

        assert result["prior_weight"] == pytest.approx(5.0)

    def test_posterior_mean_returns_fresh_dict(self) -> None:
        """The returned dict is a brand-new object — the input
        ``current`` dict is not mutated."""
        current = _state(value=165.0, prior_weight=0.5)
        observation = _observation(value=170.0, weight=1.0)

        result = bayesian_update(current, observation)

        assert result is not current
        assert current["value"] == 165.0  # unchanged
        assert current["prior_weight"] == 0.5  # unchanged


# ---------------------------------------------------------------------------
# bayesian_update — uncertainty floor.
# ---------------------------------------------------------------------------


class TestBayesianUpdateUncertaintyFloor:
    """``bayesian_update`` floors posterior uncertainty at 0.5
    (UNCERTAINTY_FLOOR) so uncertainty never collapses to zero."""

    def test_uncertainty_floor_applied_when_scaled_below_floor(self) -> None:
        """Massive evidence shrinks uncertainty toward 0, but the
        0.5 floor prevents it from collapsing."""
        current = _state(uncertainty=1.0, prior_weight=0.001)
        observation = _observation(weight=1000.0)

        result = bayesian_update(current, observation)

        # decayed_weight ≈ 0.001, new_total_weight ≈ 1000.001
        # scaled_uncertainty = 1.0 * sqrt(0.001 / 1000.001) ≈ 0.001
        # posterior_uncertainty = max(0.001, 0.5) = 0.5
        assert result["uncertainty"] == pytest.approx(UNCERTAINTY_FLOOR)

    def test_uncertainty_above_floor_when_evidence_moderate(self) -> None:
        """With moderate evidence, the scaled uncertainty is above
        the floor and is returned as-is."""
        # Same-day observation → decayed_weight = 1.0 → new_total
        # = 2.0 → scaled = 2.0 * sqrt(1/2) = sqrt(2). The default
        # ``_state``/``_observation`` fixtures have a 45-day gap
        # which would shrink decayed_weight to 0.34 and lift the
        # uncertainty further toward the floor, so the dates must
        # be pinned here for the assertion to hold.
        current = _state(
            uncertainty=2.0,
            prior_weight=1.0,
            last_observation_date="2026-06-15",
        )
        observation = _observation(weight=1.0)

        result = bayesian_update(current, observation)

        # decayed_weight = 1.0, new_total_weight = 2.0
        # scaled_uncertainty = 2.0 * sqrt(1.0 / 2.0) = 2.0 * 0.707 ≈ 1.414
        # posterior_uncertainty = max(1.414, 0.5) = 1.414
        assert result["uncertainty"] == pytest.approx(math.sqrt(2.0))
        assert result["uncertainty"] > UNCERTAINTY_FLOOR

    def test_uncertainty_never_below_floor(self) -> None:
        """Property test: across a range of inputs, the returned
        uncertainty is always >= 0.5."""
        for prior_weight in [0.001, 0.1, 1.0, 10.0, 100.0]:
            for obs_weight in [0.001, 0.1, 1.0, 10.0, 100.0]:
                current = _state(uncertainty=1.0, prior_weight=prior_weight)
                observation = _observation(weight=obs_weight)
                result = bayesian_update(current, observation)
                assert result["uncertainty"] >= UNCERTAINTY_FLOOR


# ---------------------------------------------------------------------------
# bayesian_update — dominant source.
# ---------------------------------------------------------------------------


class TestBayesianUpdateDominantSource:
    """``bayesian_update`` sets ``dominant_source`` to the observation's
    source iff ``observation.weight > decayed_weight``, else keeps the
    current dominant source."""

    def test_observation_dominates_when_weight_exceeds_decayed_prior(
        self,
    ) -> None:
        """When observation.weight > decayed_weight, the observation's
        source becomes the new dominant source."""
        current = _state(
            prior_weight=0.5,
            dominant_source="training_hr_deflection",
        )
        observation = _observation(
            weight=2.0,
            source=MeasurementSource.TRAINING_RR_INFLECTION,
        )

        result = bayesian_update(current, observation)

        # decayed_weight = 0.5 (same-day), obs.weight = 2.0 → obs wins
        assert result["dominant_source"] == "training_rr_inflection"

    def test_prior_dominates_when_decayed_weight_exceeds_observation(
        self,
    ) -> None:
        """When decayed_weight > observation.weight, the current
        dominant source is preserved."""
        current = _state(
            prior_weight=10.0,
            dominant_source="training_hr_deflection",
        )
        observation = _observation(
            weight=0.5,
            source=MeasurementSource.TRAINING_RR_INFLECTION,
        )

        result = bayesian_update(current, observation)

        # decayed_weight = 10.0, obs.weight = 0.5 → prior wins
        assert result["dominant_source"] == "training_hr_deflection"

    def test_prior_dominates_when_weights_equal(self) -> None:
        """When observation.weight == decayed_weight, the comparison
        is strict ``>`` so the prior wins (the observation does NOT
        dominate on a tie)."""
        # Same-day observation → decayed_weight = 1.0. The default
        # ``_state``/``_observation`` fixtures have a 45-day gap
        # which would shrink decayed_weight to 0.34, so the
        # observation would dominate and the prior would lose.
        # The dates must be pinned here for the "tie" semantics
        # to hold.
        current = _state(
            prior_weight=1.0,
            dominant_source="training_hr_deflection",
            last_observation_date="2026-06-15",
        )
        observation = _observation(
            weight=1.0,
            source=MeasurementSource.TRAINING_RR_INFLECTION,
        )

        result = bayesian_update(current, observation)

        # decayed_weight = 1.0, obs.weight = 1.0 → 1.0 > 1.0 is False
        assert result["dominant_source"] == "training_hr_deflection"

    def test_dominant_source_stored_as_value_string(self) -> None:
        """The dominant_source is stored as the MeasurementSource.value
        string, not the enum member."""
        current = _state(prior_weight=0.5)
        observation = _observation(
            weight=2.0,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
        )

        result = bayesian_update(current, observation)

        assert result["dominant_source"] == "training_power_hr_ratio"
        assert isinstance(result["dominant_source"], str)


# ---------------------------------------------------------------------------
# bayesian_update — prior decay.
# ---------------------------------------------------------------------------


class TestBayesianUpdatePriorDecay:
    """``bayesian_update`` applies ``decay_factor = exp(-days_since_last / 42)``
    to the current prior weight before blending with the observation."""

    def test_same_day_observation_keeps_prior_weight_intact(self) -> None:
        """When the observation date equals the current
        last_observation_date, days_since_last = 0 and the prior
        weight is not decayed."""
        current = _state(
            prior_weight=2.0,
            last_observation_date="2026-06-15",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 15),
        )

        result = bayesian_update(current, observation)

        # decayed_weight = 2.0 * exp(0) = 2.0
        # new_total_weight = 2.0 + 1.0 = 3.0
        assert result["prior_weight"] == pytest.approx(3.0)

    def test_42_day_gap_decays_prior_to_37_percent(self) -> None:
        """After 42 days, the prior weight decays to ~37% (1/e)."""
        current = _state(
            prior_weight=10.0,
            last_observation_date="2026-05-04",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 15),  # 42 days later
        )

        result = bayesian_update(current, observation)

        # decayed_weight = 10.0 * exp(-42/42) = 10.0 * exp(-1) ≈ 3.679
        # new_total_weight = 3.679 + 1.0 ≈ 4.679
        expected_decayed = 10.0 * math.exp(-1.0)
        expected_total = expected_decayed + 1.0
        assert result["prior_weight"] == pytest.approx(expected_total)

    def test_long_gap_decays_prior_toward_zero(self) -> None:
        """After ~3 years (1095 days), the prior weight is essentially
        zero — the observation dominates the posterior."""
        current = _state(
            prior_weight=10.0,
            last_observation_date="2023-06-15",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 15),  # ~3 years later
        )

        result = bayesian_update(current, observation)

        # decayed_weight = 10.0 * exp(-1095/42) ≈ 0 (essentially)
        # new_total_weight ≈ 1.0
        assert result["prior_weight"] == pytest.approx(1.0, abs=1e-6)

    def test_future_observation_date_clamped_to_zero_days(self) -> None:
        """A future observation date (negative days_since_last) is
        clamped to 0 — the prior weight is not decayed."""
        current = _state(
            prior_weight=2.0,
            last_observation_date="2026-06-20",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 15),  # 5 days BEFORE current
        )

        result = bayesian_update(current, observation)

        # days_since_last = max(0, -5) = 0
        # decayed_weight = 2.0 * exp(0) = 2.0
        # new_total_weight = 2.0 + 1.0 = 3.0
        assert result["prior_weight"] == pytest.approx(3.0)


# ---------------------------------------------------------------------------
# bayesian_update — date parsing.
# ---------------------------------------------------------------------------


class TestBayesianUpdateDateParsing:
    """``bayesian_update`` accepts both ISO-8601 datetime strings and
    bare ``YYYY-MM-DD`` date strings for ``current.last_observation_date``,
    and accepts both ``datetime`` and ``date`` objects for
    ``observation.date``."""

    def test_iso_datetime_string_in_current_date(self) -> None:
        """A full ISO-8601 datetime string in ``last_observation_date``
        is parsed to its date component."""
        current = _state(
            prior_weight=1.0,
            last_observation_date="2026-05-12T08:30:00+00:00",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 15),
        )

        result = bayesian_update(current, observation)

        # 34 days between 2026-05-12 and 2026-06-15
        # decayed_weight = 1.0 * exp(-34/42)
        expected_decayed = math.exp(-34.0 / 42.0)
        expected_total = expected_decayed + 1.0
        assert result["prior_weight"] == pytest.approx(expected_total)

    def test_bare_date_string_in_current_date(self) -> None:
        """A bare ``YYYY-MM-DD`` string in ``last_observation_date``
        is parsed to a date."""
        current = _state(
            prior_weight=1.0,
            last_observation_date="2026-05-12",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 15),
        )

        result = bayesian_update(current, observation)

        # Same 34-day gap as the ISO datetime test
        expected_decayed = math.exp(-34.0 / 42.0)
        expected_total = expected_decayed + 1.0
        assert result["prior_weight"] == pytest.approx(expected_total)

    def test_datetime_observation_truncated_to_date(self) -> None:
        """A ``datetime`` observation is truncated to its date component
        for the days_since_last computation."""
        current = _state(
            prior_weight=1.0,
            last_observation_date="2026-06-15",
        )
        observation = _observation(
            weight=1.0,
            obs_date=datetime(2026, 6, 20, 14, 30, tzinfo=timezone.utc),
        )

        result = bayesian_update(current, observation)

        # 5 days between 2026-06-15 and 2026-06-20
        expected_decayed = math.exp(-5.0 / 42.0)
        expected_total = expected_decayed + 1.0
        assert result["prior_weight"] == pytest.approx(expected_total)

    def test_date_observation_used_directly(self) -> None:
        """A ``date`` observation is used directly without truncation."""
        current = _state(
            prior_weight=1.0,
            last_observation_date="2026-06-15",
        )
        observation = _observation(
            weight=1.0,
            obs_date=date(2026, 6, 20),
        )

        result = bayesian_update(current, observation)

        # Same 5-day gap as the datetime test
        expected_decayed = math.exp(-5.0 / 42.0)
        expected_total = expected_decayed + 1.0
        assert result["prior_weight"] == pytest.approx(expected_total)

    def test_unsupported_current_date_type_raises_type_error(self) -> None:
        """A non-date / non-datetime / non-string ``last_observation_date``
        raises ``TypeError``."""
        current = _state(
            prior_weight=1.0,
            last_observation_date=12345,  # type: ignore[arg-type]
        )
        observation = _observation(weight=1.0)

        with pytest.raises(TypeError, match="unsupported last_observation_date"):
            bayesian_update(current, observation)

    def test_unsupported_observation_date_type_raises_type_error(
        self,
    ) -> None:
        """A non-date / non-datetime ``observation.date`` raises
        ``TypeError``."""
        current = _state(prior_weight=1.0)
        observation = _observation(weight=1.0, obs_date="not-a-date") # type: ignore[arg-type]

        with pytest.raises(TypeError, match="unsupported observation date"):
            bayesian_update(current, observation)

    def test_returned_last_observation_date_is_iso_string(self) -> None:
        """The returned ``last_observation_date`` is always the bare
        ``YYYY-MM-DD`` ISO form, regardless of the input format."""
        current = _state(
            prior_weight=1.0,
            last_observation_date="2026-05-12T08:30:00+00:00",
        )
        observation = _observation(
            weight=1.0,
            obs_date=datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc),
        )

        result = bayesian_update(current, observation)

        assert result["last_observation_date"] == "2026-06-15"


# ---------------------------------------------------------------------------
# init_null_parameter_state — first-observation bootstrap.
# ---------------------------------------------------------------------------


class TestInitNullParameterState:
    """``init_null_parameter_state`` bootstraps a brand-new
    ``PhysiologyParameterState`` from the first qualifying observation
    against a previously-null parameter column."""

    def test_bootstrap_uses_observation_value(self) -> None:
        """The bootstrapped ``value`` is the observation's value."""
        observation = _observation(value=260.0, weight=1.5)

        result = init_null_parameter_state(observation)

        assert result["value"] == 260.0

    def test_bootstrap_uses_initial_uncertainty(self) -> None:
        """The bootstrapped ``uncertainty`` is the population default
        (INITIAL_UNCERTAINTY = 1.0)."""
        observation = _observation(value=260.0, weight=1.5)

        result = init_null_parameter_state(observation)

        assert result["uncertainty"] == INITIAL_UNCERTAINTY

    def test_bootstrap_uses_observation_weight(self) -> None:
        """The bootstrapped ``prior_weight`` is the observation's weight."""
        observation = _observation(value=260.0, weight=1.5)

        result = init_null_parameter_state(observation)

        assert result["prior_weight"] == 1.5

    def test_bootstrap_uses_observation_source(self) -> None:
        """The bootstrapped ``dominant_source`` is the observation's
        source, stored as the ``.value`` string."""
        observation = _observation(
            value=260.0,
            weight=1.5,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
        )

        result = init_null_parameter_state(observation)

        assert result["dominant_source"] == "training_power_hr_ratio"

    def test_bootstrap_uses_observation_date(self) -> None:
        """The bootstrapped ``last_observation_date`` is the observation's
        date, stored as an ISO string."""
        observation = _observation(
            value=260.0,
            weight=1.5,
            obs_date=date(2026, 6, 15),
        )

        result = init_null_parameter_state(observation)

        assert result["last_observation_date"] == "2026-06-15"

    def test_bootstrap_shape_matches_bayesian_update_return(self) -> None:
        """The bootstrapped dict has the same five keys as the
        ``bayesian_update`` return value."""
        observation = _observation(value=260.0, weight=1.5)

        result = init_null_parameter_state(observation)

        assert set(result.keys()) == {
            "value",
            "uncertainty",
            "prior_weight",
            "dominant_source",
            "last_observation_date",
        }


# ---------------------------------------------------------------------------
# PhysiologyUpdateResult — dataclass shape.
# ---------------------------------------------------------------------------


class TestPhysiologyUpdateResultDataclass:
    """``PhysiologyUpdateResult`` carries the updated physiology row,
    shifted parameters, per-metric confidence, confidence transitions,
    and measurements-written count."""

    def test_is_a_dataclass(self) -> None:
        """``PhysiologyUpdateResult`` is a dataclass."""
        assert is_dataclass(PhysiologyUpdateResult)

    def test_required_field_physiology(self) -> None:
        """``physiology`` is a required field (no default)."""
        field_names = {f.name for f in fields(PhysiologyUpdateResult)}
        assert "physiology" in field_names

    def test_default_shifted_parameters_is_empty_list(self) -> None:
        """``shifted_parameters`` defaults to an empty list."""
        # Build a minimal physiology row to satisfy the required field.
        physiology = AthletePhysiology(
            athlete_id=uuid.uuid4(),
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        result = PhysiologyUpdateResult(physiology=physiology)
        assert result.shifted_parameters == []
        assert isinstance(result.shifted_parameters, list)

    def test_default_metric_confidence_is_empty_dict(self) -> None:
        """``metric_confidence`` defaults to an empty dict."""
        physiology = AthletePhysiology(
            athlete_id=uuid.uuid4(),
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        result = PhysiologyUpdateResult(physiology=physiology)
        assert result.metric_confidence == {}
        assert isinstance(result.metric_confidence, dict)

    def test_default_confidence_transitions_is_empty_dict(self) -> None:
        """``confidence_transitions`` defaults to an empty dict."""
        physiology = AthletePhysiology(
            athlete_id=uuid.uuid4(),
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        result = PhysiologyUpdateResult(physiology=physiology)
        assert result.confidence_transitions == {}
        assert isinstance(result.confidence_transitions, dict)

    def test_default_measurements_written_is_zero(self) -> None:
        """``measurements_written`` defaults to 0."""
        physiology = AthletePhysiology(
            athlete_id=uuid.uuid4(),
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        result = PhysiologyUpdateResult(physiology=physiology)
        assert result.measurements_written == 0

    def test_default_lists_are_independent_per_instance(self) -> None:
        """Two ``PhysiologyUpdateResult`` instances do not share the
        same default list/dict — the ``default_factory`` pattern
        prevents the classic mutable-default-argument bug."""
        physiology = AthletePhysiology(
            athlete_id=uuid.uuid4(),
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        result_a = PhysiologyUpdateResult(physiology=physiology)
        result_b = PhysiologyUpdateResult(physiology=physiology)

        result_a.shifted_parameters.append(PhysiologyParameter.LT1_HR)
        result_a.metric_confidence["lt1_hr"] = "medium"

        assert result_b.shifted_parameters == []
        assert result_b.metric_confidence == {}

    def test_all_fields_can_be_set_explicitly(self) -> None:
        """Every field can be set explicitly at construction time."""
        physiology = AthletePhysiology(
            athlete_id=uuid.uuid4(),
            lt1={"hr": None, "power": None, "pace": None},
            lt2={"hr": None, "power": None, "pace": None},
        )
        result = PhysiologyUpdateResult(
            physiology=physiology,
            shifted_parameters=[PhysiologyParameter.LT2_HR],
            metric_confidence={"lt2_hr": "medium"},
            confidence_transitions={"lt2_hr": ("low", "medium")},
            measurements_written=3,
        )

        assert result.shifted_parameters == [PhysiologyParameter.LT2_HR]
        assert result.metric_confidence == {"lt2_hr": "medium"}
        assert result.confidence_transitions == {
            "lt2_hr": ("low", "medium")
        }
        assert result.measurements_written == 3
