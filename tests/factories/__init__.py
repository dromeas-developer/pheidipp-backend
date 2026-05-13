from tests.factories.athlete_factory import (
    make_athlete,
    make_athlete_full,
    make_athlete_batch,
    make_athlete_profile,
    make_athlete_profile_full,
    make_athlete_profile_batch,
)
from tests.factories.activity_factory import (
    make_activity,
    make_activity_full,
    make_activity_batch,
)
from tests.factories.physiology_factory import (
    make_athlete_physiology,
    make_athlete_physiology_full,
    make_athlete_physiology_batch,
)
from tests.factories.training_preferences_factory import (
    make_training_preferences,
    make_training_preferences_full,
    make_training_preferences_batch,
)
from tests.factories.wellness_factory import (
    make_athlete_wellness,
    make_athlete_wellness_full,
    make_athlete_wellness_batch,
)

__all__ = [
    # Athlete
    "make_athlete",
    "make_athlete_full",
    "make_athlete_batch",
    # Athlete Profile
    "make_athlete_profile",
    "make_athlete_profile_full",
    "make_athlete_profile_batch",
    # Activity
    "make_activity",
    "make_activity_full",
    "make_activity_batch",
    # Physiology
    "make_athlete_physiology",
    "make_athlete_physiology_full",
    "make_athlete_physiology_batch",
    # Training Preferences
    "make_training_preferences",
    "make_training_preferences_full",
    "make_training_preferences_batch",
    # Wellness
    "make_athlete_wellness",
    "make_athlete_wellness_full",
    "make_athlete_wellness_batch",
]
