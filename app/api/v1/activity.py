"""Activity API surface — five endpoints behind ``require_self``.

Implements the Phase-1.6 + Phase-1.8 contract from
``docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md`` and
``docs/implementation/phase-1/phase-1-8-p1-fix-event-ordering-and-async-processing.md``:

* ``POST /athletes/{athlete_id}/activities/upload`` — accept FIT
  file, stage to object storage + persist an empty ``Activity``
  row, enqueue the ``fit_ingest`` procrastinate task, and return
  ``202 Accepted`` with the worker's ``task_id``.
* ``GET  /athletes/{athlete_id}/activities`` — paginated list.
* ``GET  /athletes/{athlete_id}/activities/{activity_id}`` — single
  activity (404 when missing or cross-athlete).
* ``POST /athletes/{athlete_id}/activities/{activity_id}/analyse`` —
  trigger ``PostWorkoutAgent``. Idempotent — second call returns
  the existing message without re-invoking the LLM.
* ``GET  /athletes/{athlete_id}/activities/{activity_id}/analysis`` —
  fetch the existing analysis + coaching message (404 when none).

All endpoints depend on ``require_self`` so the JWT's
``athlete_id`` must equal the path parameter — mismatches surface
as HTTP 403, never 404, so authentication and authorization
failures remain distinguishable.

Transaction ownership mirrors the first-message-agent and
workout-generation-agent patterns: the agent / ingestion service
does NOT commit. The upload handler commits once after the
``stage_upload`` returns so the empty Activity row is durable
before the worker task is enqueued; the worker commits once
after ``ingest_async`` returns so the populated Activity,
``TwinState``, and outbox row land atomically.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.post_workout_agent import (
    ActivityNotFoundError,
    PostWorkoutAgent,
    PostWorkoutLLMUnavailableError,
)
from app.api.deps import get_db, require_self
from app.models.enums import ActivitySource, MessageType
from app.repositories.activity_repository import ActivityRepository
from app.repositories.coaching_message_repository import (
    CoachingMessageRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.planned_session_repository import PlannedSessionRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.schemas.activity import (
    ActivityListResponse,
    ActivityResponse,
    ActivityUploadResponse,
    CoachingMessageSummary,
    PostWorkoutAnalysisResponse,
)
from app.services.activity_ingestion_service import (
    ActivityIngestionError,
    ActivityIngestionService,
    ObjectStorageFailureError,
)
from app.services.compliance_service import ComplianceService
from app.worker.app import app as procrastinate_app


# Maximum upload size (bytes). 10MB matches the
# ``python-multipart`` default and comfortably holds a 4-hour FIT
# file at 1Hz HR + GPS.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


activity_router = APIRouter(prefix="/athletes", tags=["activity"])


# ---------------------------------------------------------------------------
# Dependency factories — kept module-level so each endpoint stays a thin
# wrapper around the agent / service / repositories.
# ---------------------------------------------------------------------------


def build_activity_ingestion_service(
    session: AsyncSession = Depends(get_db),
) -> ActivityIngestionService:
    """Construct an :class:`ActivityIngestionService` for the current request."""
    return ActivityIngestionService(session=session)


def build_post_workout_agent(
    session: AsyncSession = Depends(get_db),
) -> PostWorkoutAgent:
    """Construct a :class:`PostWorkoutAgent` for the current request."""
    return PostWorkoutAgent(
        session=session,
        coaching_messages=CoachingMessageRepository(session),
        generation_events=GenerationEventRepository(session),
        activities=ActivityRepository(session),
        planned_sessions=PlannedSessionRepository(session),
        twin_states=TwinStateRepository(session),
        prompt_registry=_shared_prompt_registry(),
        compliance_service=ComplianceService(),
    )


def build_activity_repository(
    session: AsyncSession = Depends(get_db),
) -> ActivityRepository:
    """Construct an :class:`ActivityRepository` for the current request."""
    return ActivityRepository(session=session)


def build_coaching_message_repository(
    session: AsyncSession = Depends(get_db),
) -> CoachingMessageRepository:
    """Construct a :class:`CoachingMessageRepository` for the current request."""
    return CoachingMessageRepository(session=session)


def _shared_prompt_registry():
    """Return the process-wide prompt registry singleton.

    Lazy import to avoid a top-level cycle between the activity
    router and the agent module.
    """
    from app.core.prompt_registry import get_default_prompt_registry

    return get_default_prompt_registry()


# ---------------------------------------------------------------------------
# Endpoints.
# ---------------------------------------------------------------------------


@activity_router.post(
    "/{athlete_id}/activities/upload",
    response_model=ActivityUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_upload_activity(
    athlete_id: uuid.UUID,
    file: UploadFile = File(...),
    planned_session_id: Optional[uuid.UUID] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    auth_athlete_id: uuid.UUID = Depends(require_self),
    service: ActivityIngestionService = Depends(
        build_activity_ingestion_service
    ),
    session: AsyncSession = Depends(get_db),
) -> ActivityUploadResponse:
    """Stage a FIT file upload and enqueue async ingestion.

    The endpoint performs only the cheap, synchronous staging work
    required by the architecture invariant "object-storage upload
    happens BEFORE Activity creation":

        1. Read the upload bytes (size-checked).
        2. Upload the raw FIT to object storage.
        3. Persist an empty ``Activity`` row (``fit_file_key`` set,
           load scores ``null``) — no parsing, no load computation,
           no twin recalibration. This row is the durable reprocessing
           anchor.
        4. Commit the staging transaction so the empty Activity is
           visible to the worker.
        5. Enqueue the ``fit_ingest`` procrastinate task carrying
           ``activity_id`` and ``athlete_id`` so the worker can pick
           up the heavy parse / load / twin / event-publish pipeline.
        6. Return ``202 Accepted`` with ``task_id`` (the procrastinate
           job id) and the staged ``Activity``.

    The API response never blocks on FIT parsing, load computation,
    or twin recalibration — those run in the ``fit_ingest`` worker
    task per ``04-platform/async-pipeline.md``.

    Errors:

    * 503 — object storage upload failed (architecture invariant:
      no ``Activity`` row is created when storage fails).
    * 422 — uploaded file is empty / too large / activity creation
      failed.
    * 403 — JWT athlete_id mismatch with the path parameter.
    * 413 — uploaded file exceeds the size limit.
    """
    file_bytes = await _read_upload_bytes(file)
    try:
        activity = await service.stage_upload(
            athlete_id=athlete_id,
            file_bytes=file_bytes,
            planned_session_id=planned_session_id,
            source=ActivitySource.MANUAL_UPLOAD,
            notes=notes,
        )
    except ObjectStorageFailureError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
    except ActivityIngestionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )

    # Commit before enqueue so the worker never observes a queue
    # item that resolves to a missing / uncommitted Activity row.
    await session.commit()

    # Enqueue the heavy ingestion pipeline. Procrastinate's
    # ``defer`` returns the job id as an ``int`` (not a
    # ``Job`` object). We promote it to a ``UUID`` here so the
    # response schema's ``task_id: UUID`` field is satisfied.
    # The conversion is lossless and reversible:
    # ``UUID(int=job_id << 96).int >> 96 == job_id``.
    #
    # ``defer`` (sync) is used because the shared procrastinate
    # app is configured with ``Psycopg2Connector`` (sync-only);
    # ``defer_async`` would unconditionally raise
    # ``SyncConnectorConfigurationError``. The defer operation
    # is a lightweight single-row INSERT into ``procrastinate_jobs``
    # — negligible blocking time from an async endpoint.
    job = procrastinate_app.tasks["fit_ingest"].defer(  # type: ignore
        athlete_id=str(athlete_id),
        activity_id=str(activity.id),
    )

    return ActivityUploadResponse(
        activity=ActivityResponse.model_validate(activity),
        task_id=uuid.UUID(int=job << 96),
        ingestion_status="pending",
    )


@activity_router.get(
    "/{athlete_id}/activities",
    response_model=ActivityListResponse,
)
async def list_activities(
    athlete_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    repository: ActivityRepository = Depends(build_activity_repository),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    from_date: Optional[date] = Query(default=None),
    to_date: Optional[date] = Query(default=None),
) -> ActivityListResponse:
    """Return activities for the athlete, newest first."""
    activities = await repository.list_for_athlete(
        athlete_id=athlete_id,
        limit=limit,
        offset=offset,
        from_date=from_date,
        to_date=to_date,
    )
    total = await repository.count_for_athlete(
        athlete_id=athlete_id,
        from_date=from_date,
        to_date=to_date,
    )
    return ActivityListResponse(
        activities=[ActivityResponse.model_validate(a) for a in activities],
        total=total,
    )


@activity_router.get(
    "/{athlete_id}/activities/{activity_id}",
    response_model=ActivityResponse,
)
async def get_activity(
    athlete_id: uuid.UUID,
    activity_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    repository: ActivityRepository = Depends(build_activity_repository),
) -> ActivityResponse:
    """Return a single activity by id, or 404 when missing / cross-athlete."""
    activity = await repository.get_by_id(activity_id)
    if activity is None or activity.athlete_id != athlete_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )
    return ActivityResponse.model_validate(activity)


@activity_router.post(
    "/{athlete_id}/activities/{activity_id}/analyse",
    response_model=PostWorkoutAnalysisResponse,
)
async def post_analyse_activity(
    athlete_id: uuid.UUID,
    activity_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    agent: PostWorkoutAgent = Depends(build_post_workout_agent),
    activities: ActivityRepository = Depends(build_activity_repository),
    coaching_messages: CoachingMessageRepository = Depends(
        build_coaching_message_repository
    ),
    session: AsyncSession = Depends(get_db),
) -> PostWorkoutAnalysisResponse:
    """Trigger the ``PostWorkoutAgent`` for the activity.

    Idempotent — second call returns the existing
    ``CoachingMessage`` without invoking the LLM. Errors:

    * 404 — activity not found or cross-athlete.
    * 503 — LLM service unavailable.
    * 422 — activity has no TwinState (athlete has not completed
      onboarding).
    """
    try:
        coaching_message = await agent.generate(
            athlete_id=athlete_id,
            activity_id=activity_id,
        )
    except ActivityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )
    except PostWorkoutLLMUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Coach service temporarily unavailable.",
        )

    await session.commit()

    activity = await activities.get_by_id(activity_id)
    if activity is None:  # pragma: no cover — defensive
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )

    return PostWorkoutAnalysisResponse(
        activity=ActivityResponse.model_validate(activity),
        coaching_message=CoachingMessageSummary.model_validate(
            coaching_message
        ),
    )


@activity_router.get(
    "/{athlete_id}/activities/{activity_id}/analysis",
    response_model=PostWorkoutAnalysisResponse,
)
async def get_activity_analysis(
    athlete_id: uuid.UUID,
    activity_id: uuid.UUID,
    auth_athlete_id: uuid.UUID = Depends(require_self),
    activities: ActivityRepository = Depends(build_activity_repository),
    coaching_messages: CoachingMessageRepository = Depends(
        build_coaching_message_repository
    ),
) -> PostWorkoutAnalysisResponse:
    """Return the existing post-workout analysis + coaching message.

    404 when no ``post_workout`` ``CoachingMessage`` exists yet —
    callers should use ``POST /analyse`` to trigger generation.
    """
    activity = await activities.get_by_id(activity_id)
    if activity is None or activity.athlete_id != athlete_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Activity {activity_id} not found.",
        )

    message = await coaching_messages.get_by_activity_and_type(
        athlete_id=athlete_id,
        activity_id=activity_id,
        message_type=MessageType.POST_WORKOUT,
    )
    if message is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No post-workout analysis yet for activity {activity_id}. "
                f"Call POST /analyse to generate it."
            ),
        )

    return PostWorkoutAnalysisResponse(
        activity=ActivityResponse.model_validate(activity),
        coaching_message=CoachingMessageSummary.model_validate(message),
    )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _read_upload_bytes(file: UploadFile) -> bytes:
    """Read the full upload body and enforce the size limit.

    Returns the raw bytes that ``stage_upload`` ships to object
    storage and that the ``fit_ingest`` worker later passes to
    ``FitParserService``. The size check protects the parser from
    pathological uploads (the 10MB cap is well above any 4-hour
    HR-only FIT).
    """
    payload = await file.read()
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=(
                f"Uploaded file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)}MB "
                "limit."
            ),
        )
    if len(payload) == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded file is empty.",
        )
    return payload