"""Persistence models for Pheidipp.

Importing this package registers all model metadata with ``Base.metadata``
so alembic autogenerate can discover every table declared in Phase scope.
"""

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.athlete_preferences import (
    AthletePreferences,
    infer_data_tier,
)
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    ActivitySource,
    AuthProvider,
    DataTier,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    Sex,
    SportBackground,
    TrainingTimeOfDay,
)
from app.models.refresh_token import RefreshToken
from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)

__all__ = [
    "Activity",
    "ActivitySource",
    "Athlete",
    "AthleteAuth",
    "AthletePreferences",
    "AthleteProfile",
    "AuthProvider",
    "DataTier",
    "EventPublicationStatus",
    "GpsSource",
    "HrSource",
    "PowerSource",
    "PrimaryTrainingPlatform",
    "RefreshToken",
    "Sex",
    "SportBackground",
    "SystemEvent",
    "SystemEventOutbox",
    "TrainingTimeOfDay",
    "infer_data_tier",
]
