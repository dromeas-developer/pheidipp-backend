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
from app.repositories.refresh_token_repository import RefreshTokenRepository
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from app.repositories.system_event_repository import SystemEventRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.twin_state_repository import TwinStateRepository

__all__ = [
    "AthleteAuthRepository",
    "AthleteFitnessRepository",
    "AthletePhysiologyRepository",
    "AthletePreferencesRepository",
    "AthleteProfileRepository",
    "AthleteRepository",
    "RefreshTokenRepository",
    "SystemEventOutboxRepository",
    "SystemEventRepository",
    "TrainingGoalRepository",
    "TwinStateRepository",
]
