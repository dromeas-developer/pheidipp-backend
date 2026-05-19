"""Factory functions for TwinState model."""

import uuid
from datetime import datetime

from app.models.twin_state import TwinState
from app.models.enums import (
    TwinTrigger,
    ConfidenceLevel,
    DataTier,
)
from app.schemas.twin_state import TwinStateCreate


def make_twin_state(
    athlete_id: uuid.UUID | None = None,
    athlete_preferences_id: uuid.UUID | None = None,
    **overrides,
) -> TwinState:
    """Create a minimal valid TwinState instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    if athlete_preferences_id is None:
        athlete_preferences_id = uuid.uuid4()

    # Pop known fields from overrides to avoid duplicate keyword argument errors
    # Use overrides values if provided, otherwise use defaults
    fitness_score = overrides.pop("fitness_score", 50.0)
    fatigue_score = overrides.pop("fatigue_score", 0.0)
    max_hr_estimate = overrides.pop("max_hr_estimate", 187.0)
    lt1_hr_estimate = overrides.pop("lt1_hr_estimate", 130.9)
    lt2_hr_estimate = overrides.pop("lt2_hr_estimate", 155.2)
    lt1_pace_estimate = overrides.pop("lt1_pace_estimate", None)
    lt2_pace_estimate = overrides.pop("lt2_pace_estimate", None)
    structural_capacity_score = overrides.pop("structural_capacity_score", 0.7)
    fitness_time_constant = overrides.pop("fitness_time_constant", 42.0)
    fatigue_time_constant = overrides.pop("fatigue_time_constant", 7.0)

    return TwinState(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        athlete_preferences_id=athlete_preferences_id,
        trigger=TwinTrigger.QUESTIONNAIRE,
        confidence_level=ConfidenceLevel.LOW,
        data_tier=DataTier.TIER1,
        fitness_score=fitness_score,
        fatigue_score=fatigue_score,
        max_hr_estimate=max_hr_estimate,
        lt1_hr_estimate=lt1_hr_estimate,
        lt2_hr_estimate=lt2_hr_estimate,
        lt1_pace_estimate=lt1_pace_estimate,
        lt2_pace_estimate=lt2_pace_estimate,
        structural_capacity_score=structural_capacity_score,
        fitness_time_constant=fitness_time_constant,
        fatigue_time_constant=fatigue_time_constant,
        computation_summary="Age 30, male, fitness score 50.0, data tier tier1, structural capacity 0.70, max HR formula: Tanaka",
        computation_metadata={
            "age": 30,
            "fitness_score": 50.0,
            "data_tier": "tier1",
            "structural_capacity_score": 0.7,
            "gender": "male",
            "max_hr_formula": "Tanaka",
        },
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_twin_state_full(
    athlete_id: uuid.UUID | None = None,
    athlete_preferences_id: uuid.UUID | None = None,
    **overrides,
) -> TwinState:
    """Create a TwinState instance with all fields populated."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    if athlete_preferences_id is None:
        athlete_preferences_id = uuid.uuid4()

    # Pop known fields from overrides to avoid duplicate keyword argument errors
    fitness_score = overrides.pop("fitness_score", 75.0)
    fatigue_score = overrides.pop("fatigue_score", 25.0)
    max_hr_estimate = overrides.pop("max_hr_estimate", 190.0)
    lt1_hr_estimate = overrides.pop("lt1_hr_estimate", 138.7)
    lt2_hr_estimate = overrides.pop("lt2_hr_estimate", 161.5)
    lt1_pace_estimate = overrides.pop("lt1_pace_estimate", 5.5)
    lt2_pace_estimate = overrides.pop("lt2_pace_estimate", 4.2)
    structural_capacity_score = overrides.pop("structural_capacity_score", 0.8)
    fitness_time_constant = overrides.pop("fitness_time_constant", 42.0)
    fatigue_time_constant = overrides.pop("fatigue_time_constant", 7.0)

    return TwinState(
        id=uuid.uuid4(),
        athlete_id=athlete_id,
        athlete_preferences_id=athlete_preferences_id,
        trigger=TwinTrigger.CALIBRATION,
        confidence_level=ConfidenceLevel.HIGH,
        data_tier=DataTier.TIER1,
        fitness_score=fitness_score,
        fatigue_score=fatigue_score,
        max_hr_estimate=max_hr_estimate,
        lt1_hr_estimate=lt1_hr_estimate,
        lt2_hr_estimate=lt2_hr_estimate,
        lt1_pace_estimate=lt1_pace_estimate,
        lt2_pace_estimate=lt2_pace_estimate,
        structural_capacity_score=structural_capacity_score,
        fitness_time_constant=fitness_time_constant,
        fatigue_time_constant=fatigue_time_constant,
        computation_summary="Age 35, female, fitness score 75.0, data tier tier1, structural capacity 0.80, max HR formula: Gulati",
        computation_metadata={
            "age": 35,
            "fitness_score": 75.0,
            "data_tier": "tier1",
            "structural_capacity_score": 0.8,
            "gender": "female",
            "max_hr_formula": "Gulati",
        },
        created_at=datetime(2024, 1, 1, 0, 0, 0),
        **overrides,
    )


def make_twin_state_batch(
    n: int,
    athlete_id: uuid.UUID | None = None,
    athlete_preferences_id: uuid.UUID | None = None,
    **overrides,
) -> list[TwinState]:
    """Create a list of n TwinState instances."""
    return [
        make_twin_state(athlete_id, athlete_preferences_id, **overrides)
        for _ in range(n)
    ]


def make_twin_state_create_schema(
    athlete_id: uuid.UUID | None = None,
    athlete_preferences_id: uuid.UUID | None = None,
    **overrides,
) -> TwinStateCreate:
    """Create a TwinStateCreate Pydantic schema instance."""
    if athlete_id is None:
        athlete_id = uuid.uuid4()
    if athlete_preferences_id is None:
        athlete_preferences_id = uuid.uuid4()

    # Pop known fields from overrides to avoid duplicate keyword argument errors
    fitness_score = overrides.pop("fitness_score", 50.0)
    fatigue_score = overrides.pop("fatigue_score", 0.0)
    max_hr_estimate = overrides.pop("max_hr_estimate", 187.0)
    lt1_hr_estimate = overrides.pop("lt1_hr_estimate", 130.9)
    lt2_hr_estimate = overrides.pop("lt2_hr_estimate", 155.2)
    lt1_pace_estimate = overrides.pop("lt1_pace_estimate", None)
    lt2_pace_estimate = overrides.pop("lt2_pace_estimate", None)
    structural_capacity_score = overrides.pop("structural_capacity_score", 0.7)
    fitness_time_constant = overrides.pop("fitness_time_constant", 42.0)
    fatigue_time_constant = overrides.pop("fatigue_time_constant", 7.0)

    return TwinStateCreate(
        athlete_id=athlete_id,
        athlete_preferences_id=athlete_preferences_id,
        trigger=TwinTrigger.QUESTIONNAIRE,
        confidence_level=ConfidenceLevel.LOW,
        data_tier=DataTier.TIER1,
        fitness_score=fitness_score,
        fatigue_score=fatigue_score,
        max_hr_estimate=max_hr_estimate,
        lt1_hr_estimate=lt1_hr_estimate,
        lt2_hr_estimate=lt2_hr_estimate,
        lt1_pace_estimate=lt1_pace_estimate,
        lt2_pace_estimate=lt2_pace_estimate,
        structural_capacity_score=structural_capacity_score,
        fitness_time_constant=fitness_time_constant,
        fatigue_time_constant=fatigue_time_constant,
        computation_summary="Test summary",
        computation_metadata={"test": "data"},
        **overrides,
    )