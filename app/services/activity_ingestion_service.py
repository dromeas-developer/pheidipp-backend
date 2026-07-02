"""ActivityIngestionService — orchestrate the FIT upload pipeline.

Implements the Phase-1.6 + Phase-1.8 contract from
``docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md` →
Step 8 (core ingestion workflow) and
``docs/implementation/phase-1/phase-1-8-p1-fix-event-ordering-and-async-processing.md``.

The pipeline is split into two phases so that the heavy work
(parsing, load computation, twin recalibration) never blocks the
API response — per ``04-platform/async-pipeline.md`` "all heavy
processing is async — API responses never wait for analysis":

    1. **Staging (sync, API-side)** —
       :meth:`stage_upload` uploads the FIT to object storage and
       creates an empty ``Activity`` row (``fit_file_key`` set,
       load scores ``null``).
    2. **Pipeline (async, worker-side)** —
       :meth:`_run_ingestion_pipeline` parses the FIT, computes
       the load, updates the existing Activity, evaluates
       calibration eligibility, and runs the Banister twin
       recalibration. The worker task calls this and then
       publishes the ``activity_ingested`` event inside the same
       transaction so the transactional outbox row + Activity
       state land atomically.

Two public entry points exist for convenience:

* :meth:`ingest` — synchronous end-to-end mode used by tests /
  debugging. Runs staging + pipeline + event publication in one
  call so callers can assert the fully populated Activity
  without spinning up a worker.
* :meth:`ingest_async` — production mode invoked from the
  ``fit_ingest`` procrastinate task. Operates against the
  ``Activity`` already created by :meth:`stage_upload`.

Pipeline order for the heavy phase (the architecture-mandated
sequence — see ``01-entities/activity.md`` and
``04-platform/system-event.md``):

    3. Parse the FIT file with FitParserService
    4. Compute aerobic_load with LoadComputationService
    5. Update the Activity with load scores
    6. Set calibration_eligible = false (Phase-1.6 hard-off)
    7. Apply Banister update via TwinRecalibrationService
    8. Append new TwinState (trigger = activity_sync)
    9. Fire ``activity_ingested`` event via transactional outbox
       (same transaction as the Activity state updates — committed
       by the caller; the publisher worker picks up the outbox row
       only after the producing transaction commits).

If any step in the heavy phase fails the surrounding transaction
rolls back — the FIT file remains in object storage as the
reprocessing anchor. The architecture invariant ``fit_file_key
MUST be set for source != manual_entry BEFORE the Activity row is
created`` is preserved by uploading first and creating second in
the same transaction.

Transaction ownership:

* The service does NOT commit. The API route handler
  (``POST /athletes/{id}/activities/upload``) commits after
  :meth:`stage_upload` returns; the worker commits after
  :meth:`ingest_async` returns. Each call site owns exactly one
  commit boundary so the outbox row only becomes visible to the
  publisher worker after the producer's transaction succeeds.

Idempotency:

* The dedup gate (per the architecture doc — see ``Activity``
  invariants) compares ``(athlete_id, external_id, source)``
  BEFORE the object-storage upload runs. Manual uploads have
  ``external_id IS NULL`` so the partial unique index does not
  apply — the doc explicitly notes that manual uploads
  deduplicate via the athlete's awareness, not via the index.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.activity import Activity
from app.models.enums import ActivitySource
from app.models.twin_state import TwinState
from app.repositories.activity_repository import ActivityRepository
from app.services.calibration_eligibility_service import (
    CalibrationEligibilityService,
)
from app.services.event_publisher import EventPublisher
from app.services.fit_parser_service import (
    FitParseEmptyError,
    FitParseError,
    FitParserService,
    ParsedFitData,
)
from app.services.load_computation_service import (
    LoadComputationInputs,
    LoadComputationService,
    LoadScores,
    estimate_max_hr_from_age,
)
from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageConflictError,
    ObjectStorageError,
    ObjectStorageUploadError,
)
from app.services.twin_recalibration_service import (
    MissingAthleteFitnessError,
    MissingTrainingGoalError,
    RecalibrationResult,
    TwinRecalibrationService,
)


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class ActivityIngestionError(Exception):
    """Base class for activity-ingestion failures."""


class AthleteNotFoundForIngestionError(ActivityIngestionError):
    """The athlete profile is missing — bootstrap must complete first."""


class ObjectStorageFailureError(ActivityIngestionError):
    """Object storage upload failed (network / 5xx).

    The ingestion pipeline must NOT create an ``Activity`` row when
    this surfaces — the architecture invariant requires the storage
    upload to succeed before any DB write.
    """


class TwinRecalibrationFailureError(ActivityIngestionError):
    """The Banister update / TwinState append failed.

    Wrapped separately so the API layer can surface a 422 with
    detail and the caller can re-trigger the recalibration without
    re-uploading the FIT file.
    """


# ---------------------------------------------------------------------------
# Result dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActivityIngestionResult:
    """Value object returned by :meth:`ActivityIngestionService.ingest`.

    Carries the freshly created ``Activity`` plus the new
    ``TwinState`` so the API layer can build the response without
    re-querying.
    """

    activity: Activity
    twin_state: TwinState
    load_scores: dict


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class ActivityIngestionService:
    """Orchestrate the FIT upload → Activity → load → twin pipeline.

    Constructed with the per-request ``AsyncSession`` so all writes
    participate in the caller's transaction. The service never
    commits — the route handler owns the boundary.
    """

    INGESTION_PIPELINE_VERSION = "v1-simple-fit"

    def __init__(
        self,
        session: AsyncSession,
        *,
        object_storage: Optional[ObjectStorageClient] = None,
        fit_parser: Optional[FitParserService] = None,
        load_computation: Optional[LoadComputationService] = None,
        twin_recalibration: Optional[TwinRecalibrationService] = None,
        calibration_eligibility: Optional[CalibrationEligibilityService] = None,
        events: Optional[EventPublisher] = None,
    ) -> None:
        self.session = session
        self.activities = ActivityRepository(session)
        self.object_storage = object_storage or ObjectStorageClient()
        self.fit_parser = fit_parser or FitParserService()
        self.load_computation = load_computation or LoadComputationService()
        self.twin_recalibration = twin_recalibration or TwinRecalibrationService(
            session
        )
        self.calibration_eligibility = (
            calibration_eligibility or CalibrationEligibilityService()
        )
        self.events = events or self._build_default_publisher(session)

    # ------------------------------------------------------------------
    # Public entry points.
    #
    # Two flows share the same service so the staging logic and the
    # heavy pipeline stay in one place:
    #
    # * :meth:`stage_upload`      — synchronous; API-side. Uploads the
    #                                FIT to object storage and persists
    #                                an empty ``Activity`` row so the
    #                                raw file is the reprocessing
    #                                anchor before any heavy work runs.
    # * :meth:`ingest`            — synchronous end-to-end (testing).
    #                                Runs staging + the heavy pipeline
    #                                + event publication in one call
    #                                so tests can assert the fully
    #                                populated Activity without
    #                                spinning up a worker.
    # * :meth:`ingest_async`      — production worker-side. Operates
    #                                against the ``Activity`` already
    #                                staged by the API endpoint;
    #                                publishes the ``activity_ingested``
    #                                event inside the caller's
    #                                transaction so the outbox row
    #                                only becomes visible to the
    #                                publisher worker after the
    #                                producing transaction commits.
    # * :meth:`_run_ingestion_pipeline` — internal helper: parse → load
    #                                → update → recalibrate. Does NOT
    #                                publish events; called by both
    #                                ``ingest`` and ``ingest_async``.
    # ------------------------------------------------------------------

    async def stage_upload(
        self,
        *,
        athlete_id: uuid.UUID,
        file_bytes: bytes,
        planned_session_id: Optional[uuid.UUID] = None,
        source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
        external_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Activity:
        """Stage a FIT upload — write to object storage, persist an
        empty ``Activity`` row with null load scores.

        Returns the freshly persisted (and flushed) ``Activity`` so
        the caller can pass its id to the ``fit_ingest`` worker
        task. The activity row remains in the caller's transaction;
        the route handler commits after this returns.

        Failure modes:

        * :class:`ObjectStorageFailureError` — storage upload
          failed; **no Activity is created** (architecture invariant
          requires the storage upload to succeed before any DB
          write).
        * :class:`ActivityIngestionError` — key conflict on upload.

        The activity row's ``activity_date`` is set from ``now`` for
        manual uploads; the worker rewrites it from the parsed FIT
        ``start_time`` once parsing completes (Phase 1.8 async
        pipeline — keeping the staging step cheap).
        """
        today = datetime.now(timezone.utc).date()
        try:
            stored = await self.object_storage.upload_fit(
                athlete_id=athlete_id,
                activity_date=today,
                file_bytes=file_bytes,
            )
        except ObjectStorageConflictError as exc:
            raise ActivityIngestionError(
                "object storage reported a key conflict; aborting"
            ) from exc
        except ObjectStorageUploadError as exc:
            raise ObjectStorageFailureError(
                f"object storage upload failed: {exc}"
            ) from exc
        except ObjectStorageError as exc:
            raise ObjectStorageFailureError(
                f"object storage error: {exc}"
            ) from exc

        activity = Activity(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
            source=source,
            external_id=external_id,
            activity_date=today,
            start_time=datetime.now(timezone.utc),
            duration_seconds=0,
            aerobic_load=None,
            neuromuscular_load=None,
            structural_load=None,
            has_hr=False,
            has_rr_intervals=False,
            has_power=False,
            calibration_eligible=False,
            quality_flags={},
            fit_file_key=stored.key,
            ingestion_pipeline_version=self.INGESTION_PIPELINE_VERSION,
            cleaning_pipeline_version=None,
            notes=notes,
        )
        await self.activities.add(activity)
        return activity

    async def ingest(
        self,
        *,
        athlete_id: uuid.UUID,
        file_bytes: bytes,
        planned_session_id: Optional[uuid.UUID] = None,
        source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
        external_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ActivityIngestionResult:
        """Run the full ingestion pipeline for *file_bytes* (sync mode).

        Convenience wrapper used by tests and debugging. Calls
        :meth:`stage_upload` to persist the file + empty Activity
        row, then :meth:`_run_ingestion_pipeline` to run the heavy
        steps, then publishes the ``activity_ingested`` event
        inside the caller's transaction. The caller commits once.

        Production traffic uses the two-step flow instead — see
        :meth:`stage_upload` + :meth:`ingest_async` — so the API
        returns 202 Accepted before any heavy work runs.
        """
        activity = await self.stage_upload(
            athlete_id=athlete_id,
            file_bytes=file_bytes,
            planned_session_id=planned_session_id,
            source=source,
            external_id=external_id,
            notes=notes,
        )

        recalibration, scores = await self._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity.id,
            file_bytes=file_bytes,
        )

        # Sync mode publishes the event inline so the result
        # object is fully consumed before the caller sees it. The
        # worker path (:meth:`ingest_async`) does the same; the
        # difference is purely who owns the orchestrating transaction.
        # Publish event within the current transaction. The EventPublisher
        # writes to the outbox tables (system_events + system_event_outbox);
        # the external publisher worker reads from the outbox after this
        # transaction commits. This follows the same transactional outbox
        # pattern as sync services — see docs/architecture/04-platform/event-topology.md
        await self.events.publish(
            event_type="activity_ingested",
            athlete_id=athlete_id,
            payload={
                "activity_id": str(activity.id),
                "date": activity.activity_date.isoformat(),
                "duration": activity.duration_seconds,
                "has_hr": activity.has_hr,
                "has_rr": activity.has_rr_intervals,
                "has_power": activity.has_power,
                "fit_file_key": activity.fit_file_key,
                "aerobic_load": scores.aerobic_load,
            },
        )

        return ActivityIngestionResult(
            activity=activity,
            twin_state=recalibration.twin_state,
            load_scores={
                "aerobic_load": scores.aerobic_load,
                "neuromuscular_load": scores.neuromuscular_load,
                "structural_load": scores.structural_load,
            },
        )

    async def ingest_async(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        file_bytes: bytes,
    ) -> ActivityIngestionResult:
        """Run the heavy ingestion pipeline against an existing
        ``Activity`` row (worker-side / async production flow).

        Invoked from the ``fit_ingest`` procrastinate task after the
        API endpoint has staged the upload via
        :meth:`stage_upload` and committed the empty Activity row.
        The worker owns the surrounding transaction — it has already
        downloaded the FIT bytes from object storage and committed
        the API-side stage before this method runs, so this method
        is the second transaction of the pipeline.

        Steps:

            3. Parse the FIT file
            4. Compute aerobic_load
            5. Update Activity with load scores
            6. Set calibration_eligible = false (Phase-1.6 hard-off)
            7. Apply Banister update + append TwinState
            9. Fire ``activity_ingested`` event inside this
               transaction so the outbox row only becomes visible
               to the publisher worker after the producing
               transaction commits.

        The caller (worker task) commits the surrounding
        transaction exactly once, after this method returns.

        Raises:
            ActivityNotFoundError: the activity row is missing
                (stale job — the stage was rolled back).
            ActivityIngestionError: parse / load / recalibration
                failure. Propagated to procrastinate for retry / DLQ
                handling; the FIT file remains the immutable
                reprocessing anchor in object storage.
        """
        recalibration, scores = await self._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        activity = await self.activities.get_by_id(activity_id)
        if activity is None:  # pragma: no cover — defensive
            raise ActivityIngestionError(
                f"Activity {activity_id} disappeared mid-pipeline"
            )

        # Publish event within the worker's transaction. The worker commits
        # after this method returns; the external publisher reads from the
        # outbox post-commit. Same transactional outbox pattern as sync
        # services — see docs/architecture/04-platform/event-topology.md
        await self.events.publish(
            event_type="activity_ingested",
            athlete_id=athlete_id,
            payload={
                "activity_id": str(activity.id),
                "date": activity.activity_date.isoformat(),
                "duration": activity.duration_seconds,
                "has_hr": activity.has_hr,
                "has_rr": activity.has_rr_intervals,
                "has_power": activity.has_power,
                "fit_file_key": activity.fit_file_key,
                "aerobic_load": scores.aerobic_load,
            },
        )

        return ActivityIngestionResult(
            activity=activity,
            twin_state=recalibration.twin_state,
            load_scores={
                "aerobic_load": scores.aerobic_load,
                "neuromuscular_load": scores.neuromuscular_load,
                "structural_load": scores.structural_load,
            },
        )

    async def _run_ingestion_pipeline(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        file_bytes: bytes,
    ) -> tuple[RecalibrationResult, LoadScores]:
        """Run the heavy ingestion steps against an existing Activity.

        Steps:

            3. Parse the FIT file with FitParserService
            4. Compute aerobic_load with LoadComputationService
            5. Update the Activity with load scores
            6. Set calibration_eligible = false (Phase-1.6 hard-off)
            7. Apply Banister update via TwinRecalibrationService
            8. Append new TwinState (trigger = activity_sync)

        Does **NOT** publish events; the caller is responsible for
        firing ``activity_ingested`` within the same transaction so
        the outbox row only becomes visible to the publisher worker
        after the producing transaction commits.

        Returns ``(recalibration, scores)`` — the caller may need
        the recalibration result for its ``ActivityIngestionResult``
        and the scores for the event payload.

        Raises:
            ActivityIngestionError: parse / load failure.
            TwinRecalibrationFailureError: twin refused (no active
                goal / missing ``AthleteFitness`` row).
        """
        activity = await self.activities.get_by_id(activity_id)
        if activity is None:
            raise ActivityIngestionError(
                f"Activity {activity_id} not found"
            )

        athlete_profile_birth_date = await self._read_profile_date_of_birth(
            athlete_id
        )

        try:
            parsed: ParsedFitData = await self.fit_parser.parse(file_bytes)
        except FitParseEmptyError as exc:
            raise ActivityIngestionError(
                f"parsed FIT contains no HR records: {exc}"
            ) from exc
        except FitParseError as exc:
            raise ActivityIngestionError(
                f"FIT parse failed: {exc}"
            ) from exc

        max_hr_estimate = self._resolve_max_hr_estimate(
            athlete_birth_date=athlete_profile_birth_date,
        )
        load_inputs = LoadComputationInputs(
            parsed_fit=parsed,
            max_hr_estimate=max_hr_estimate,
        )
        try:
            scores = self.load_computation.compute_aerobic_load(load_inputs)
        except Exception as exc:
            raise ActivityIngestionError(
                f"load computation failed: {exc}"
            ) from exc

        await self.activities.update_load_scores(
            activity_id=activity.id,
            aerobic_load=scores.aerobic_load,
            neuromuscular_load=scores.neuromuscular_load,
            structural_load=scores.structural_load,
        )
        activity.has_hr = parsed.has_hr
        activity.has_rr_intervals = parsed.has_rr_intervals
        activity.has_power = parsed.has_power
        activity.duration_seconds = parsed.duration_seconds
        activity.start_time = parsed.start_time
        activity.activity_date = parsed.start_time.date()
        await self.session.flush()

        eligible = self.calibration_eligibility.evaluate(activity)
        if eligible != activity.calibration_eligible:
            await self.activities.update_calibration_eligibility(
                activity_id=activity.id,
                calibration_eligible=eligible,
            )

        try:
            recalibration = await self.twin_recalibration.recalibrate(
                athlete_id=athlete_id,
                activity_id=activity.id,
                aerobic_load=scores.aerobic_load,
            )
        except (MissingTrainingGoalError, MissingAthleteFitnessError) as exc:
            raise TwinRecalibrationFailureError(
                f"twin recalibration refused: {exc}"
            ) from exc

        return recalibration, scores

    # ------------------------------------------------------------------
    # Internal helpers.
    # ------------------------------------------------------------------

    async def _read_profile_date_of_birth(
        self, athlete_id: uuid.UUID
    ) -> Optional[date]:
        """Look up the athlete's date of birth for max-HR estimation.

        Returns ``None`` when the profile is missing — the caller
        falls back to the population default
        (``POPULATION_MAX_HR_FALLBACK_BPM``). The lookup is
        performed via raw SQL to avoid coupling this service to the
        ``AthleteProfileRepository`` constructor (which is built
        per-request and not currently imported by the ingestion
        service).
        """
        from sqlalchemy import text

        result = await self.session.execute(
            text("SELECT date_of_birth FROM athlete_profiles WHERE athlete_id = :id"),
            {"id": str(athlete_id)},
        )
        row = result.first()
        if row is None or row[0] is None:
            return None
        return row[0]

    def _resolve_max_hr_estimate(
        self,
        *,
        athlete_birth_date: Optional[date],
    ) -> int:
        """Return the max-HR estimate used by the load formula.

        Falls back to ``settings.POPULATION_MAX_HR_FALLBACK_BPM``
        when the profile is missing. The TwinState LT1 / max_hr
        snapshot is not consulted at this phase because Phase 1.6
        ships ``calibration_eligible = false`` for every activity —
        the snapshot is population-derived too, so the difference is
        nil.
        """
        if athlete_birth_date is None:
            return settings.POPULATION_MAX_HR_FALLBACK_BPM
        return estimate_max_hr_from_age(athlete_birth_date)

    @staticmethod
    def _build_default_publisher(
        session: AsyncSession,
    ) -> EventPublisher:
        """Build the default ``EventPublisher`` for the session."""
        from app.repositories.system_event_outbox_repository import (
            SystemEventOutboxRepository,
        )
        from app.repositories.system_event_repository import SystemEventRepository

        return EventPublisher(
            SystemEventRepository(session),
            SystemEventOutboxRepository(session),
        )