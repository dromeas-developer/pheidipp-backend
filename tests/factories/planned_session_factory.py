"""Factory functions for PlannedSession model."""

import uuid
from datetime import date, datetime

from app.models.planned_session import PlannedSession
from app.models.enums import SessionType, PhysiologicalIntent, TrainingPhase


def make_planned_session(
    training_plan_id: uuid.UUID | None = None, **overrides
) -> PlannedSession:
    """Create a minimal valid PlannedSession instance."""
    if training_plan_id is None:
        training_plan_id = uuid.uuid4()

    known_fields = {
        "id", "training_plan_id", "scheduled_date", "session_type",
        "dominant_physiological_intent", "target_duration_minutes",
        "is_key_session", "week_number", "phase", "generation_metadata",
        "created_at",
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return PlannedSession(
        id=overrides.get("id", uuid.uuid4()),
        training_plan_id=overrides.get("training_plan_id", training_plan_id),
        scheduled_date=overrides.get("scheduled_date", date(2024, 1, 15)),
        session_type=overrides.get("session_type", SessionType.EASY_RUN),
        dominant_physiological_intent=overrides.get(
            "dominant_physiological_intent", PhysiologicalIntent.LOW_AEROBIC
        ),
        target_duration_minutes=overrides.get("target_duration_minutes", None),
        is_key_session=overrides.get("is_key_session", False),
        week_number=overrides.get("week_number", 1),
        phase=overrides.get("phase", TrainingPhase.BASE),
        generation_metadata=overrides.get("generation_metadata", None),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_planned_session_full(
    training_plan_id: uuid.UUID | None = None, **overrides
) -> PlannedSession:
    """Create a fully populated PlannedSession instance."""
    if training_plan_id is None:
        training_plan_id = uuid.uuid4()

    known_fields = {
        "id", "training_plan_id", "scheduled_date", "session_type",
        "dominant_physiological_intent", "target_duration_minutes",
        "is_key_session", "week_number", "phase", "generation_metadata",
        "created_at",
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return PlannedSession(
        id=overrides.get("id", uuid.uuid4()),
        training_plan_id=overrides.get("training_plan_id", training_plan_id),
        scheduled_date=overrides.get("scheduled_date", date(2024, 1, 15)),
        session_type=overrides.get("session_type", SessionType.LONG_RUN),
        dominant_physiological_intent=overrides.get(
            "dominant_physiological_intent", PhysiologicalIntent.HIGH_AEROBIC
        ),
        target_duration_minutes=overrides.get("target_duration_minutes", 120),
        is_key_session=overrides.get("is_key_session", True),
        week_number=overrides.get("week_number", 1),
        phase=overrides.get("phase", TrainingPhase.BASE),
        generation_metadata=overrides.get(
            "generation_metadata",
            {"model": "test-model", "prompt_version": "v1"},
        ),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        **filtered_overrides,
    )


def make_planned_session_batch(
    n: int, training_plan_id: uuid.UUID | None = None, **overrides
) -> list[PlannedSession]:
    """Create a list of n PlannedSession instances."""
    return [make_planned_session(training_plan_id, **overrides) for _ in range(n)]


def make_week_sessions(
    training_plan_id: uuid.UUID,
    week_number: int,
    phase: TrainingPhase,
    day_assignments: dict[str, str],
) -> list[PlannedSession]:
    """Create sessions for a given week.

    Args:
        training_plan_id: The ID of the parent training plan.
        week_number: The week number.
        phase: The training phase for the week.
        day_assignments: Dict mapping day names (e.g., "mon") to session type strings.
            Example: {"mon": "easy_run", "wed": "threshold", "sat": "long_run"}
    """
    sessions = []
    day_start = date(2024, 1, 1)  # Reference date for scheduling
    weekday_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

    # Base date for the given week number
    week_base = day_start + datetime.timedelta(days=(week_number - 1) * 7)

    for day_name, session_type_str in day_assignments.items():
        day_offset = weekday_map.get(day_name, 0)
        scheduled_date = week_base + datetime.timedelta(days=day_offset)
        session_type = SessionType(session_type_str)

        sessions.append(
            PlannedSession(
                id=uuid.uuid4(),
                training_plan_id=training_plan_id,
                scheduled_date=scheduled_date,
                session_type=session_type,
                dominant_physiological_intent=_session_type_to_intent(session_type),
                target_duration_minutes=None,
                is_key_session=False,
                week_number=week_number,
                phase=phase,
                generation_metadata=None,
                created_at=datetime(2024, 1, 1, 0, 0, 0),
            )
        )

    return sessions


def _session_type_to_intent(session_type: SessionType) -> PhysiologicalIntent:
    """Map session type to dominant physiological intent."""
    mapping = {
        SessionType.REST: PhysiologicalIntent.RECOVERY_SUPPORT,
        SessionType.RECOVERY_RUN: PhysiologicalIntent.RECOVERY_SUPPORT,
        SessionType.EASY_RUN: PhysiologicalIntent.LOW_AEROBIC,
        SessionType.LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
        SessionType.MEDIUM_LONG_RUN: PhysiologicalIntent.HIGH_AEROBIC,
        SessionType.STEADY_STATE: PhysiologicalIntent.HIGH_AEROBIC,
        SessionType.TEMPO: PhysiologicalIntent.THRESHOLD,
        SessionType.THRESHOLD: PhysiologicalIntent.THRESHOLD,
        SessionType.VO2MAX: PhysiologicalIntent.VO2MAX,
        SessionType.HILL_REPEATS: PhysiologicalIntent.VO2MAX,
        SessionType.FARTLEK: PhysiologicalIntent.VO2MAX,
        SessionType.RACE_SPECIFIC: PhysiologicalIntent.RACE_SPECIFIC,
        SessionType.STRIDES: PhysiologicalIntent.NEUROMUSCULAR,
        SessionType.DRILLS_MOBILITY: PhysiologicalIntent.NEUROMUSCULAR,
        SessionType.CROSS_TRAINING: PhysiologicalIntent.LOW_AEROBIC,
        SessionType.TEST_SESSION: PhysiologicalIntent.CALIBRATION,
        SessionType.OPTIONAL_RUN: PhysiologicalIntent.RECOVERY_SUPPORT,
    }
    return mapping.get(session_type, PhysiologicalIntent.LOW_AEROBIC)