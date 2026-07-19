"""Workout target-type and intent constants for WorkoutGenerationAgent."""

from __future__ import annotations

from app.models.enums import DataTier, PhysiologicalIntent, SessionType, StepType


SESSION_INTENT_MAP: dict[SessionType, PhysiologicalIntent] = {
    SessionType.REST: PhysiologicalIntent.RECOVERY,
    SessionType.RECOVERY_RUN: PhysiologicalIntent.RECOVERY,
    SessionType.EASY_RUN: PhysiologicalIntent.LOW_AEROBIC,
    SessionType.LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.MEDIUM_LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.STEADY_STATE: PhysiologicalIntent.HIGH_AEROBIC,
    SessionType.TEMPO: PhysiologicalIntent.THRESHOLD,
    SessionType.THRESHOLD: PhysiologicalIntent.THRESHOLD,
    SessionType.VO2MAX: PhysiologicalIntent.VO2MAX,
    SessionType.HILL_REPEATS: PhysiologicalIntent.VO2MAX,
    SessionType.FARTLEK: PhysiologicalIntent.VO2MAX,
    SessionType.STRIDES: PhysiologicalIntent.NEUROMUSCULAR,
    SessionType.DRILLS_MOBILITY: PhysiologicalIntent.NEUROMUSCULAR,
    SessionType.CROSS_TRAINING: PhysiologicalIntent.LOW_AEROBIC,
    SessionType.TEST_SESSION: PhysiologicalIntent.VO2MAX,
    SessionType.OPTIONAL_RUN: PhysiologicalIntent.RECOVERY,
}


DATA_TIER_TARGET_TYPE: dict[DataTier, str] = {
    DataTier.TIER_1: "power",
    DataTier.TIER_2: "power",
    DataTier.TIER_3: "gap",
    DataTier.TIER_4: "gap",
    DataTier.TIER_5: "description",
    DataTier.TIER_6: "description",
}


def get_step_physiological_intent(
    step_type: StepType, session_type: SessionType
) -> PhysiologicalIntent:
    """Return prescribed PhysiologicalIntent for a (step, session) pair."""
    if step_type in {StepType.WARMUP, StepType.COOLDOWN, StepType.RECOVERY}:
        return PhysiologicalIntent.RECOVERY
    # StepType.WORK — derive from session_type via map.
    return SESSION_INTENT_MAP[session_type]
