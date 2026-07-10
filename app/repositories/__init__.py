"""Persistence repositories for Pheidipp domain entities."""

from app.repositories.athlete_auth_repository import AthleteAuthRepository
from app.repositories.athlete_fitness_repository import AthleteFitnessRepository
from app.repositories.athlete_physiology_repository import (
    AthletePhysiologyRepository,
)
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.checkpoint_repository import CheckpointRepository
from app.repositories.coaching_message_repository import (
    CoachingMessageRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.generated_workout_repository import (
    GeneratedWorkoutRepository,
)
from app.repositories.planned_session_repository import (
    PlannedSessionRepository,
)
from app.repositories.raw_sensor_stream_repository import (
    RawSensorStreamRepository,
)
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.workout_step_repository import WorkoutStepRepository
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from app.repositories.system_event_repository import SystemEventRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.weekly_plan_repository import (
    WeeklyPlanRepository,
    WeeklySessionRepository,
)

__all__ = [
    "AthleteAuthRepository",
    "AthleteFitnessRepository",
    "AthletePhysiologyRepository",
    "AthletePreferencesRepository",
    "AthleteProfileRepository",
    "AthleteRepository",
    "CheckpointRepository",
    "CoachingMessageRepository",
    "GenerationEventRepository",
    "GeneratedWorkoutRepository",
    "PlannedSessionRepository",
    "RawSensorStreamRepository",
    "RefreshTokenRepository",
    "SystemEventOutboxRepository",
    "SystemEventRepository",
    "TrainingGoalRepository",
    "TrainingPlanRepository",
    "TwinStateRepository",
    "WeeklyPlanRepository",
    "WeeklySessionRepository",
    "WorkoutStepRepository",
]
