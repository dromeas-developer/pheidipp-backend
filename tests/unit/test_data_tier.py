from app.models.athlete_preferences import infer_data_tier
from app.models.enums import DataTier, HrSource, PowerSource


class TestInferDataTier:
    def test_tier1_chest_strap_rr_with_running_power(self):
        assert (
            infer_data_tier(HrSource.CHEST_STRAP_RR, PowerSource.RUNNING_POWER_METER)
            == DataTier.TIER_1
        )

    def test_tier2_running_power_with_non_rr_hr(self):
        assert (
            infer_data_tier(HrSource.WRIST_OPTICAL, PowerSource.RUNNING_POWER_METER)
            == DataTier.TIER_2
        )

    def test_tier2_running_power_with_no_rr_hr_variant(self):
        assert (
            infer_data_tier(HrSource.CHEST_STRAP_NO_RR, PowerSource.RUNNING_POWER_METER)
            == DataTier.TIER_2
        )

    def test_tier3_chest_strap_rr_no_power(self):
        assert (
            infer_data_tier(HrSource.CHEST_STRAP_RR, PowerSource.NONE)
            == DataTier.TIER_3
        )

    def test_tier4_chest_strap_no_rr_no_power(self):
        assert (
            infer_data_tier(HrSource.CHEST_STRAP_NO_RR, PowerSource.NONE)
            == DataTier.TIER_4
        )

    def test_tier4_wrist_optical_no_power(self):
        assert (
            infer_data_tier(HrSource.WRIST_OPTICAL, PowerSource.NONE) == DataTier.TIER_4
        )

    def test_tier5_no_hr_no_power(self):
        assert infer_data_tier(HrSource.NONE, PowerSource.NONE) == DataTier.TIER_5

    def test_tier6_unhandled_combination_falls_back(self):
        for hr in HrSource:
            for power in PowerSource:
                tier = infer_data_tier(hr, power)
                if (hr, power) in {
                    (HrSource.CHEST_STRAP_RR, PowerSource.RUNNING_POWER_METER),
                    (HrSource.CHEST_STRAP_NO_RR, PowerSource.RUNNING_POWER_METER),
                    (HrSource.WRIST_OPTICAL, PowerSource.RUNNING_POWER_METER),
                    (HrSource.CHEST_STRAP_RR, PowerSource.NONE),
                    (HrSource.CHEST_STRAP_NO_RR, PowerSource.NONE),
                    (HrSource.WRIST_OPTICAL, PowerSource.NONE),
                    (HrSource.NONE, PowerSource.NONE),
                    (HrSource.NONE, PowerSource.RUNNING_POWER_METER),
                }:
                    assert tier != DataTier.TIER_6
                else:
                    assert tier == DataTier.TIER_6
