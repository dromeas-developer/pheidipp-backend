"""Error types for ``WorkoutGenerationAgent``.

Mirrors the first-message-agent error module pattern. Each domain
failure case is its own subclass so the API layer can map cleanly to
specific HTTP status codes:

* :class:`PlannedSessionNotFoundError` → 404
* :class:`WorkoutAlreadyGeneratedError` → 409 (POST generate endpoint)
* :class:`LLMServiceUnavailableError` → 502 (LLM proxy failure;
  distinct status vs. first-message's 503 so we can switch keep-alive
  behaviour separately.)

All errors are constructed with the athlete_id (where relevant) and
the necessary cross-references so the API layer can format a
deterministic detail string. They never carry ORM sessions —
:exc:`Exception.args` is the surfaced payload.
"""

from __future__ import annotations

import uuid


class WorkoutGenerationError(Exception):
    """Base class for ``WorkoutGenerationAgent`` domain failures.

    The API layer catches this base when fall-through behaviour is
    acceptable (e.g. observability hooks). Endpoint handlers map the
    specific subclasses below to HTTP status codes.
    """


class PlannedSessionNotFoundError(WorkoutGenerationError):
    """The requested ``planned_session_id`` does not exist.

    The API layer maps this to HTTP 404.
    """

    def __init__(self, planned_session_id: uuid.UUID) -> None:
        super().__init__(
            f"planned session {planned_session_id} not found"
        )
        self.planned_session_id = planned_session_id


class WorkoutAlreadyGeneratedError(WorkoutGenerationError):
    """A ``GeneratedWorkout`` already exists for this key.

    Raised by the explicit ``POST /generate-workout`` endpoint when
    the unique constraint ``(planned_session_id, generation_date)``
    is already satisfied. The API layer maps this to HTTP 409 and
    returns the existing workout id in the detail body.

    The idempotent ``GET /athletes/{id}/today`` lookup does NOT
    raise this — it returns the existing workout transparently per
    the architecture idempotency contract.
    """

    def __init__(self, existing_workout_id: uuid.UUID) -> None:
        super().__init__(
            "workout already generated for this session and date"
        )
        self.existing_workout_id = existing_workout_id


class LLMServiceUnavailableError(WorkoutGenerationError):
    """The LLM call failed (proxy unavailable, rate limit, timeout, etc.).

    The API layer maps this to HTTP 502 so callers can distinguish a
    workout-generation LLM outage from ``FirstMessageAgent``'s more
    general ``503 Service Unavailable``. The is-502-is-vs-503 split is
    deliberate: ``generate-workout`` callers are coached workflows
    that may want to retry; 502 communicates "bad gateway upstream"
    with that nuance, while 503 stays reserved for the first-message
    service-wide outage.
    """


class WorkoutGenerationContractError(Exception):
    """LLM output violated a structural invariant of the workout schema.

    Raised by the validator when steps fail the warmup-first /
    cooldown-last / sequential order / intent-never-null /
    target-type-shape rules. The agent catches this and writes a
    ``GenerationEvent(success=False, failure_reason="invalid_output_format")``
    before converting it to :class:`LLMServiceUnavailableError` for
    the route. This type is kept separate so test code can assert
    the validator trigger without going through the LLM-error
    mapping.
    """
