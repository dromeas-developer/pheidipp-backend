import pytest

from app.models.enums import GoalType
from app.services.onboarding_errors import InvalidGoalTypeError
from app.services.onboarding_service import OnboardingService


class TestGoalTypeWhitelist:
    def test_race_event_accepted(self):
        OnboardingService.validate_goal_type(GoalType.RACE_EVENT)

    def test_target_performance_accepted(self):
        OnboardingService.validate_goal_type(GoalType.TARGET_PERFORMANCE)

    def test_fitness_improvement_rejected(self):
        with pytest.raises(InvalidGoalTypeError) as exc_info:
            OnboardingService.validate_goal_type(GoalType.FITNESS_IMPROVEMENT)
        assert f"goal_type '{GoalType.FITNESS_IMPROVEMENT.value}' is not permitted at onboarding" in str(
            exc_info.value
        )

    def test_maintenance_rejected(self):
        with pytest.raises(InvalidGoalTypeError) as exc_info:
            OnboardingService.validate_goal_type(GoalType.MAINTENANCE)
        assert f"goal_type '{GoalType.MAINTENANCE.value}' is not permitted at onboarding" in str(exc_info.value)

    def test_recovery_rejected(self):
        with pytest.raises(InvalidGoalTypeError) as exc_info:
            OnboardingService.validate_goal_type(GoalType.RECOVERY)
        assert f"goal_type '{GoalType.RECOVERY.value}' is not permitted at onboarding" in str(exc_info.value)
