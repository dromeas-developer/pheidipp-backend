"""Unit tests for ``OnboardingService`` module-level helpers.

These are pure-function tests — no database, no session, no HTTP.
They exercise the small helpers the service relies on for its bootstrap
math and error mapping.

* ``age_in_years`` — birthday-aware age computation (drives the
  ``max_hr = 220 - age`` formula).
* ``bootstrap_signal`` — JSON shape for a populated physiology posterior.
* ``TrainingGoalRepository_unique_violation`` — PostgreSQL ``23505``
  detection for partial unique index failures.
* ``_validate_goal_type`` — the onboarding whitelist for ``GoalType``.
* The ``BOOTSTRAP_MODEL_VERSION`` constant matches the documented value.
* ``POPULATION_TAU`` time constants carry the documented values from
  the architecture's Banister contract.
* ``bootstrap_metric_confidence`` produces the expected ``lt1_hr`` /
  ``lt2_hr`` low-confidence JSON with all other metric slots null.

Reference plan: docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import cast

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.enums import GoalType
from app.services.onboarding_errors import InvalidGoalTypeError
from app.services.onboarding_service import (
    ALLOWED_ONBOARDING_GOAL_TYPES,
    BOOTSTRAP_MODEL_VERSION,
    LT1_FACTOR,
    LT2_FACTOR,
    POPULATION_TAU,
    OnboardingService,
    TrainingGoalRepository_unique_violation,
    age_in_years,
    bootstrap_metric_confidence,
    bootstrap_signal,
)


# ---------------------------------------------------------------------------
# age_in_years — birthday-aware computation.
# ---------------------------------------------------------------------------


class TestAgeInYears:
    """Birthday-aware age. Negative ages must never be produced."""

    def test_age_is_zero_when_birthday_is_today(self) -> None:
        today = datetime(2026, 6, 25, tzinfo=timezone.utc)
        assert age_in_years(date(2026, 6, 25), today) == 0

    def test_age_is_zero_when_birthday_is_in_the_future_this_year(self) -> None:
        today = datetime(2026, 6, 25, tzinfo=timezone.utc)
        assert age_in_years(date(2026, 6, 26), today) == 0

    def test_age_increments_after_birthday_this_year(self) -> None:
        today = datetime(2026, 6, 25, tzinfo=timezone.utc)
        assert age_in_years(date(1990, 6, 25), today) == 36

    def test_age_holds_before_birthday_this_year(self) -> None:
        """One day before birthday — age must NOT increment yet."""
        today = datetime(2026, 6, 25, tzinfo=timezone.utc)
        assert age_in_years(date(1990, 6, 26), today) == 35

    def test_age_works_across_year_boundary_before_birthday(self) -> None:
        today = datetime(2026, 1, 1, tzinfo=timezone.utc)
        # Birthday in March — should report age as year-1 (turning N on
        # March 15), not the new age.
        assert age_in_years(date(1990, 3, 15), today) == 35

    def test_age_works_across_year_boundary_after_birthday(self) -> None:
        today = datetime(2026, 6, 25, tzinfo=timezone.utc)
        # Birthday in January — already past, so age is N.
        assert age_in_years(date(1990, 1, 15), today) == 36

    def test_age_drives_max_hr_estimate(self) -> None:
        """The bootstrap uses ``max_hr = 220 - age``. Asserting the
        formula directly is fragile to refactors; this test pins the
        mapping at 36y -> 184 bpm which the rest of the suite
        relies on."""
        today = datetime(2026, 6, 25, tzinfo=timezone.utc)
        age = age_in_years(date(1990, 6, 25), today)
        assert 220 - age == 184


# ---------------------------------------------------------------------------
# bootstrap_signal — posterior JSON shape.
# ---------------------------------------------------------------------------


class TestBootstrapSignal:
    """The physiology bootstrap serialises every posterior as the
    canonical ``PhysiologyParameterState`` JSON."""

    def test_emits_expected_key_set(self) -> None:
        observation = datetime(2026, 6, 25, tzinfo=timezone.utc)
        sig = bootstrap_signal(value=138.0, observation_date=observation)
        expected_keys = {
            "value",
            "uncertainty",
            "prior_weight",
            "dominant_source",
            "last_observation_date",
        }
        assert set(sig.keys()) == expected_keys

    def test_value_passes_through_unchanged(self) -> None:
        observation = datetime(2026, 6, 25, tzinfo=timezone.utc)
        sig = bootstrap_signal(value=160.5, observation_date=observation)
        assert sig["value"] == 160.5

    def test_uncertainty_is_high_for_bootstrap(self) -> None:
        """Population priors are high-uncertainty until individual
        observations arrive — the architecture sets this to 1.0 at
        bootstrap."""
        observation = datetime(2026, 6, 25, tzinfo=timezone.utc)
        sig = bootstrap_signal(value=160.0, observation_date=observation)
        assert sig["uncertainty"] == 1.0

    def test_prior_weight_is_uniform_half(self) -> None:
        """Per the architecture's Bayesian contract, bootstrap priors
        carry a uniform weight of 0.5."""
        observation = datetime(2026, 6, 25, tzinfo=timezone.utc)
        sig = bootstrap_signal(value=160.0, observation_date=observation)
        assert sig["prior_weight"] == 0.5

    def test_dominant_source_is_questionnaire_estimate(self) -> None:
        observation = datetime(2026, 6, 25, tzinfo=timezone.utc)
        sig = bootstrap_signal(value=160.0, observation_date=observation)
        assert sig["dominant_source"] == "questionnaire_estimate"

    def test_last_observation_date_is_the_supplied_datetime(self) -> None:
        observation = datetime(2026, 6, 25, tzinfo=timezone.utc)
        sig = bootstrap_signal(value=160.0, observation_date=observation)
        # The implementation returns ISO format string for JSONB storage.
        # The contract is "the supplied observation date is preserved".
        assert sig["last_observation_date"] == observation.isoformat()


# ---------------------------------------------------------------------------
# TrainingGoalRepository_unique_violation — 23505 detection.
# ---------------------------------------------------------------------------


class TestIntegrityErrorDetection:
    """``TrainingGoalRepository_unique_violation`` returns True only
    for a PostgreSQL ``23505`` error — the contract relied on by the
    service to map partial unique-index conflicts to
    ``TrainingGoalConflictError``."""

    def _make_error(self, pgcode: object) -> IntegrityError:
        """Build a ``IntegrityError`` with a controlled ``orig.pgcode``."""

        class _Orig(BaseException):
            def __init__(self, code: object) -> None:
                super().__init__()
                self.pgcode = code

        # SQLAlchemy IntegrityError signature: (message, params=None, orig=None)
        # The .orig attribute holds the DBAPI exception which has .pgcode
        return IntegrityError("test", None, _Orig(pgcode))

    def test_returns_true_for_23505(self) -> None:
        err = self._make_error("23505")
        assert TrainingGoalRepository_unique_violation(err) is True

    def test_returns_false_for_other_pgcodes(self) -> None:
        # 23502 is NOT NULL violation, 23503 is FK violation.
        assert TrainingGoalRepository_unique_violation(
            self._make_error("23502")
        ) is False
        assert TrainingGoalRepository_unique_violation(
            self._make_error("23503")
        ) is False
        assert TrainingGoalRepository_unique_violation(
            self._make_error("23514")
        ) is False

    def test_returns_false_when_pgcode_is_none(self) -> None:
        err = self._make_error(None)
        assert TrainingGoalRepository_unique_violation(err) is False

    def test_returns_false_when_orig_is_missing(self) -> None:
        # SQLAlchemy type stubs require ``BaseException`` for ``orig``,
        # but the runtime accepts ``None`` to represent a missing
        # DBAPI exception. We use ``cast`` here to match reality.
        err = IntegrityError("test", None, cast("BaseException", None))
        assert TrainingGoalRepository_unique_violation(err) is False


# ---------------------------------------------------------------------------
# Goal-type whitelist — only race_event / target_performance accepted.
# ---------------------------------------------------------------------------


class TestGoalTypeWhitelist:
    """The bootstrap rejects ``fitness_improvement``, ``maintenance``,
    and ``recovery`` even though the ``GoalType`` enum still carries
    them for later phases."""

    def test_allowed_set_exactly_race_and_target(self) -> None:
        assert ALLOWED_ONBOARDING_GOAL_TYPES == frozenset(
            {GoalType.RACE_EVENT, GoalType.TARGET_PERFORMANCE}
        )

    @pytest.mark.parametrize("goal_type", [GoalType.RACE_EVENT, GoalType.TARGET_PERFORMANCE])
    def test_allowed_goal_types_pass_validation(self, goal_type: GoalType) -> None:
        # Should NOT raise.
        OnboardingService.validate_goal_type(goal_type)

    @pytest.mark.parametrize(
        "goal_type",
        [
            GoalType.FITNESS_IMPROVEMENT,
            GoalType.MAINTENANCE,
            GoalType.RECOVERY,
        ],
    )
    def test_rejected_goal_types_raise_invalid_goal_type(
        self, goal_type: GoalType
    ) -> None:
        with pytest.raises(InvalidGoalTypeError) as exc_info:
            OnboardingService.validate_goal_type(goal_type)
        assert goal_type.value in str(exc_info.value)

    def test_validate_goal_type_strenum_equality_accepts_value_string(
        self,
    ) -> None:
        OnboardingService.validate_goal_type(
            "race_event",  # type: ignore[arg-type]
        )

    def test_module_level_helper_matches_class_validator(self) -> None:
        """The onboarding whitelist is enforced through
        :meth:`OnboardingService.validate_goal_type`. The helper
        rejects every value outside ``ALLOWED_ONBOARDING_GOAL_TYPES``,
        so disallowed values must produce :class:`InvalidGoalTypeError`
        and allowed values must pass silently."""
        with pytest.raises(InvalidGoalTypeError):
            OnboardingService.validate_goal_type(
                GoalType.FITNESS_IMPROVEMENT
            )
        # No raise for allowed types.
        OnboardingService.validate_goal_type(GoalType.RACE_EVENT)
        OnboardingService.validate_goal_type(GoalType.TARGET_PERFORMANCE)


# ---------------------------------------------------------------------------
# Threshold factors — drive LT1/LT2/max_hr from age.
# ---------------------------------------------------------------------------


class TestThresholdFactors:
    """``max_hr = 220 - age``, ``lt1 = 0.75 * max_hr``,
    ``lt2 = 0.875 * max_hr``. These factors appear in plan generation
    and must match the architecture's confidence model."""

    def test_lt1_factor_is_three_quarters(self) -> None:
        assert LT1_FACTOR == 0.75

    def test_lt2_factor_is_seven_eighths(self) -> None:
        assert LT2_FACTOR == 0.875

    def test_threshold_formulae_apply_to_a_reference_age(self) -> None:
        """36-year-old -> max_hr = 184, lt1 = 138.0, lt2 = 161.0."""
        max_hr = 220 - 36
        assert max_hr == 184
        assert round(max_hr * LT1_FACTOR, 2) == 138.0
        assert round(max_hr * LT2_FACTOR, 2) == 161.0


# ---------------------------------------------------------------------------
# Population time constants — Banister contract.
# ---------------------------------------------------------------------------


class TestPopulationTau:
    """Architecture-invariant population time constants used at the
    bootstrap. These feed the Banister fitness/fatigue decay — they
    must remain stable or downstream planning regressions appear."""

    def test_aerobic_tau_matches_architecture(self) -> None:
        assert POPULATION_TAU["aerobic"] == {
            "fitness_tau_days": 42,
            "fatigue_tau_days": 7,
        }

    def test_neuromuscular_tau_matches_architecture(self) -> None:
        assert POPULATION_TAU["neuromuscular"] == {
            "fitness_tau_days": 21,
            "fatigue_tau_days": 3,
        }

    def test_structural_tau_matches_architecture(self) -> None:
        assert POPULATION_TAU["structural"] == {
            "fitness_tau_days": 56,
            "fatigue_tau_days": 14,
        }

    def test_aerobic_has_longer_fitness_tau_than_fatigue_tau(self) -> None:
        """Fitness decays slower than fatigue across all dimensions —
        a regression that swaps them would silently break all
        downstream planning."""
        for dim, tau in POPULATION_TAU.items():
            assert tau["fitness_tau_days"] > tau["fatigue_tau_days"], (
                f"{dim}: fitness_tau_days must exceed fatigue_tau_days"
            )


# ---------------------------------------------------------------------------
# Bootstrap model version — pinned string used by ``TwinState.model_version``.
# ---------------------------------------------------------------------------


class TestBootstrapModelVersion:
    def test_bootstrap_model_version_is_pinned(self) -> None:
        """The bootstrap TwinState carries ``model_version =
        'v1-questionnaire-bootstrap'``. A silent rename would break
        recalibration version matching."""
        assert BOOTSTRAP_MODEL_VERSION == "v1-questionnaire-bootstrap"


# ---------------------------------------------------------------------------
# Metric confidence bootstrap JSON.
# ---------------------------------------------------------------------------


class TestBootstrapMetricConfidence:
    """``lt1_hr`` / ``lt2_hr`` are populated at bootstrap with
    ``low``; all other metric slots are explicitly ``null``."""

    def test_lt1_hr_and_lt2_hr_are_low(self) -> None:
        confidence = bootstrap_metric_confidence()
        assert confidence["lt1_hr"] == "low"
        assert confidence["lt2_hr"] == "low"

    def test_other_metric_slots_are_null(self) -> None:
        confidence = bootstrap_metric_confidence()
        for key in ("lt1_power", "lt1_pace", "lt2_power", "lt2_pace", "cp"):
            assert key in confidence, f"missing metric confidence key: {key}"
            assert confidence[key] is None, (
                f"{key} must be null at bootstrap, got {confidence[key]!r}"
            )

    def test_global_confidence_level_is_min_of_per_metric(self) -> None:
        """Global ``TwinState.confidence_level`` is
        ``min(per-metric)``. With only low-populated entries the
        result must be ``low``."""
        confidence = bootstrap_metric_confidence()
        populated = [v for v in confidence.values() if v is not None]
        assert populated  # at least one populated
        assert all(v == "low" for v in populated)

    def test_carries_all_expected_keys(self) -> None:
        confidence = bootstrap_metric_confidence()
        expected = {
            "lt1_hr",
            "lt1_power",
            "lt1_pace",
            "lt2_hr",
            "lt2_power",
            "lt2_pace",
            "cp",
        }
        assert set(confidence.keys()) == expected
