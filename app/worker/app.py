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
from app.services.plan_generation_service import PlanGenerationService



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


@app.task(name="generate_plan")
async def generate_plan(*, athlete_id: str) -> dict[str, Any]:
    """Generate the active TrainingPlan for *athlete_id* on demand.

    Triggered by ``OnboardingService.complete_onboarding`` via
    procrastinate task deferral after the onboarding commit — the
    ``twin_model_ready`` event published there is the semantic
    trigger. The worker opens its own session, calls
    :meth:`PlanGenerationService.generate_plan`, and the service
    commits its own transaction (supersession + insert +
    ``training_plan_generated`` event in one atomic transaction).

    After the plan is committed, the task defers the
    ``generate_first_message`` procrastinate task with the same
    ``athlete_id``. The defer happens AFTER the service call (which
    commits); a first-message-defer failure does not invalidate the
    just-committed plan — the manual retry path is
    ``POST /coach/first-message``.

    Idempotent: ``PlanGenerationService.generate_plan`` supersedes
    any existing active plan for the goal, so re-running for an
    athlete that already has a plan simply replaces it.
    """
    athlete_uuid = uuid.UUID(athlete_id)

    async with AsyncSessionLocal() as session:
        service = PlanGenerationService(session=session)
        result = await service.generate_plan(athlete_id=athlete_uuid)

        # Note: ``generate_plan`` commits its own transaction via
        # ``_persist_full_plan``; the worker does not commit again
        # here. The defer of the first-message task happens after
        # the service call returns so the plan is durably written
        # before we wire the next hop. ``defer`` is sync per the
        # shared ``Psycopg2Connector`` configuration — the
        # ``generate_first_message`` task itself is ``async``.
        generate_first_message.defer(athlete_id=str(athlete_uuid))

        return {
            "training_plan_id": str(result.plan.id),
            "athlete_id": str(athlete_uuid),
        }


@app.task(name="generate_first_message")
async def generate_first_message(*, athlete_id: str) -> dict[str, Any]:
    """Generate the first coach message for *athlete_id* on demand.

    Triggered after plan generation completes (from the
    ``generate_plan`` worker task via task deferral, NOT outbox
    polling). The agent is idempotent — if a first_message already
    exists for this athlete, the agent raises
    :class:`FirstMessageAlreadyExistsError` and the task returns
    successfully (the message was already generated; this is not an
    error).

    LLM failures (proxy down, rate limit, etc.) raise
    :class:`LLMServiceUnavailableError` and the task bubbles the
    exception up so procrastinate applies its retry policy; the
    agent writes a ``GenerationEvent`` with ``success=false`` before
    raising.
    """
    athlete_uuid = uuid.UUID(athlete_id)

    async with AsyncSessionLocal() as session:
        from app.repositories.athlete_preferences_repository import (
            AthletePreferencesRepository,
        )
        from app.repositories.athlete_profile_repository import (
            AthleteProfileRepository,
        )
        from app.repositories.coaching_message_repository import (
            CoachingMessageRepository,
        )
        from app.repositories.generation_event_repository import (
            GenerationEventRepository,
        )
        from app.repositories.training_goal_repository import (
            TrainingGoalRepository,
        )
        from app.repositories.training_plan_repository import (
            TrainingPlanRepository,
        )
        from app.repositories.twin_state_repository import (
            TwinStateRepository,
        )
        from app.services.context_budget_service import (
            ContextBudgetService,
        )
        from app.core.prompt_registry import PromptRegistry
        from app.agents.first_message_agent import (
            FirstMessageAgent,
            FirstMessageAlreadyExistsError,
            LLMServiceUnavailableError,
        )

        twin_states = TwinStateRepository(session)
        training_goals = TrainingGoalRepository(session)
        plans = TrainingPlanRepository(session)

        agent = FirstMessageAgent(
            session=session,
            coaching_messages=CoachingMessageRepository(session),
            generation_events=GenerationEventRepository(session),
            context_budget=ContextBudgetService(
                twin_states=twin_states,
                training_goals=training_goals,
                plans=plans,
                profiles=AthleteProfileRepository(session),
                preferences=AthletePreferencesRepository(session),
            ),
            prompt_registry=PromptRegistry(),
            training_goals=training_goals,
            plans=plans,
            twin_states=twin_states,
        )

        try:
            result = await agent.generate(athlete_id=athlete_uuid)
        except FirstMessageAlreadyExistsError:
            # Idempotent path: another caller (manual retry endpoint,
            # earlier worker run) already created the first message.
            # Treat as success — the system invariant "one first
            # message per athlete per active goal" is intact.
            await session.commit()
            return {
                "coaching_message_id": None,
                "athlete_id": str(athlete_uuid),
                "already_existed": True,
            }
        except LLMServiceUnavailableError:
            # Agent already wrote GenerationEvent(success=False).
            # Roll back so the failure event lands in its own
            # transaction; the manual retry path is
            # ``POST /coach/first-message``.
            await session.rollback()
            raise
        except Exception:
            await session.rollback()
            raise

        await session.commit()

        return {
            "coaching_message_id": str(result.id),
            "athlete_id": str(athlete_uuid),
            "already_existed": False,
        }


OUTBOX_PUBLISHER_BATCH_SIZE = 100


@app.periodic(cron="*/15 * * * * *")
@app.task(name="outbox_publisher")
async def outbox_publisher(timestamp: int) -> dict[str, Any]:
    """Transition ``pending`` outbox rows to ``published``.

    Delegates the publish-side transaction to
    :class:`OutboxPublisherService` per ADR-013; the worker owns
    scheduling, registration, and exception handling only and must
    not construct repositories or open sessions (ADR-001
    ``WorkerIntegration`` / ``RepositoryAccess``).

    The service runs in its own transaction, separate from the
    producing domain transaction. The producing transaction has
    already committed by the time this task observes a row — that
    is what makes the row ``pending`` rather than invisible to a
    different session. The service then flips each row's status to
    ``published`` and stamps ``published_at`` via the existing
    ``SystemEventOutboxRepository.mark_published`` helper.

    No external message bus is involved: the publisher only mutates
    the outbox row. The future bus insertion point is inside
    ``OutboxPublisherService`` — adding a Kafka / NATS / Redis
    client there is a localized change that does not touch the
    worker task.

    Idempotent: ``get_pending`` filters on ``status = 'pending'``, so
    a second run after a successful first run finds an empty queue
    and returns ``{"published_count": 0}`` with no further work.
    """
    from app.services.outbox_publisher_service import OutboxPublisherService

    service = OutboxPublisherService()
    published_count = await service.publish_pending(
        limit=OUTBOX_PUBLISHER_BATCH_SIZE
    )

    return {
        "published_count": published_count,
        "scheduled_at": int(timestamp),
    }