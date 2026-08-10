"""Activity API surface — five endpoints behind ``require_self``."""

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
from app.core.prompt_registry import PromptRegistry
from app.worker.app import fit_ingest


# Maximum upload size (bytes). 10MB matches the
# ``python-multipart`` default and comfortably holds a 4-hour FIT
# file at 1Hz HR + GPS.
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


activity_router = APIRouter(prefix="/athletes", tags=["activity"])


def build_activity_ingestion_service(
    session: AsyncSession = Depends(get_db),
) -> ActivityIngestionService:
    return ActivityIngestionService(session=session)


def build_post_workout_agent(
    session: AsyncSession = Depends(get_db),
) -> PostWorkoutAgent:
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
    return ActivityRepository(session=session)


def build_coaching_message_repository(
    session: AsyncSession = Depends(get_db),
) -> CoachingMessageRepository:
    return CoachingMessageRepository(session=session)


def _shared_prompt_registry() -> PromptRegistry:
    # Lazy import to avoid a top-level cycle between the activity
    # router and the agent module.
    from app.core.prompt_registry import get_default_prompt_registry

    return get_default_prompt_registry()


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
    service: ActivityIngestionService = Depends(build_activity_ingestion_service),
    session: AsyncSession = Depends(get_db),
) -> ActivityUploadResponse:
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
    # ``defer_async`` returns the job id as an ``int`` (not a
    # ``Job`` object). We promote it to a ``UUID`` here so the
    # response schema's ``task_id: UUID`` field is satisfied.
    # The conversion is lossless and reversible:
    # ``UUID(int=job_id << 96).int >> 96 == job_id``.
    #
    # ``defer_async`` is used because the shared procrastinate
    # app is configured with ``PsycopgConnector`` (psycopg3,
    # async-capable) per ADR-014; ``defer`` (sync) is unavailable
    # on async connectors. The defer operation is a lightweight
    # single-row INSERT into ``procrastinate_jobs`` driven by
    # the connector's own connection pool — independent of the
    # caller's transaction, so the after-commit ordering
    # preserves the durability invariant.
    job = await fit_ingest.defer_async(
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
        coaching_message=CoachingMessageSummary.model_validate(coaching_message),
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


async def _read_upload_bytes(file: UploadFile) -> bytes:
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
