"""Persistence models for Pheidipp.

Importing this package registers all model metadata with ``Base.metadata``
so alembic autogenerate can discover every table declared in Phase scope.
"""

from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.athlete_profile import AthleteProfile
from app.models.enums import AuthProvider, Sex
from app.models.refresh_token import RefreshToken
from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)

__all__ = [
    "Athlete",
    "AthleteAuth",
    "AthleteProfile",
    "AuthProvider",
    "EventPublicationStatus",
    "RefreshToken",
    "Sex",
    "SystemEvent",
    "SystemEventOutbox",
]
