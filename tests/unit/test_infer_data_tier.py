"""Unit tests for the pure ``infer_data_tier`` function.

The function maps an athlete's ``HrSource`` x ``PowerSource`` combination
to one of the six hardware ``DataTier`` values. Every downstream
component — load computation, threshold detection, calibration
eligibility, plan generation — reasons about tiers via this rule, so a
silent change here is a silent regression across the entire twin.

The algorithm is canonical:

* Running power meter + chest strap (RR) -> Tier 1
* Running power meter + non-RR HR   -> Tier 2
* Chest strap (RR) alone              -> Tier 3
* Chest strap (no RR) OR wrist optical -> Tier 4
* ``HrSource.NONE``                  -> Tier 5
* Fallback                           -> Tier 6 (manual-entry path)

Reference: docs/architecture/00-foundations/data-tiers.md
"""

from __future__ import annotations

import pytest

from app.models.athlete_preferences import infer_data_tier
from app.models.enums import DataTier, HrSource, PowerSource


class TestInferenceAlgorithm:
    @pytest.mark.parametrize(
        "hr_source, power_source, expected_tier",
        [
            # Tier 1 — best: power + RR
            (HrSource.CHEST_STRAP_RR, PowerSource.RUNNING_POWER_METER, DataTier.TIER_1),
            # Tier 2 — power + non-RR HR (any non-RR HR source triggers Tier 2)
            (
                HrSource.CHEST_STRAP_NO_RR,
                PowerSource.RUNNING_POWER_METER,
                DataTier.TIER_2,
            ),
            (HrSource.WRIST_OPTICAL, PowerSource.RUNNING_POWER_METER, DataTier.TIER_2),
            (HrSource.NONE, PowerSource.RUNNING_POWER_METER, DataTier.TIER_2),
            # Tier 3 — RR alone (no power)
            (HrSource.CHEST_STRAP_RR, PowerSource.NONE, DataTier.TIER_3),
            # Tier 4 — non-RR HR alone
            (HrSource.CHEST_STRAP_NO_RR, PowerSource.NONE, DataTier.TIER_4),
            (HrSource.WRIST_OPTICAL, PowerSource.NONE, DataTier.TIER_4),
            # Tier 5 — no HR at all
            (HrSource.NONE, PowerSource.NONE, DataTier.TIER_5),
        ],
    )
    def test_inference_matches_canonical_table(
        self, hr_source: HrSource, power_source: PowerSource, expected_tier: DataTier
    ) -> None:
        assert infer_data_tier(hr_source, power_source) is expected_tier

    def test_inference_is_pure_no_side_effects(self) -> None:
        """Repeated calls with the same inputs return equal values."""
        a = infer_data_tier(HrSource.CHEST_STRAP_RR, PowerSource.RUNNING_POWER_METER)
        b = infer_data_tier(HrSource.CHEST_STRAP_RR, PowerSource.RUNNING_POWER_METER)
        assert a is b

    def test_inference_power_priority_over_hr_for_power_meter_path(self) -> None:
        """If a power meter is present, the function decides between
        Tier 1 and Tier 2 based on HR source only. This guards against
        accidental reordering where HR is checked before power."""
        # Wrist optical + power meter is Tier 2, not Tier 4.
        assert (
            infer_data_tier(HrSource.WRIST_OPTICAL, PowerSource.RUNNING_POWER_METER)
            is DataTier.TIER_2
        )
        # Chest strap (no RR) + power meter is Tier 2, not Tier 4.
        assert (
            infer_data_tier(HrSource.CHEST_STRAP_NO_RR, PowerSource.RUNNING_POWER_METER)
            is DataTier.TIER_2
        )


class TestInferenceCoverage:
    """Cover the entire (HrSource x PowerSource) cartesian product to
    guarantee the function is a total mapping (no unhandled branches,
    no silent fall-throughs to Tier 6 besides the documented ones)."""

    @pytest.mark.parametrize(
        "hr_source, power_source",
        [
            (hr, pw)
            for hr in HrSource
            for pw in PowerSource
        ],
    )
    def test_inference_returns_a_valid_tier(
        self, hr_source: HrSource, power_source: PowerSource
    ) -> None:
        result = infer_data_tier(hr_source, power_source)
        assert isinstance(result, DataTier)
        # Returned tier is in the closed 1..6 set.
        assert 1 <= int(result) <= 6

    def test_tier_6_fallback_path_documented(self) -> None:
        """The (HrSource.NONE, PowerSource.NONE) input maps to Tier 5;
        Tier 6 is reserved for the manual-entry fallback handled outside
        this function (Activity.source = ``manual_entry`` does not
        reach ``infer_data_tier``). This test pins the documented
        fallback behaviour for that exact input."""
        # Tier 6 is reachable only via the manual-entry path handled at
        # the Activity ingestion boundary; the pure function never
        # returns it for a real HR/Power source pair.
        assert (
            infer_data_tier(HrSource.NONE, PowerSource.NONE) is DataTier.TIER_5
        )


class TestRegressionGuards:
    """Guards against specific regression classes."""

    def test_implementation_matches_architecture_pseudocode(self) -> None:
        """The architecture spec gives the canonical algorithm in
        TypeScript pseudocode. This test mirrors it line-for-line so
        a refactor that accidentally diverges is caught instantly.

        See docs/architecture/00-foundations/data-tiers.md →
        'Tier Inference from AthletePreferences'.
        """
        # Mirror the canonical function exactly.
        def canonical(
            hr_source: HrSource, power_source: PowerSource
        ) -> DataTier:
            if power_source == PowerSource.RUNNING_POWER_METER:
                return (
                    DataTier.TIER_1
                    if hr_source == HrSource.CHEST_STRAP_RR
                    else DataTier.TIER_2
                )
            if hr_source == HrSource.CHEST_STRAP_RR:
                return DataTier.TIER_3
            if hr_source in {
                HrSource.CHEST_STRAP_NO_RR,
                HrSource.WRIST_OPTICAL,
            }:
                return DataTier.TIER_4
            if hr_source == HrSource.NONE:
                return DataTier.TIER_5
            return DataTier.TIER_6

        for hr in HrSource:
            for pw in PowerSource:
                assert infer_data_tier(hr, pw) == canonical(hr, pw)
