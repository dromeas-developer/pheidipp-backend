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
from app.models.checkpoint import Checkpoint
from app.models.enums import (
    ActivitySource,
    AuthProvider,
    CheckpointStatus,
    CheckpointType,
    DataTier,
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    InjurySeverity,
    ObjectiveCategory,
    PhaseLabel,
    PlannedSessionStatus,
    PowerSource,
    PrimaryTrainingPlatform,
    SecondaryEventPriority,
    SessionPriority,
    SessionSlot,
    SessionType,
    Sex,
    SportBackground,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TrainingTimeOfDay,
    WeeklyPlanStatus,
)
from app.models.planned_session import PlannedSession
from app.models.regeneration_task import RegenerationTask
from app.models.refresh_token import RefreshToken
from app.models.secondary_event import SecondaryEvent
from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan, WeeklySession

__all__ = [
    "Activity",
    "ActivitySource",
    "Athlete",
    "AthleteAuth",
    "AthletePreferences",
    "AthleteProfile",
    "AuthProvider",
    "Checkpoint",
    "CheckpointStatus",
    "CheckpointType",
    "DataTier",
    "EventPublicationStatus",
    "GoalEventType",
    "GoalType",
    "GpsSource",
    "HrSource",
    "InjurySeverity",
    "ObjectiveCategory",
    "PhaseLabel",
    "PlannedSession",
    "PlannedSessionStatus",
    "PowerSource",
    "PrimaryTrainingPlatform",
    "RefreshToken",
    "RegenerationTask",
    "SecondaryEvent",
    "SecondaryEventPriority",
    "SessionPriority",
    "SessionSlot",
    "SessionType",
    "Sex",
    "SportBackground",
    "SystemEvent",
    "SystemEventOutbox",
    "TrainingGoal",
    "TrainingGoalStatus",
    "TrainingPlan",
    "TrainingPlanStatus",
    "TrainingTimeOfDay",
    "WeeklyPlan",
    "WeeklyPlanStatus",
    "WeeklySession",
    "infer_data_tier",
]
