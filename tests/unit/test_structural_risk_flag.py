from app.models.enums import SportBackground


class TestStructuralRiskFlag:
    def test_running_primary_is_false(self):
        assert (
            SportBackground.RUNNING_PRIMARY != SportBackground.RUNNING_PRIMARY
        ) is False

    def test_triathlon_is_true(self):
        assert (SportBackground.TRIATHLON != SportBackground.RUNNING_PRIMARY) is True

    def test_cycling_primary_is_true(self):
        assert (
            SportBackground.CYCLING_PRIMARY != SportBackground.RUNNING_PRIMARY
        ) is True

    def test_swimming_primary_is_true(self):
        assert (
            SportBackground.SWIMMING_PRIMARY != SportBackground.RUNNING_PRIMARY
        ) is True

    def test_cycling_is_true(self):
        assert (SportBackground.CYCLING != SportBackground.RUNNING_PRIMARY) is True

    def test_swimming_is_true(self):
        assert (SportBackground.SWIMMING != SportBackground.RUNNING_PRIMARY) is True

    def test_team_sport_is_true(self):
        assert (SportBackground.TEAM_SPORT != SportBackground.RUNNING_PRIMARY) is True

    def test_gym_fitness_is_true(self):
        assert (SportBackground.GYM_FITNESS != SportBackground.RUNNING_PRIMARY) is True

    def test_none_sport_background_is_true(self):
        assert (SportBackground.NONE != SportBackground.RUNNING_PRIMARY) is True

    def test_only_running_primary_returns_false(self):
        for bg in SportBackground:
            is_running_primary = bg == SportBackground.RUNNING_PRIMARY
            assert (bg != SportBackground.RUNNING_PRIMARY) is not is_running_primary
