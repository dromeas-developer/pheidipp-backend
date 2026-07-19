"""Procrastinate worker app for Phase-1.7 — PostgreSQL-backed task queue."""

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



# SQLAlchemy ``+driver`` suffixes are stripped inside
# ``get_procrastinate_dsn`` so the call site doesn't have to know
# the converter exists. See app.config for the rationale.
app = procrastinate.App(connector=Psycopg2Connector(dsn=get_procrastinate_dsn()))




# Use ``async_task`` for all tasks so they integrate with the async
# event loop without blocking. Procrastinate handles the
# thread/await dispatch internally.


@app.task(name="fit_ingest")
async def fit_ingest(*, activity_id: str, athlete_id: str) -> dict[str, Any]:
    """Ingest a previously uploaded FIT file into the activity pipeline."""
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
    """Recalibrate the Banister twin model after a manual load update."""
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
    """Run the signal-cleaning pipeline for a previously ingested activity."""
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
    """Orchestrate threshold detection, physiology update, and twin recalibration in one transaction."""
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