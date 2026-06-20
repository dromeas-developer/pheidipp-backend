"""Enumerations shared across models in the Athis architecture."""

from enum import Enum


class AuthProvider(str, Enum):
    """Authentication method used by a given AthleteAuth record."""

    EMAIL = "email"
    GOOGLE = "google"
    STRAVA = "strava"


class Sex(str, Enum):
    """Biological sex for demographic identity and cycle tracking."""

    MALE = "male"
    FEMALE = "female"
    NOT_SPECIFIED = "not_specified"
