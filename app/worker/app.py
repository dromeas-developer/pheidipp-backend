"""Procrastinate worker app for Phase-1.7 — PostgreSQL-backed task queue.

Defines async tasks that replace the ARQ/Redis stack. Procrastinate 2.x is
used deliberately with Psycopg2Connector for its psycopg2 compatibility; 
3.x requires a psycopg3 connector and is intentionally not adopted because 
the queue is transitional.

Workers are started via::

    procrastinate --app=app.worker.app worker

The app reads the database URL from the ``PROCRASTINATE_DATABASE_URL``
environment variable (already set in ``.env`` and ``.env.test``).

Task queue invariants (per ``04-platform/async-pipeline.md``):
- All heavy processing is async — FIT parsing, twin recalibration,
  post-workout analysis run in the worker queue.
- API responses never wait for heavy processing.
- The queue backend is decoupled — PostgreSQL-backed at Phase 1.7,
  with a migration path to Redis if queue contention requires it.
"""

from __future__ import annotations

import uuid
from typing import Any

import procrastinate
from procrastinate.contrib.psycopg2 import Psycopg2Connector

from app.config import get_procrastinate_dsn
from app.db.session import AsyncSessionLocal
from app.services.activity_ingestion_service import (
    ActivityIngestionService,
    ActivityIngestionError,
)
from app.services.object_storage_client import ObjectStorageClient

# ---------------------------------------------------------------------------
# Procrastinate App — single shared instance used by the CLI.
# ---------------------------------------------------------------------------

# SQLAlchemy ``+driver`` suffixes are stripped inside
# ``get_procrastinate_dsn`` so the call site doesn't have to know
# the converter exists. See app.config for the rationale.
app = procrastinate.App(connector=Psycopg2Connector(dsn=get_procrastinate_dsn()))


# ---------------------------------------------------------------------------
# Tasks.
# ---------------------------------------------------------------------------

# Use ``async_task`` for all tasks so they integrate with the async
# event loop without blocking. Procrastinate handles the
# thread/await dispatch internally.


@app.task(name="fit_ingest")
async def fit_ingest(*, activity_id: str, athlete_id: str) -> dict[str, Any]:
    """Ingest a previously uploaded FIT file into the activity pipeline.

    Dispatches after the API endpoint has staged the upload
    (``stage_upload`` persisted an empty ``Activity`` row with the
    raw FIT in object storage). The worker:

        1. Opens its own ``AsyncSession`` / transaction.
        2. Reads the persisted ``Activity`` row to obtain
           ``fit_file_key`` (and validates it exists).
        3. Downloads the raw FIT bytes from object storage.
        4. Delegates the heavy parse / load / twin / event pipeline
           to :meth:`ActivityIngestionService.ingest_async`, which
           publishes the ``activity_ingested`` outbox row inside the
           same transaction so the transactional outbox pattern is
           preserved.
        5. Commits the surrounding transaction.

    On success the ``Activity`` row is fully populated with load
    scores; on a parse / load / recalibration failure the
    transaction rolls back, the ``Activity`` row remains in its
    pre-pipeline ``null``-load-scores state, and the FIT file stays
    in object storage as the immutable reprocessing anchor. The
    raised exception is propagated to procrastinate so it can be
    retried up to N times before reaching the DLQ.

    Args:
        activity_id: UUID of the existing Activity row.
        athlete_id: UUID of the owning athlete.

    Returns:
        ``{"activity_id": str, "twin_state_id": str}`` on success.

    Raises:
        ActivityIngestionError: on any pipeline failure after the
            Activity row was created. Propagated to procrastinate
            for retry / DLQ handling.
    """
    athlete_uuid = uuid.UUID(athlete_id)
    activity_uuid = uuid.UUID(activity_id)

    object_storage = ObjectStorageClient()

    async with AsyncSessionLocal() as session:
        from app.repositories.activity_repository import ActivityRepository

        activities = ActivityRepository(session)
        activity = await activities.get_by_id(activity_uuid)

        if activity is None:
            raise ActivityIngestionError(f"Activity {activity_id} not found")

        if activity.fit_file_key is None:
            raise ActivityIngestionError(
                f"Activity {activity_id} has no fit_file_key"
            )

        # Download the raw FIT bytes from object storage so the
        # service can re-parse against the file the API endpoint
        # had previously uploaded (the original upload is the
        # immutable reprocessing anchor).
        file_bytes = await object_storage.download_fit(activity.fit_file_key)

        service = ActivityIngestionService(
            session=session,
            object_storage=object_storage,
        )

        result = await service.ingest_async(
            athlete_id=athlete_uuid,
            activity_id=activity_uuid,
            file_bytes=file_bytes,
        )

        await session.commit()

        return {
            "activity_id": str(result.activity.id),
            "twin_state_id": str(result.twin_state.id),
        }


@app.task()
async def recalibrate_twin(*, athlete_id: str, activity_id: str) -> dict[str, Any]:
    """Recalibrate the Banister twin model after a manual load update.

    Dispatches a targeted Banister update without re-running the full
    FIT parse. Used when a coach or athlete manually adjusts the
    aerobic_load on an existing Activity and the twin model needs to
    reflect the correction.

    Args:
        athlete_id: UUID of the athlete whose twin is being recalibrated.
        activity_id: UUID of the Activity triggering the recalibration.

    Returns:
        ``{"twin_state_id": str, "updated_form": float}`` on success.

    Raises:
        MissingTrainingGoalError / MissingAthleteFitnessError: propagated
            to procrastinate for retry / DLQ handling.
    """
    from app.services.twin_recalibration_service import (
        TwinRecalibrationService,
    )
    from app.repositories.activity_repository import ActivityRepository

    athlete_uuid = uuid.UUID(athlete_id)
    activity_uuid = uuid.UUID(activity_id)

    async with AsyncSessionLocal() as session:
        activities = ActivityRepository(session)
        activity = await activities.get_by_id(activity_uuid)

        if activity is None:
            raise ActivityIngestionError(f"Activity {activity_id} not found")

        aerobic_load = activity.aerobic_load
        if aerobic_load is None:
            raise ActivityIngestionError(
                f"Activity {activity_id} has no aerobic_load"
            )

        twin_service = TwinRecalibrationService(session)
        recalibration = await twin_service.recalibrate(
            athlete_id=athlete_uuid,
            activity_id=activity_uuid,
            aerobic_load=aerobic_load,
        )

        await session.commit()

        return {
            "twin_state_id": str(recalibration.twin_state.id),
            "updated_form": float(recalibration.updated_form),
        }


@app.task(name="signal_clean")
async def signal_clean(*, activity_id: str) -> dict[str, Any]:
    """Run the 7-step signal-cleaning pipeline for a previously
    ingested activity and persist a ``RawSensorStream`` row.

    Dispatched by :class:`ActivityIngestionService` after the
    ingestion transaction commits, when the activity is
    calibration-eligible, is a running activity, and is not a
    manual entry. Decoupled from the ingestion transaction per
    ADR-009 so a cleaning failure does not roll back the
    already-committed ``Activity`` row.

    Steps (one transaction owned by this task — single commit
    boundary):

        1. Open ``AsyncSessionLocal``.
        2. Construct :class:`SignalCleaningService` with the
           per-task session, the process-wide
           :class:`ObjectStorageClient`, the
           :class:`RawSensorStreamRepository`, the
           :class:`ActivityRepository`, and a fresh
           :class:`FitParserService`.
        3. Call ``service.clean(uuid.UUID(activity_id))``.
        4. Commit the session exactly once.

    Retry semantics: procrastinate's default retry policy
    applies — the architecture's load-compute retry semantics
    ("up to 3×, then DLQ") are inherited via the same worker
    app configuration. No retry / timeout decorators are added
    on this task.

    Importability: the task registers on the shared
    ``app.worker.app.app`` procrastinate instance at module
    import time. The body executes no module-level I/O, so
    importing ``app.worker.app`` (e.g. from tests) is safe
    without a DB connection — only the task's invocation
    requires the DB.

    Args:
        activity_id: UUID string of the Activity to clean.

    Returns:
        ``{"activity_id": str, "raw_sensor_stream_id":
        str | None, "created": bool}``. ``raw_sensor_stream_id``
        is ``None`` on the no-op paths (manual entry, already
        cleaned, ineligible); ``created`` mirrors the
        ``CleaningResult.created`` flag.

    Raises:
        SignalCleaningNotFoundError: the activity row is
            missing. Propagated to procrastinate.
        SignalCleaningIneligibleError: a stale queue entry —
            the activity is not calibration-eligible or not
            running. Propagated to procrastinate.
        FitParseError / SignalCleaningError: cleaning
            failure. Propagated to procrastinate for retry /
            DLQ handling per the architecture's load-compute
            retry contract.
    """
    activity_uuid = uuid.UUID(activity_id)

    async with AsyncSessionLocal() as session:
        from app.services.fit_parser_service import FitParserService
        from app.services.object_storage_client import ObjectStorageClient
        from app.services.signal_cleaning_service import (
            SignalCleaningService,
        )
        from app.repositories.activity_repository import (
            ActivityRepository,
        )
        from app.repositories.raw_sensor_stream_repository import (
            RawSensorStreamRepository,
        )

        service = SignalCleaningService(
            session=session,
            object_storage=ObjectStorageClient(),
            raw_stream_repository=RawSensorStreamRepository(session),
            activity_repository=ActivityRepository(session),
            fit_parser=FitParserService(),
        )

        result = await service.clean(activity_uuid)

        await session.commit()

        return {
            "activity_id": str(activity_uuid),
            "raw_sensor_stream_id": (
                str(result.raw_sensor_stream_id)
                if result.raw_sensor_stream_id is not None
                else None
            ),
            "created": bool(result.created),
        }