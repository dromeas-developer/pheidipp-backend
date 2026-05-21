"""Factory functions for TrainingPlan and PlannedSession models."""

import uuid
from datetime import date, datetime

from app.models.training_plan import TrainingPlan
from app.models.planned_session import PlannedSession
from app.models.enums import TrainingPlanStatus, SessionType, PhysiologicalIntent, TrainingPhase


def make_training_plan(athlete_id: uuid.UUID | None = None, **overrides) -> TrainingPlan:
    """Create a minimal valid TrainingPlan instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    known_fields = {
        "id", "athlete_id", "training_block_id", "status", "created_at",
        "archived_at", "generation_metadata", "plan_rationale",
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return TrainingPlan(
        id=overrides.get("id", uuid.uuid4()),
        athlete_id=overrides.get("athlete_id", athlete_id),
        training_block_id=overrides.get("training_block_id", None),
        status=overrides.get("status", TrainingPlanStatus.ACTIVE),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        archived_at=overrides.get("archived_at", None),
        generation_metadata=overrides.get("generation_metadata", {}),
        plan_rationale=overrides.get("plan_rationale", None),
        **filtered_overrides,
    )


def make_training_plan_full(athlete_id: uuid.UUID | None = None, **overrides) -> TrainingPlan:
    """Create a fully populated TrainingPlan instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    known_fields = {
        "id", "athlete_id", "training_block_id", "status", "created_at",
        "archived_at", "generation_metadata", "plan_rationale",
    }
    filtered_overrides = {k: v for k, v in overrides.items() if k not in known_fields}

    return TrainingPlan(
        id=overrides.get("id", uuid.uuid4()),
        athlete_id=overrides.get("athlete_id", athlete_id),
        training_block_id=overrides.get("training_block_id", uuid.uuid4()),
        status=overrides.get("status", TrainingPlanStatus.ACTIVE),
        created_at=overrides.get("created_at", datetime(2024, 1, 1, 0, 0, 0)),
        archived_at=overrides.get("archived_at", None),
        generation_metadata=overrides.get(
            "generation_metadata",
            {
                "methodology_profile": {
                    "trait_weights": {
                        "HIGH_AEROBIC_VOLUME": 1.0,
                        "LOW_INTENSITY_DOMINANT": 0.9,
                        "THRESHOLD_DENSITY": 0.2,
                        "HIGH_INTENSITY_SPARSE": 0.3,
                        "HIGH_FREQUENCY": 0.7,
                        "STRUCTURAL_DURABILITY": 0.6,
                        "RACE_SPECIFICITY": 0.2,
                        "VARIETY_EMPHASIS": 0.5,
                        "NEUROMUSCULAR_SUPPORT": 0.5,
                        "CONSERVATIVE_PROGRESSION": 0.8,
                    }
                },
                "model": "test-model",
                "prompt_version": "v1",
            },
        ),
        plan_rationale=overrides.get(
            "plan_rationale",
            "Build aerobic base with progressive intensity.",
        ),
        **filtered_overrides,
    )


def make_training_plan_batch(
    n: int, athlete_id: uuid.UUID | None = None, **overrides
) -> list[TrainingPlan]:
    """Create a list of n TrainingPlan instances."""
    return [make_training_plan(athlete_id, **overrides) for _ in range(n)]


def make_archived_training_plan(
    athlete_id: uuid.UUID | None = None, **overrides
) -> TrainingPlan:
    """Create a TrainingPlan with ARCHIVED status."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()

    return make_training_plan(
        athlete_id,
        status=TrainingPlanStatus.ARCHIVED,
        archived_at=overrides.get("archived_at", datetime(2024, 6, 1, 0, 0, 0)),
        **overrides,
    )