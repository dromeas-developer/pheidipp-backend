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
from app.core.logging_utils import log_event
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

        # Defer threshold detection AFTER the commit (ADR-009
        # decoupling principle). A threshold detection failure
        # must not roll back the already-committed cleaned stream.
        # The defer is swallowed after logging so the cleaning
        # commit still succeeds — Phase 2.4 backfill (Principle
        # #14 reprocessing) covers the missed enqueue.
        #
        # ``threshold_detection`` loads the activity itself to
        # extract ``athlete_id``, so the defer only needs
        # ``activity_id`` — the ``signal_clean`` task signature
        # does not need to change.
        if result.created:
            try:
                threshold_detection.defer(
                    activity_id=activity_id,
                )
            except Exception as exc:  # pragma: no cover — defensive swallow
                log_event(
                    event="threshold_detection.enqueue.failure",
                    activity_id=activity_id,
                    outcome="failed",
                    error=str(exc),
                )

        return {
            "activity_id": str(activity_uuid),
            "raw_sensor_stream_id": (
                str(result.raw_sensor_stream_id)
                if result.raw_sensor_stream_id is not None
                else None
            ),
            "created": bool(result.created),
        }


@app.task(name="threshold_detection")
async def threshold_detection(*, activity_id: str) -> dict[str, Any]:
    """Orchestrate the full threshold detection → physiology update →
    twin recalibration pipeline in a single transaction.

    Dispatched by the ``signal_clean`` worker task after its commit
    (per ADR-009's decoupling principle). The task owns one
    transaction — all writes land atomically:

        * ``AthletePhysiology`` posterior mutation (P2)
        * ``PhysiologyMeasurement`` audit rows (P2)
        * ``TwinState`` calibration snapshot (P3)
        * Outbox events: ``physiology_updated`` (P2) →
          ``twin_recalibrated`` (P3) → ``twin_confidence_upgraded``
          (P3, only on upgrade)

    Steps (one transaction owned by this task — single commit
    boundary):

        1. Open ``AsyncSessionLocal``.
        2. Load the ``Activity`` row to obtain ``athlete_id`` (the
           defer only carries ``activity_id``; the task resolves
           the athlete here so the ``signal_clean`` signature
           stays unchanged).
        3. Construct :class:`ThresholdDetectionService` with the
           per-task session and a :class:`PlannedSessionRepository`
           — the repository is REQUIRED for the LT1 natural
           training analysis algorithm (method 3) to run. Without
           it, easy-run HR patterns never produce LT1 observations.
        4. Construct :class:`PhysiologyUpdateService` and
           :class:`TwinRecalibrationService` with the shared
           session.
        5. Call ``threshold_service.detect(athlete_id, activity_id)``.
           If the observations list is empty, commit and return
           early — no threshold signal in this session is not an
           error.
        6. Call ``physiology_service.apply_observations(athlete_id,
           observations)``. If ``shifted_parameters`` is empty,
           commit and return early — the posterior did not shift
           > 1 unit, so no recalibration is needed and the
           ``physiology_updated`` event was not fired by P2.
        7. Call ``twin_service.recalibrate_for_calibration(
           athlete_id, activity_id, physiology_result)``.
        8. Commit the session exactly once.

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
        activity_id: UUID string of the Activity to process. The
            owning ``athlete_id`` is resolved from the loaded
            Activity row inside the task body — the defer from
            ``signal_clean`` only carries ``activity_id`` per the
            plan's Implementation Clarifications.

    Returns:
        ``{"activity_id": str, "twin_state_id": str | None,
        "observations_count": int, "shifted": bool,
        "confidence_upgraded": bool}``. ``twin_state_id`` is
        ``None`` on the early-return paths (no observations, or
        no parameters shifted); ``shifted`` mirrors whether the
        posterior shifted > 1 unit; ``confidence_upgraded``
        mirrors whether the calibration TwinState's
        ``confidence_level`` increased relative to the previous
        TwinState.

    Raises:
        MissingTrainingGoalError / MissingAthleteFitnessError:
            propagated to procrastinate for retry / DLQ handling.
    """
    from app.services.threshold_detection_service import (
        ThresholdDetectionService,
    )
    from app.services.physiology_update_service import (
        PhysiologyUpdateService,
    )
    from app.services.twin_recalibration_service import (
        TwinRecalibrationService,
    )
    from app.services.object_storage_client import ObjectStorageClient
    from app.repositories.activity_repository import ActivityRepository
    from app.repositories.raw_sensor_stream_repository import (
        RawSensorStreamRepository,
    )
    from app.repositories.athlete_physiology_repository import (
        AthletePhysiologyRepository,
    )
    from app.repositories.physiology_measurement_repository import (
        PhysiologyMeasurementRepository,
    )
    from app.repositories.planned_session_repository import (
        PlannedSessionRepository,
    )

    activity_uuid = uuid.UUID(activity_id)

    async with AsyncSessionLocal() as session:
        # Resolve the activity to confirm it exists before running
        # the pipeline. The ``signal_clean`` defer carries only
        # ``activity_id``; the athlete is loaded here so the
        # ``signal_clean`` task signature stays unchanged.
        activities = ActivityRepository(session)
        activity = await activities.get_by_id(activity_uuid)
        if activity is None:
            raise ActivityIngestionError(
                f"Activity {activity_id} not found"
            )

        # Extract ``athlete_id`` from the loaded activity row —
        # the task signature only carries ``activity_id`` per the
        # plan's Implementation Clarifications.
        athlete_uuid = activity.athlete_id

        threshold_service = ThresholdDetectionService(
            session=session,
            object_storage=ObjectStorageClient(),
            raw_stream_repository=RawSensorStreamRepository(session),
            activity_repository=activities,
            athlete_physiology_repository=AthletePhysiologyRepository(
                session
            ),
            physiology_measurement_repository=(
                PhysiologyMeasurementRepository(session)
            ),
            # REQUIRED for LT1 natural training analysis (method 3)
            # — without this, easy-run HR patterns never produce
            # LT1 observations.
            planned_session_repository=PlannedSessionRepository(session),
        )
        physiology_service = PhysiologyUpdateService(session)
        twin_service = TwinRecalibrationService(session)

        observations = await threshold_service.detect(
            athlete_id=athlete_uuid,
            activity_id=activity_uuid,
        )

        if not observations:
            await session.commit()
            return {
                "activity_id": activity_id,
                "twin_state_id": None,
                "observations_count": 0,
                "shifted": False,
                "confidence_upgraded": False,
            }

        update_result = await physiology_service.apply_observations(
            athlete_id=athlete_uuid,
            observations=observations,
        )

        if not update_result.shifted_parameters:
            await session.commit()
            return {
                "activity_id": activity_id,
                "twin_state_id": None,
                "observations_count": len(observations),
                "shifted": False,
                "confidence_upgraded": False,
            }

        recalibration = await twin_service.recalibrate_for_calibration(
            athlete_id=athlete_uuid,
            activity_id=activity_uuid,
            physiology_result=update_result,
        )

        await session.commit()

        return {
            "activity_id": activity_id,
            "twin_state_id": str(recalibration.twin_state.id),
            "observations_count": len(observations),
            "shifted": True,
            "confidence_upgraded": recalibration.confidence_upgraded,
        }