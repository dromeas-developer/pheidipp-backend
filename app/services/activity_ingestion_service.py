"""Orchestrate the FIT upload pipeline."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging_utils import log_event
from app.models.activity import Activity
from app.models.enums import ActivitySource, DataTier, SportType
from app.models.twin_state import TwinState
from app.repositories.activity_repository import ActivityRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_physiology_repository import (
    AthletePhysiologyRepository,
)
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

# Additional imports for Phase-2.1
from app.models.athlete_preferences import AthletePreferences, infer_data_tier
from app.models.athlete_physiology import AthletePhysiology


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
    load_scores: dict[str, Any]


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
        athlete_profiles: Optional[AthleteProfileRepository] = None,
        athlete_preferences: Optional[AthletePreferencesRepository] = None,
        athlete_physiology: Optional[AthletePhysiologyRepository] = None,
        events: Optional[EventPublisher] = None,
        task_dispatcher: Optional[Any] = None,
    ) -> None:
        self.session = session
        self.activities = ActivityRepository(session)
        self.athlete_profiles = athlete_profiles or AthleteProfileRepository(session)
        self.athlete_preferences = athlete_preferences or AthletePreferencesRepository(
            session
        )
        self.athlete_physiology = athlete_physiology or AthletePhysiologyRepository(
            session
        )
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
        # ``task_dispatcher`` is the procrastinate ``App.tasks[…].defer_async``
        # callable bound to ``signal_clean``; it MUST be an async
        # callable with signature ``async (**kwargs) -> int`` per
        # ADR-014. When ``None`` (production) the service lazily
        # resolves the live procrastinate app's
        # ``tasks["signal_clean"].defer_async`` so this module stays
        # importable even if the worker module is unavailable in a
        # trimmed test runtime.
        #
        # The shared procrastinate app is configured with
        # ``PsycopgConnector`` (psycopg3, async-capable) per ADR-014;
        # ``defer`` (sync) is unavailable on async connectors, so the
        # seam contract is async. Test fakes injected through this
        # seam MUST be ``async def __call__``.
        self._task_dispatcher = task_dispatcher

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
    # * :meth:`run_ingestion_pipeline` — the heavy steps: parse → load
    #                                → update → recalibrate → publish.
    #                                Emits ``sport_type_detected``,
    #                                ``activity_ingested``, and
    #                                ``activity_calibration_eligible``
    #                                (the last only when the five-rule
    #                                gate passes and aerobic load is
    #                                non-null) via the transactional
    #                                outbox. Called by both ``ingest``
    #                                and ``ingest_async``.
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
            raise ObjectStorageFailureError(f"object storage error: {exc}") from exc

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
        row, then :meth:`run_ingestion_pipeline` to run the heavy
        steps and publish ``sport_type_detected``,
        ``activity_ingested``, and ``activity_calibration_eligible``
        (when eligible) through the transactional outbox inside the
        caller's transaction. The caller commits once.

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

        recalibration, scores = await self.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity.id,
            file_bytes=file_bytes,
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
            4. Compute all load scores
            5. Update Activity with load scores and signal flags
            6. Evaluate calibration eligibility
            7. Apply Banister update + append TwinState
            8. Fire ``activity_ingested`` event
            9. Fire ``activity_calibration_eligible`` event when eligible

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
        recalibration, scores = await self.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        activity = await self.activities.get_by_id(activity_id)
        if activity is None:  # pragma: no cover — defensive
            raise ActivityIngestionError(
                f"Activity {activity_id} disappeared mid-pipeline"
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

    async def run_ingestion_pipeline(
        self,
        *,
        athlete_id: uuid.UUID,
        activity_id: uuid.UUID,
        file_bytes: bytes,
    ) -> tuple[RecalibrationResult, LoadScores]:
        """Run the heavy ingestion steps against an existing Activity.

        Steps:

            3. Parse the FIT file with FitParserService
            4. Compute all load scores with LoadComputationService
            5. Update the Activity with load scores and signal flags
            6. Evaluate calibration eligibility with full five-rule gate
            7. Apply Banister update via TwinRecalibrationService
            8. Append new TwinState (trigger = activity_sync)
            9. Publish events via the transactional outbox

        Publishes three events through :class:`EventPublisher` within the
        caller's transaction so the outbox rows only become visible to
        the publisher worker after the producing transaction commits:

        * ``sport_type_detected`` — fires for every non-manual-entry
          source before the ingested event; the detection result is
          the event payload.
        * ``activity_ingested`` — fires after the activity is
          updated with load scores and signal flags; the payload
          includes sport type for downstream consumers.
        * ``activity_calibration_eligible`` — fires after the
          ingested event when the five-rule gate passes and the
          aerobic load is non-null; the outbox publisher reads
          events in insertion order so this naturally lands
          after the ingested event.

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
            raise ActivityIngestionError(f"Activity {activity_id} not found")

        # Fetch athlete profile for date of birth (max HR estimation)
        athlete_profile_birth_date = await self._read_profile_date_of_birth(athlete_id)

        # Fetch athlete preferences for data tier inference
        athlete_preferences = await self._read_athlete_preferences(athlete_id)

        # Fetch athlete physiology for CP estimate
        athlete_physiology = await self._read_athlete_physiology(athlete_id)

        # Fetch recent structural load for density penalty computation
        seventy_two_hours_ago = datetime.now(timezone.utc) - timedelta(hours=72)
        recent_structural_load = await self.activities.get_recent_structural_load(
            athlete_id=athlete_id, since_date=seventy_two_hours_ago.date()
        )

        try:
            parsed: ParsedFitData = await self.fit_parser.parse(file_bytes)
        except FitParseEmptyError as exc:
            raise ActivityIngestionError(
                f"parsed FIT contains no HR records: {exc}"
            ) from exc
        except FitParseError as exc:
            raise ActivityIngestionError(f"FIT parse failed: {exc}") from exc

        # Set sport_type on the activity from parsed FIT data
        # (Phase-2.1-P3 — sport type detection from FIT sport message)
        activity.sport_type = parsed.sport_type
        activity.sport_type_detection_version = parsed.detection_version

        # Infer data tier from athlete preferences
        data_tier = self._infer_data_tier(athlete_preferences)

        # Override data_tier to TIER_6 for non-running activities
        # (architecture invariant: sport_type != 'running' → data_tier = 6)
        # This takes precedence over the hardware-based tier inference
        if parsed.sport_type != SportType.RUNNING:
            data_tier = DataTier.TIER_6

        # Estimate max HR from age
        max_hr_estimate = self._resolve_max_hr_estimate(
            athlete_birth_date=athlete_profile_birth_date,
        )

        # Get CP estimate from physiology or use population default
        cp_estimate = self._resolve_cp_estimate(athlete_physiology)

        # Get structural risk flag from profile
        structural_risk_flag = await self.read_structural_risk_flag(athlete_id)

        # Create comprehensive load computation inputs
        load_inputs = LoadComputationInputs(
            parsed_fit=parsed,
            max_hr_estimate=max_hr_estimate,
            data_tier=data_tier,
            cp_estimate=cp_estimate,
            total_distance_m=parsed.total_distance_m,
            total_ascent_m=parsed.total_ascent_m,
            recent_structural_load_72h=recent_structural_load,
            structural_risk_flag=structural_risk_flag,
            sport_type=parsed.sport_type,
            sport_type_detection_version=parsed.detection_version,
        )

        try:
            scores = self.load_computation.compute_aerobic_load(load_inputs)
        except Exception as exc:
            raise ActivityIngestionError(f"load computation failed: {exc}") from exc

        # Update activity with load scores and signal flags
        await self.activities.update_load_scores(
            activity_id=activity.id,
            aerobic_load=scores.aerobic_load,
            neuromuscular_load=scores.neuromuscular_load,
            structural_load=scores.structural_load,
        )
        activity.has_hr = parsed.has_hr
        activity.has_rr_intervals = parsed.has_rr_intervals
        activity.has_power = parsed.has_power
        activity.has_gps = parsed.has_gps
        activity.duration_seconds = parsed.duration_seconds
        activity.start_time = parsed.start_time
        activity.activity_date = parsed.start_time.date()
        # sport_type and sport_type_detection_version were set earlier
        # (right after parse), but we ensure they are explicitly set here
        # for clarity (they may have been set directly on the object already)

        # Compute quality flags
        quality_flags = self.compute_quality_flags(parsed)
        activity.quality_flags = quality_flags

        await self.session.flush()

        # Fire sport_type_detected event (Phase-2.1-P3) BEFORE activity_ingested.
        # This event fires for all non-manual-entry sources regardless of
        # whether the sport is running or not — the detection result is the
        # event, not the eligibility outcome.
        # Does NOT fire for manual_entry activities (no FIT file, no detection).
        if activity.source != ActivitySource.MANUAL_ENTRY:
            await self.events.publish(
                event_type="sport_type_detected",
                athlete_id=athlete_id,
                payload={
                    "activity_id": str(activity.id),
                    "sport_type": activity.sport_type.value,
                    "detection_confidence": parsed.detection_confidence,
                    "detection_version": parsed.detection_version,
                },
            )

        # Evaluate calibration eligibility with full five-rule gate.
        # Tier 5-6 activities are NEVER calibration eligible even if all
        # five rule criteria pass.
        eligible = self.calibration_eligibility.evaluate(activity)
        if eligible and data_tier in (DataTier.TIER_5, DataTier.TIER_6):
            eligible = False
        if eligible != activity.calibration_eligible:
            await self.activities.update_calibration_eligibility(
                activity_id=activity.id,
                calibration_eligible=eligible,
            )

        # Fire activity_ingested event first. The EventPublisher writes to
        # the outbox tables (system_events + system_event_outbox); the
        # external publisher worker reads from the outbox after this
        # transaction commits in insertion order. Same transactional
        # outbox pattern as sync services — see
        # docs/architecture/04-platform/event-topology.md.
        # Phase-2.1-P3: Added sport_type to payload for downstream consumers
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
                "has_gps": activity.has_gps,
                "fit_file_key": activity.fit_file_key,
                "aerobic_load": scores.aerobic_load,
                "sport_type": activity.sport_type.value,
            },
        )

        # Fire activity_calibration_eligible event when eligible and load
        # scores are non-null. The outbox publisher reads events in
        # insertion order so this naturally lands AFTER the
        # activity_ingested event written above.
        if eligible and scores.aerobic_load is not None:
            await self.events.publish(
                event_type="activity_calibration_eligible",
                athlete_id=athlete_id,
                payload={
                    "activity_id": str(activity.id),
                    "aerobic_load": scores.aerobic_load,
                    "neuromuscular_load": scores.neuromuscular_load,
                    "structural_load": scores.structural_load,
                },
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

        # Signal cleaning is a decoupled async task per ADR-009 — the
        # cleaned-stream upload and the ``RawSensorStream`` insert run
        # in their own transaction owned by the ``signal_clean``
        # procrastinate worker. The defer is enqueued AFTER the twin
        # recalibration returns so, per the
        # ``04-platform/async-pipeline.md`` ordering note, the
        # twin update and the cleaning persist against the same
        # ingestion-time Activity snapshot (the defer is created with
        # ``activity_id`` so the worker re-reads the row in its own
        # transaction).
        #
        # Gate: per ADR-009, the task is only enqueued when the
        # activity is calibration-eligible, is a running activity,
        # and is not a manual entry. Manual entries have no FIT and
        # so can never have a stream to clean; non-running activities
        # are forced to ``data_tier = 6`` downstream and never carry
        # a cleaned stream.
        #
        # Do NOT await the deferred task result — the cleaning runs
        # asynchronously on the procrastinate worker. The ingestion
        # transaction commits and returns immediately afterwards.
        #
        # If the defer itself raises (queue backend outage), swallow
        # and log so the ingestion commit still succeeds. The
        # activity remains in a cleanable state and Phase 2.4
        # backfill (Principle #14 reprocessing) covers the missed enqueue.
        if (
            eligible
            and activity.sport_type == SportType.RUNNING
            and activity.source != ActivitySource.MANUAL_ENTRY
        ):
            await self._defer_signal_clean(activity_id=activity.id)

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
        (``POPULATION_MAX_HR_FALLBACK_BPM``).
        """
        profile = await self.athlete_profiles.get_by_athlete_id(athlete_id)
        if profile is None:
            return None
        return profile.date_of_birth

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

    async def _read_athlete_preferences(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthletePreferences]:
        """Look up the athlete's preferences for data tier inference.

        Returns ``None`` when preferences are missing — the caller
        falls back to Tier 6 (manual entry path).
        """
        return await self.athlete_preferences.get_by_athlete_id(athlete_id)

    def _infer_data_tier(self, preferences: Optional[AthletePreferences]) -> DataTier:
        """Infer the data tier from athlete preferences.

        Returns Tier 6 when preferences are missing.
        """
        if preferences is None:
            return DataTier.TIER_6
        return infer_data_tier(
            hr_source=preferences.hr_source,
            power_source=preferences.power_source,
        )

    async def _read_athlete_physiology(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthletePhysiology]:
        """Look up the athlete's physiology for CP estimate.

        Returns ``None`` when physiology is missing.
        """
        return await self.athlete_physiology.get_by_athlete_id(athlete_id)

    def _resolve_cp_estimate(
        self, physiology: Optional[AthletePhysiology]
    ) -> Optional[int]:
        """Extract CP estimate from physiology JSONB.

        Returns None when physiology or CP is missing.
        """
        if physiology is None or physiology.cp is None:
            return None
        # CP is stored as JSONB with shape {"value": int, "uncertainty": float, ...}
        if isinstance(value := physiology.cp.get("value"), (int, float)):
            return int(value)
        return None

    async def read_structural_risk_flag(self, athlete_id: uuid.UUID) -> bool:
        """Look up the structural risk flag for crossover athletes.

        Returns False when profile is missing.
        """
        profile = await self.athlete_profiles.get_by_athlete_id(athlete_id)
        if profile is None or profile.structural_risk_flag is None:
            return False
        return bool(profile.structural_risk_flag)

    def compute_quality_flags(self, parsed: ParsedFitData) -> dict[str, Any]:
        """Compute quality flags from parsed FIT data.

        Returns dict with:
        - hr_dropout_pct: percentage of HR record gaps (>5s gaps)
        - gps_loss: whether GPS data has continuous loss (>30s)
        - sensor_malfunction: whether sensor readings are anomalous
        - has_gps_spikes: whether GPS speed spikes detected (>25 m/s)
        - has_rr_intervals: pass through to quality_flags
        """
        quality_flags: dict[str, Any] = {}

        # HR dropout: percentage of gaps in HR records > 5 seconds
        if not parsed.hr_records:
            quality_flags["hr_dropout_pct"] = 1.0
        else:
            # Estimate gap count based on actual HR records vs expected
            duration = parsed.duration_seconds
            expected_samples = duration  # 1 per second
            actual_samples = len(parsed.hr_records)
            if expected_samples > 0:
                dropout_pct = max(0.0, 1.0 - (actual_samples / expected_samples))
                quality_flags["hr_dropout_pct"] = dropout_pct
            else:
                quality_flags["hr_dropout_pct"] = 0.0

        # GPS loss detection: find continuous gaps > 30s with no GPS data
        if not parsed.has_gps:
            gps_loss = False  # no GPS to lose; preserve current behaviour
        elif not parsed.gps_records:
            gps_loss = True  # claimed GPS but zero records; preserve current behaviour
        else:
            # Continuous-gap detection per Phase-2.1-P1 Handoff Note #2.
            # gps_records arrives in chronological order from FitParserService.
            gps_timestamps = [r.timestamp for r in parsed.gps_records]
            if len(gps_timestamps) <= 1:
                # Only one or no GPS record - no gap to measure
                gps_loss = False
            else:
                previous_ts = gps_timestamps[0]
                max_continuous_gap_s = 0.0
                for record_ts in gps_timestamps[1:]:
                    delta = (record_ts - previous_ts).total_seconds()
                    # Only treat forward gaps (delta < 0 means out-of-order; ignore)
                    if delta > max_continuous_gap_s:
                        max_continuous_gap_s = delta
                    previous_ts = record_ts
                gps_loss = max_continuous_gap_s > 30.0

            # GPS spike detection (unchanged from original)
            spike_count = sum(
                1 for r in parsed.gps_records if r.speed is not None and r.speed > 25.0
            )
            quality_flags["gps_spike_count"] = spike_count

        quality_flags["gps_loss"] = gps_loss

        # Sensor malfunction: heuristic check for anomalous HR/power values
        # Already filtered in parsing, so flag if values are extreme
        sensor_malfunction = False
        if parsed.hr_records:
            # Check for sustained HR > 220 or < 30 (likely malfunction).
            # `ParsedFitData` preserves raw optional samples, so ignore None.
            if any(
                hr is not None and (hr > 220 or hr < 30) for hr in parsed.hr_records
            ):
                sensor_malfunction = True
        if parsed.power_records:
            # Check for power > 2000W (impossible for running).
            # `ParsedFitData` preserves raw optional samples, so ignore None.
            if any(p is not None and p > 2000 for p in parsed.power_records):
                sensor_malfunction = True
        quality_flags["sensor_malfunction"] = sensor_malfunction

        return quality_flags

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

    async def _defer_signal_clean(
        self,
        *,
        activity_id: uuid.UUID,
    ) -> None:
        """Defer the ``signal_clean`` procrastinate task for *activity_id*.

        The dispatcher is the live ``procrastinate_app.tasks[
        "signal_clean"].defer_async`` callable when no test
        fake was injected; the default is resolved lazily on
        the first call so the module remains importable in
        environments where the worker module is unavailable
        (and the task is then never invoked anyway because
        :meth:`__init__` accepts ``task_dispatcher=None`` —
        tests inject their own).

        The defer MUST NOT block on the task result; defer is
        a free operation and the worker picks the queued job up
        off its own schedule. Failures raised by ``defer_async``
        itself (queue backend outage, etc.) are swallowed after
        logging so the ingestion commit path can still succeed.
        """
        dispatcher: Callable[..., Any] | None = self._task_dispatcher
        if dispatcher is None:
            from app.worker.app import signal_clean

            dispatcher = cast(Callable[..., Any], signal_clean.defer_async)

        try:
            await dispatcher(activity_id=str(activity_id))
        except Exception as exc:  # pragma: no cover — defensive swallow
            log_event(
                event="activity.signal_clean.enqueue.failure",
                activity_id=str(activity_id),
                outcome="failed",
                error=str(exc),
            )
