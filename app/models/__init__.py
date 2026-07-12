"""Persistence models for Pheidipp.

Importing this package registers all model metadata with ``Base.metadata``
so alembic autogenerate can discover every table declared in Phase scope.
"""

from app.models.activity import Activity
from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import (
    AthletePreferences,
    infer_data_tier,
)
from app.models.athlete_profile import AthleteProfile
from app.models.checkpoint import Checkpoint
from app.models.coaching_message import CoachingMessage
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
    MeasurementSource,
    MessageType,
    ObjectiveCategory,
    PhaseLabel,
    PhysiologicalIntent,
    PhysiologyParameter,
    PlannedSessionStatus,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    SecondaryEventPriority,
    SessionPriority,
    SessionPurpose,
    SessionSlot,
    SessionType,
    Sex,
    SignalType,
    SportBackground,
    SportType,
    StepType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TrainingTimeOfDay,
    TwinConfidenceLevel,
    TwinTrigger,
    WeeklyPlanStatus,
    WellnessTrend,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.generation_event import GenerationEvent
from app.models.physiology_measurement import PhysiologyMeasurement
from app.models.planned_session import PlannedSession
from app.models.raw_sensor_stream import RawSensorStream
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
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan, WeeklySession
from app.models.workout_step import WorkoutStep

__all__ = [
    "Activity",
    "ActivitySource",
    "Athlete",
    "AthleteAuth",
    "AthleteFitness",
    "AthletePhysiology",
    "AthletePreferences",
    "AthleteProfile",
    "AuthProvider",
    "Checkpoint",
    "CheckpointStatus",
    "CheckpointType",
    "CoachingMessage",
    "DataTier",
    "EventPublicationStatus",
    "GeneratedWorkout",
    "GenerationEvent",
    "GoalEventType",
    "GoalType",
    "GpsSource",
    "HrSource",
    "InjurySeverity",
    "MeasurementSource",
    "MessageType",
    "ObjectiveCategory",
    "PhaseLabel",
    "PhysiologicalIntent",
    "PhysiologyMeasurement",
    "PhysiologyParameter",
    "PlannedSession",
    "PlannedSessionStatus",
    "PowerSource",
    "PrimaryTrainingPlatform",
    "RawSensorStream",
    "RecoveryModifierLevel",
    "RefreshToken",
    "RegenerationTask",
    "SecondaryEvent",
    "SecondaryEventPriority",
    "SessionPriority",
    "SessionPurpose",
    "SessionSlot",
    "SessionType",
    "Sex",
    "SignalType",
    "SportBackground",
    "SportType",
    "StepType",
    "SystemEvent",
    "SystemEventOutbox",
    "TrainingGoal",
    "TrainingGoalStatus",
    "TrainingPlan",
    "TrainingPlanStatus",
    "TrainingTimeOfDay",
    "TwinConfidenceLevel",
    "TwinState",
    "TwinTrigger",
    "WeeklyPlan",
    "WeeklyPlanStatus",
    "WeeklySession",
    "WellnessTrend",
    "WorkoutStep",
    "infer_data_tier",
]
