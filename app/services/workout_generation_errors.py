"""Error types for WorkoutGenerationAgent."""

from __future__ import annotations

import uuid


class WorkoutGenerationError(Exception):
    """Base class for WorkoutGenerationAgent domain failures."""


class PlannedSessionNotFoundError(WorkoutGenerationError):
    """The requested planned_session_id does not exist (HTTP 404)."""

    def __init__(self, planned_session_id: uuid.UUID) -> None:
        super().__init__(f"planned session {planned_session_id} not found")
        self.planned_session_id = planned_session_id


class WorkoutAlreadyGeneratedError(WorkoutGenerationError):
    """A GeneratedWorkout already exists for this key (HTTP 409)."""

    def __init__(self, existing_workout_id: uuid.UUID) -> None:
        super().__init__("workout already generated for this session and date")
        self.existing_workout_id = existing_workout_id


class LLMServiceUnavailableError(WorkoutGenerationError):
    """LLM call failed (HTTP 502)."""


class WorkoutGenerationContractError(Exception):
    """LLM output violated a structural invariant of the workout schema."""
