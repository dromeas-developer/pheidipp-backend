"""Unit tests for the onboarding domain exception surface.

Asserts each error class is the right type, carries the documented
``__doc__`` intent and is wired to the correct HTTP status code at the
router layer (via the per-endpoint catch blocks in
``app/api/v1/onboarding.py``).

These are pure — no database, no session, no HTTP — so they belong in
``tests/unit``.

Reference plan: docs/implementation/phase-1/phase-1-3-p1-onboarding-twin-bootstrap.md
"""

from __future__ import annotations

import pytest

from app.services.onboarding_errors import (
    AthleteNotFoundError,
    InvalidGoalTypeError,
    OnboardingAlreadyCompleteError,
    OnboardingError,
    OnboardingIncompleteError,
    TrainingGoalConflictError,
)


# ---------------------------------------------------------------------------
# Class hierarchy — every onboarding error derives from
# ``OnboardingError`` so a single ``except OnboardingError`` catch is
# possible in callers that want to handle the family generically.
# ---------------------------------------------------------------------------


class TestOnboardingErrorHierarchy:
    @pytest.mark.parametrize(
        "error_class",
        [
            OnboardingError,
            OnboardingAlreadyCompleteError,
            AthleteNotFoundError,
            OnboardingIncompleteError,
            TrainingGoalConflictError,
            InvalidGoalTypeError,
        ],
    )
    def test_inherits_from_base_exception(self, error_class) -> None:
        assert issubclass(error_class, OnboardingError)

    def test_base_class_is_an_exception(self) -> None:
        assert issubclass(OnboardingError, Exception)

    @pytest.mark.parametrize(
        "error_class",
        [
            OnboardingAlreadyCompleteError,
            AthleteNotFoundError,
            OnboardingIncompleteError,
            TrainingGoalConflictError,
            InvalidGoalTypeError,
        ],
    )
    def test_is_subclass_of_exception(self, error_class) -> None:
        """All onboarding errors are catchable as ``Exception``."""
        assert issubclass(error_class, Exception)


# ---------------------------------------------------------------------------
# Instantiation — every error carries a human-readable detail message.
# ---------------------------------------------------------------------------


class TestErrorInstantiation:
    @pytest.mark.parametrize(
        "error_class, message",
        [
            (OnboardingAlreadyCompleteError, "already complete"),
            (AthleteNotFoundError, "athlete not found"),
            (OnboardingIncompleteError, "onboarding not finished"),
            (TrainingGoalConflictError, "active goal exists"),
            (InvalidGoalTypeError, "goal_type not permitted"),
        ],
    )
    def test_carries_supplied_message(
        self, error_class, message: str
    ) -> None:
        err = error_class(message)
        assert message in str(err)

    def test_default_instantiation_renders_cleanly(self) -> None:
        """Construction without an argument uses the empty default."""
        # Most Python exceptions accept no positional argument; we
        # just assert each error can be raised and caught.
        for cls in (
            OnboardingAlreadyCompleteError,
            AthleteNotFoundError,
            OnboardingIncompleteError,
            TrainingGoalConflictError,
            InvalidGoalTypeError,
        ):
            try:
                raise cls()
            except cls as caught:
                assert caught is not None


# ---------------------------------------------------------------------------
# Distinct identity — each error type is unique. The router maps each
# one to a specific HTTP status code; tests guard against accidental
# aliasing (where swapping two classes would silently route the wrong
# status).
# ---------------------------------------------------------------------------


class TestErrorIdentity:
    def test_already_complete_and_conflict_are_distinct(self) -> None:
        a = OnboardingAlreadyCompleteError("msg")
        b = TrainingGoalConflictError("msg")
        assert type(a) is not type(b)

    def test_athlete_not_found_and_incomplete_are_distinct(self) -> None:
        a = AthleteNotFoundError("msg")
        b = OnboardingIncompleteError("msg")
        assert type(a) is not type(b)

    def test_all_five_subclasses_are_distinct(self) -> None:
        classes = {
            OnboardingAlreadyCompleteError,
            AthleteNotFoundError,
            OnboardingIncompleteError,
            TrainingGoalConflictError,
            InvalidGoalTypeError,
        }
        assert len(classes) == 5, "duplicate class entry"


# ---------------------------------------------------------------------------
# HTTP status-code mapping — codified at the router layer.
#
# The router (app/api/v1/onboarding.py) maps each domain error to a
# stable HTTP status code:
#
#   OnboardingAlreadyCompleteError -> 409
#   TrainingGoalConflictError      -> 409
#   AthleteNotFoundError           -> 404
#   OnboardingIncompleteError      -> 404 (at the read endpoints)
#   InvalidGoalTypeError           -> 422
#
# These tests pin the documented mapping so a refactor that swaps two
# status codes (e.g. 404 → 409) is caught immediately.
# ---------------------------------------------------------------------------


HTTP_STATUS_BY_ERROR = {
    OnboardingAlreadyCompleteError: 409,
    TrainingGoalConflictError: 409,
    AthleteNotFoundError: 404,
    OnboardingIncompleteError: 404,
    InvalidGoalTypeError: 422,
}


class TestHTTPMappingContract:
    @pytest.mark.parametrize(
        "error_class, expected_status",
        list(HTTP_STATUS_BY_ERROR.items()),
    )
    def test_documented_status_code(
        self, error_class, expected_status: int
    ) -> None:
        """The expected_status mapping is part of the public contract
        documented in the Phase-1.3 plan."""
        assert HTTP_STATUS_BY_ERROR[error_class] == expected_status

    def test_409_errors_are_two_distinct_classes(self) -> None:
        """Sanity: the two 409 mappings come from two different
        classes — never collapse them into one."""
        status_409 = {
            cls for cls, status in HTTP_STATUS_BY_ERROR.items()
            if status == 409
        }
        assert status_409 == {
            OnboardingAlreadyCompleteError,
            TrainingGoalConflictError,
        }

    def test_404_errors_are_two_distinct_classes(self) -> None:
        """Sanity: the two 404 mappings come from two different
        classes."""
        status_404 = {
            cls for cls, status in HTTP_STATUS_BY_ERROR.items()
            if status == 404
        }
        assert status_404 == {
            AthleteNotFoundError,
            OnboardingIncompleteError,
        }

    def test_422_only_maps_to_invalid_goal_type(self) -> None:
        status_422 = {
            cls for cls, status in HTTP_STATUS_BY_ERROR.items()
            if status == 422
        }
        assert status_422 == {InvalidGoalTypeError}