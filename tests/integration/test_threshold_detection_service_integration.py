"""Integration tests for ``ThresholdDetectionService`` — end-to-end service ↔ real DB ↔ real object-storage contract.

The unit tests in ``tests/unit/test_threshold_detection_service.py``
exercise the service surface with ``AsyncMock``-backed repositories
and a stubbed ``ObjectStorageClient``, so they only prove the
service's branching logic is correct. This integration layer
exercises the *real* test database and the *real*
``ObjectStorageClient`` (in local-fallback mode — the conftest
clears the S3 environment variables at import time) so the full
service ↔ repository ↔ object-storage ↔ cleaned-stream-deserialisation
contract is verified end-to-end.

The per-session algorithms (HR deflection, RR inflection, power-to-HR
ratio) and the LT1 passive inference methods (natural training
analysis, HR drift, HR recovery) all consume the same in-memory
``CleanedStream`` shape; the unit tests already cover their numerical
behaviour. This integration layer focuses on the cross-cutting
concerns that the unit tests cannot cover:

* The cleaned stream is deserialised from the gzipped JSON that the
  ``SignalCleaningService`` upload path produced — i.e. the
  threshold detection service can consume the exact bytes the
  cleaning service wrote. This pins the wire format.
* Gate behaviour (calibration eligibility, sport type, missing
  ``RawSensorStream``) is verified at the persistence boundary, not
  just at the in-memory mock boundary. The service never touches
  object storage when an early gate fires.
* The service does NOT write to ``PhysiologyMeasurement`` — that is
  ``PhysiologyUpdateService``'s responsibility (Plan P2). This
  boundary is a hard contract; the integration test pins it at the
  DB level.
* ``measurement_date`` on the produced observations is
  ``activity.activity_date`` — not the detection runtime date. This
  is the semantically correct choice (the observation reflects a
  physiological state measured during the activity).
* The natural training analysis method (cross-session) correctly
  queries historical easy / recovery runs through real repositories
  and downloads their cleaned streams from real object storage.

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/02-computations/threshold-detection.md
              docs/architecture/02-computations/lt1-detection.md
"""

from __future__ import annotations

import gzip
import json
import uuid
from datetime import date, datetime, timezone
from typing import Iterable, List, Optional
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import (
    ActivitySource,
    MeasurementSource,
    PhysiologyParameter,
    SessionType,
    SportType,
)
from app.models.physiology_measurement import PhysiologyMeasurement
from app.models.planned_session import PlannedSession
from app.models.raw_sensor_stream import RawSensorStream
from app.repositories.activity_repository import ActivityRepository
from app.repositories.athlete_physiology_repository import (
    AthletePhysiologyRepository,
)
from app.repositories.physiology_measurement_repository import (
    PhysiologyMeasurementRepository,
)
from app.repositories.planned_session_repository import (
    PlannedSessionRepository,
)
from app.repositories.raw_sensor_stream_repository import (
    RawSensorStreamRepository,
)
from app.services.object_storage_client import ObjectStorageClient
from app.services.signal_cleaning_service import (
    AvailableChannels,
    CleanedRecord,
    CleanedStream,
)
from app.services.threshold_detection_service import (
    ALGORITHM_HR_DEFLECTION,
    ALGORITHM_NATURAL_TRAINING,
    ALGORITHM_RR_INFLECTION,
    ThresholdDetectionService,
    WEIGHT_HR_DEFLECTION,
    WEIGHT_LT1_NATURAL_TRAINING,
    WEIGHT_RR_INFLECTION,
)
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers — small focused builders for the test fixtures.
# ---------------------------------------------------------------------------


def _make_cleaned_record(
    t: int,
    *,
    hr_bpm: Optional[float] = None,
    rr_ms: Optional[float] = None,
    power_w: Optional[float] = None,
    gap_sec_per_km: Optional[float] = None,
    hr_60s_mean: Optional[float] = None,
) -> CleanedRecord:
    """Build a single ``CleanedRecord`` with the specified fields.

    The fields used here are the ones the threshold detection
    algorithms actually read; the rest are populated with explicit
    None / placeholder values so the gzipped-JSON round-trip preserves
    the wire format the ``SignalCleaningService`` produces.
    """
    return CleanedRecord(
        t=t,
        hr_bpm=hr_bpm,
        rr_ms=rr_ms,
        power_w=power_w,
        gap_sec_per_km=gap_sec_per_km,
        cadence_rpm=None,
        elevation_m=None,
        grade_pct=None,
        variability_index=None,
        hr_30s_mean=None,
        hr_60s_mean=hr_60s_mean,
        hr_120s_mean=None,
        power_30s_mean=None,
        gap_30s_mean=None,
    )


def _stream_to_bytes(stream: CleanedStream) -> bytes:
    """Serialise a ``CleanedStream`` to gzipped JSON bytes, mirroring
    the production upload path.

    The format must match what ``_parse_cleaned_stream`` reads back:
    gzipped JSON with the ``time_series``, ``sampling_rate_hz`` and
    ``available_channels`` keys. This pins the wire format the
    service depends on.
    """
    payload = {
        "time_series": [
            {
                "t": r.t,
                "hr_bpm": r.hr_bpm,
                "rr_ms": r.rr_ms,
                "power_w": r.power_w,
                "gap_sec_per_km": r.gap_sec_per_km,
                "cadence_rpm": r.cadence_rpm,
                "elevation_m": r.elevation_m,
                "grade_pct": r.grade_pct,
                "variability_index": r.variability_index,
                "hr_30s_mean": r.hr_30s_mean,
                "hr_60s_mean": r.hr_60s_mean,
                "hr_120s_mean": r.hr_120s_mean,
                "power_30s_mean": r.power_30s_mean,
                "gap_30s_mean": r.gap_30s_mean,
            }
            for r in stream.time_series
        ],
        "sampling_rate_hz": stream.sampling_rate_hz,
        "available_channels": stream.available_channels.to_dict(),
    }
    return gzip.compress(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    )


def _build_hr_deflection_stream() -> CleanedStream:
    """Four clean intensity steps with a strong linear HR-intensity
    relationship — HR deflection should detect LT1 and LT2.

    Each step is 120 seconds (well above the algorithm's
    intra-bin-count noise floor); HR rises monotonically with
    increasing intensity (faster pace → lower ``gap_sec_per_km``
    → higher HR), giving a regression with a high R².
    """
    records: List[CleanedRecord] = []
    for t in range(120):
        records.append(_make_cleaned_record(
            t, hr_bpm=120.0, gap_sec_per_km=360.0,
        ))
    for t in range(120, 240):
        records.append(_make_cleaned_record(
            t, hr_bpm=140.0, gap_sec_per_km=330.0,
        ))
    for t in range(240, 360):
        records.append(_make_cleaned_record(
            t, hr_bpm=160.0, gap_sec_per_km=300.0,
        ))
    for t in range(360, 480):
        records.append(_make_cleaned_record(
            t, hr_bpm=180.0, gap_sec_per_km=270.0,
        ))
    return CleanedStream(
        time_series=records,
        sampling_rate_hz=1.0,
        available_channels=AvailableChannels(
            hr=True, rr_intervals=False, power=False, pace=True,
            cadence=False, elevation=False,
        ),
    )


def _build_rr_inflection_stream() -> CleanedStream:
    """Three intensity levels, each ≥10 minutes (well above the
    8-minute gate), with RMSSD declining across levels. RR
    inflection should fire on this stream."""
    records: List[CleanedRecord] = []
    # Level 1 — easy, stable RR (~1000 ms).
    for t in range(600):
        records.append(_make_cleaned_record(
            t, hr_bpm=130.0, rr_ms=1000.0, gap_sec_per_km=360.0,
        ))
    # Level 2 — moderate, RMSSD drops (oscillating around 800 ms).
    for t in range(600, 1200):
        rr = 800.0 if t % 2 == 0 else 820.0
        records.append(_make_cleaned_record(
            t, hr_bpm=150.0, rr_ms=rr, gap_sec_per_km=330.0,
        ))
    # Level 3 — hard, RMSSD drops further (oscillating around 600 ms).
    for t in range(1200, 1800):
        rr = 600.0 if t % 2 == 0 else 700.0
        records.append(_make_cleaned_record(
            t, hr_bpm=170.0, rr_ms=rr, gap_sec_per_km=300.0,
        ))
    return CleanedStream(
        time_series=records,
        sampling_rate_hz=1.0,
        available_channels=AvailableChannels(
            hr=True, rr_intervals=True, power=False, pace=True,
            cadence=False, elevation=False,
        ),
    )


def _build_easy_run_stream(mean_hr: float, duration: int = 1500) -> CleanedStream:
    """Steady-state easy run stream — flat HR, slow pace, used as
    the input to the natural training analysis method.

    ``duration=1500`` (25 minutes) is comfortably above the HR drift
    steady-state gate. ``hr_60s_mean`` is populated (rather than
    ``hr_bpm``) because natural training analysis reads the smoothed
    channels to compute mean HR.
    """
    records: List[CleanedRecord] = []
    for t in range(duration):
        records.append(_make_cleaned_record(
            t,
            hr_bpm=mean_hr,
            gap_sec_per_km=400.0,
            hr_60s_mean=mean_hr,
        ))
    return CleanedStream(
        time_series=records,
        sampling_rate_hz=1.0,
        available_channels=AvailableChannels(
            hr=True, rr_intervals=False, power=False, pace=True,
            cadence=False, elevation=False,
        ),
    )


def _build_real_object_storage() -> ObjectStorageClient:
    """Build a real ``ObjectStorageClient`` configured for the local
    fallback. The conftest clears S3 env vars at import time, so a
    fresh ``ObjectStorageClient`` always uses the local filesystem at
    ``./var/object-storage``."""
    return ObjectStorageClient()


async def _upload_cleaned_stream(
    object_storage: ObjectStorageClient,
    *,
    athlete_id: uuid.UUID,
    activity_id: uuid.UUID,
    payload_bytes: bytes,
) -> str:
    """Upload a cleaned stream via the real ``upload_cleaned_stream``
    path. Returns the object key.

    The key is deterministic
    (``cleaned-streams/{athlete_id}/{activity_id}/stream.gz``) so
    the test can build a ``RawSensorStream`` row whose
    ``fit_file_key`` matches what the upload produced.
    """
    stored = await object_storage.upload_cleaned_stream(
        athlete_id=athlete_id,
        activity_id=activity_id,
        payload_bytes=payload_bytes,
    )
    return stored.key


async def _create_running_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    activity_date: date = date(2026, 6, 15),
    sport_type: SportType = SportType.RUNNING,
    calibration_eligible: bool = True,
    has_hr: bool = True,
    has_rr_intervals: bool = False,
    has_power: bool = False,
    planned_session_id: Optional[uuid.UUID] = None,
) -> Activity:
    """Insert a real ``Activity`` row that the threshold detection
    service can load. The values are the minimum the
    ``calibration_eligible`` / sport_type / signal gates need."""
    activity = Activity(
        athlete_id=athlete_id,
        source=ActivitySource.MANUAL_UPLOAD,
        external_id=None,
        activity_date=activity_date,
        start_time=datetime(
            activity_date.year, activity_date.month, activity_date.day,
            8, 0, tzinfo=timezone.utc,
        ),
        duration_seconds=600,
        aerobic_load=85.0,
        has_hr=has_hr,
        has_rr_intervals=has_rr_intervals,
        has_power=has_power,
        has_gps=True,
        sport_type=sport_type,
        calibration_eligible=calibration_eligible,
        quality_flags={},
        fit_file_key="fit-files/test/uploaded.fit",
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version="v1-signal-cleaning",
        planned_session_id=planned_session_id,
    )
    db_session.add(activity)
    await db_session.flush()
    await db_session.refresh(activity)
    return activity


async def _create_raw_sensor_stream(
    db_session: AsyncSession,
    *,
    activity_id: uuid.UUID,
    fit_file_key: str,
) -> RawSensorStream:
    """Insert a real ``RawSensorStream`` row whose ``fit_file_key``
    is the cleaned-stream object key. The threshold detection
    service will load this row to find the cleaned stream."""
    raw = RawSensorStream(
        activity_id=activity_id,
        fit_file_key=fit_file_key,
        sampling_rate_hz=1.0,
        available_channels={"hr": True, "pace": True, "power": False,
                             "rr_intervals": False, "cadence": False,
                             "elevation": False},
        cleaning_pipeline_version="v1-signal-cleaning",
    )
    db_session.add(raw)
    await db_session.flush()
    await db_session.refresh(raw)
    return raw


async def _create_planned_session(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    session_type: SessionType = SessionType.EASY_RUN,
    target_date: Optional[date] = None,
    parent_chain: Optional[tuple] = None,
) -> tuple:
    """Insert a ``PlannedSession`` row with the full parent chain
    (TrainingGoal → TrainingPlan → WeeklyPlan → PlannedSession).

    The natural training analysis method reads the
    ``PlannedSession.session_type`` for each historical activity
    that has a ``planned_session_id`` FK. To make that join
    valid, this helper persists every parent row needed to satisfy
    the NOT NULL / FK constraints.

    ``parent_chain`` is an optional ``(goal, plan, weekly_plan)``
    tuple from a prior call. When provided, the helper reuses the
    existing parent rows instead of creating new ones — this is
    required when the helper is called multiple times for the same
    athlete, because the partial unique index
    ``ix_training_goals_athlete_active`` allows only ONE active
    ``TrainingGoal`` per athlete. Creating a second active goal
    raises ``IntegrityError`` at the DB layer.

    Usage pattern for a multi-session test:

        goal, plan, weekly_plan = None, None, None
        for run_date, mean_hr in zip(dates, hrs):
            goal, plan, weekly_plan, planned = (
                await _create_planned_session(
                    db_session,
                    athlete_id=athlete.id,
                    target_date=run_date,
                    parent_chain=(
                        (goal, plan, weekly_plan)
                        if goal is not None else None
                    ),
                )
            )
    """
    from app.models.enums import (
        PhaseLabel,
        PlannedSessionStatus,
        SessionPriority,
        SessionSlot,
        TrainingGoalStatus,
        TrainingPlanStatus,
        WeeklyPlanStatus,
    )
    from app.models.training_goal import TrainingGoal
    from app.models.training_plan import TrainingPlan
    from app.models.weekly_plan import WeeklyPlan

    if target_date is None:
        target_date = date(2026, 6, 15)

    if parent_chain is not None:
        # Reuse the parent chain from a prior call. The same
        # TrainingGoal / TrainingPlan / WeeklyPlan covers every
        # PlannedSession in the test — production code does the
        # same (one active goal, one plan, one weekly plan, many
        # planned sessions).
        goal, plan, weekly_plan = parent_chain
    else:
        # Build the chain: TrainingGoal → TrainingPlan →
        # WeeklyPlan. Each row's NOT NULL columns are populated.
        goal = TrainingGoal(
            athlete_id=athlete_id,
            goal_type="race_event",
            goal_event_type="marathon",
            goal_event_name="Test Marathon",
            goal_event_date=target_date,
            weekly_volume_hours=6.0,
            weekly_volume_km=40.0,
            fitness_level=3,
            status=TrainingGoalStatus.ACTIVE,
        )
        db_session.add(goal)
        await db_session.flush()
        await db_session.refresh(goal)

        plan = TrainingPlan(
            training_goal_id=goal.id,
            status=TrainingPlanStatus.ACTIVE,
            phases_summary=[],
            phase_definitions=[],
            weekly_distributions=[],
            checkpoint_schedule=[],
        )
        db_session.add(plan)
        await db_session.flush()
        await db_session.refresh(plan)

        weekly_plan = WeeklyPlan(
            # NOTE: WeeklyPlan has no `athlete_id` column. The
            # athlete is reached through `training_plan_id →
            # TrainingPlan → athlete_id`.
            training_plan_id=plan.id,
            week_number=1,
            week_starts_at=target_date,
            week_ends_at=target_date,
            adjusted_intent={},
            status=WeeklyPlanStatus.ACTIVE,
        )
        db_session.add(weekly_plan)
        await db_session.flush()
        await db_session.refresh(weekly_plan)

    planned = PlannedSession(
        weekly_plan_id=weekly_plan.id,
        training_plan_id=plan.id,
        # NOTE: PlannedSession has no `athlete_id` column. The
        # athlete is reached through `weekly_plan_id → WeeklyPlan
        # → training_plan_id → TrainingPlan → athlete_id`.
        target_date=target_date,
        week_number=1,
        phase_label=PhaseLabel.AEROBIC_BASE,
        session_type=session_type,
        intent_description="Test easy run",
        approximate_duration_minutes=45,
        status=PlannedSessionStatus.SCHEDULED,
        session_priority=SessionPriority.PRIMARY,
        session_slot=SessionSlot.AM,
        is_suggested=False,
    )
    db_session.add(planned)
    await db_session.flush()
    await db_session.refresh(planned)
    return goal, plan, weekly_plan, planned


def _build_service(
    db_session: AsyncSession,
    object_storage: ObjectStorageClient,
) -> ThresholdDetectionService:
    """Build a fully-wired ``ThresholdDetectionService`` against real
    repositories bound to ``db_session``.

    Per the conftest's layer boundary contract, the integration
    layer uses real repositories — the ``AsyncMock`` pattern is
    reserved for the unit layer. The service is constructed with
    every repository required by the production worker.
    """
    raw_repo = RawSensorStreamRepository(db_session)
    activity_repo = ActivityRepository(db_session)
    athlete_physiology_repo = AthletePhysiologyRepository(db_session)
    physiology_measurement_repo = PhysiologyMeasurementRepository(db_session)
    planned_session_repo = PlannedSessionRepository(db_session)
    return ThresholdDetectionService(
        session=db_session,
        object_storage=object_storage,
        raw_stream_repository=raw_repo,
        activity_repository=activity_repo,
        athlete_physiology_repository=athlete_physiology_repo,
        physiology_measurement_repository=physiology_measurement_repo,
        planned_session_repository=planned_session_repo,
    )


def _observation_summary(observations: list) -> List[dict]:
    """Reduce a list of ``ThresholdObservation`` to a comparable
    list of dicts. Used to assert on the result of ``detect()``
    without depending on dataclass equality semantics."""
    return [
        {
            "parameter": obs.parameter,
            "source": obs.source,
            "weight": obs.weight,
            "algorithm": obs.algorithm_used,
            "activity_id": obs.activity_id,
            "measurement_date": obs.measurement_date,
        }
        for obs in observations
    ]


# ---------------------------------------------------------------------------
# Test: end-to-end happy path — HR-only stream produces HR deflection.
# ---------------------------------------------------------------------------


class TestDetectEndToEndHrDeflection:
    """An HR-only running activity with a clean four-step stream
    produces ``TRAINING_HR_DEFLECTION`` observations at the
    service-observation boundary."""

    @pytest.mark.asyncio
    async def test_hr_only_running_activity_produces_hr_deflection(
        self, db_session: AsyncSession
    ) -> None:
        """End-to-end: the service loads the Activity, loads the
        ``RawSensorStream``, downloads the cleaned stream from object
        storage, deserialises it, runs HR deflection, and returns two
        observations (LT1_HR + LT2_HR) with source
        ``TRAINING_HR_DEFLECTION`` and weight 1.0."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            has_hr=True,
            has_rr_intervals=False,
            has_power=False,
        )
        stream = _build_hr_deflection_stream()
        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=activity.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, activity.id)

        # HR deflection should produce at least an LT1_HR observation
        # and (depending on the algorithm) an LT2_HR observation.
        hr_deflection_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_HR_DEFLECTION
        ]
        assert len(hr_deflection_obs) >= 1
        # First deflection observation is LT1_HR.
        assert hr_deflection_obs[0].parameter == PhysiologyParameter.LT1_HR
        # The source and weight are the documented contract values.
        for obs in hr_deflection_obs:
            assert obs.source == MeasurementSource.TRAINING_HR_DEFLECTION
            assert obs.weight == WEIGHT_HR_DEFLECTION
        # The observation is stamped with the activity date, not
        # the detection runtime date.
        assert hr_deflection_obs[0].measurement_date == activity.activity_date
        assert hr_deflection_obs[0].activity_id == activity.id
        # The confidence_weight is the R², in [0.0, 1.0].
        confidence_weight = hr_deflection_obs[0].confidence_weight
        assert confidence_weight is not None
        assert 0.0 <= confidence_weight <= 1.0

        # No RR-inflection / power-HR-ratio observations: this
        # activity has neither signal.
        assert not any(
            o.algorithm_used == ALGORITHM_RR_INFLECTION for o in result
        )

    @pytest.mark.asyncio
    async def test_detect_does_not_write_to_physiology_measurement(
        self, db_session: AsyncSession
    ) -> None:
        """The threshold detection service does NOT write to the
        ``physiology_measurements`` table — that is
        ``PhysiologyUpdateService``'s responsibility (Plan P2).

        The integration layer pins this contract at the DB level:
        after ``detect()`` returns, the
        ``physiology_measurements`` table is empty for the athlete.
        """
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        activity = await _create_running_activity(
            db_session, athlete_id=athlete.id
        )
        stream = _build_hr_deflection_stream()
        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=activity.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, activity.id)
        # Sanity: the service DID produce observations.
        assert len(result) >= 1

        # The DB has zero rows in physiology_measurements for this
        # athlete — the service must not have inserted any.
        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert rows == []


# ---------------------------------------------------------------------------
# Test: end-to-end happy path — RR + HR stream produces RR inflection.
# ---------------------------------------------------------------------------


class TestDetectEndToEndRrInflection:
    """An RR + HR activity with a clean three-level stream produces
    ``TRAINING_RR_INFLECTION`` observations at the
    service-observation boundary."""

    @pytest.mark.asyncio
    async def test_rr_and_hr_produces_rr_inflection_with_weight_2_5(
        self, db_session: AsyncSession
    ) -> None:
        """End-to-end: the service downloads the cleaned stream,
        runs RR inflection, and returns observations with source
        ``TRAINING_RR_INFLECTION`` and weight 2.5 (the documented
        higher weight for the richer RR signal)."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            has_hr=True,
            has_rr_intervals=True,
            has_power=False,
        )
        stream = _build_rr_inflection_stream()
        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=activity.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, activity.id)

        # At least one RR inflection observation is produced.
        rr_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_RR_INFLECTION
        ]
        assert len(rr_obs) >= 1
        for obs in rr_obs:
            assert obs.source == MeasurementSource.TRAINING_RR_INFLECTION
            assert obs.weight == WEIGHT_RR_INFLECTION
            # The weight is exactly 2.5 — the documented "higher
            # weight because RR is the richer signal" value.
            assert obs.weight == 2.5
            assert obs.measurement_date == activity.activity_date


# ---------------------------------------------------------------------------
# Test: gates at the persistence boundary.
# ---------------------------------------------------------------------------


class TestDetectGatesAtPersistenceBoundary:
    """The detect() gates (calibration eligibility, sport type,
    missing ``RawSensorStream``) return ``[]`` at the service
    boundary. The integration layer pins this against the real
    database: the service does NOT touch object storage when an
    early gate fires, and no observations are produced."""

    @pytest.mark.asyncio
    async def test_calibration_ineligible_activity_returns_empty(
        self, db_session: AsyncSession
    ) -> None:
        """``calibration_eligible = False`` short-circuits the
        service. The download is never attempted (no object-storage
        call), and the result is an empty list."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        # Spy: count calls to download_fit to verify the gate fires
        # BEFORE the download is attempted.
        original_download = object_storage.download_fit
        download_calls: list[str] = []

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            calibration_eligible=False,
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, activity.id)

        assert result == []
        # No download attempted — the calibration-eligibility gate
        # fires before the cleaned-stream download.
        assert download_calls == []

    @pytest.mark.asyncio
    async def test_non_running_sport_returns_empty(
        self, db_session: AsyncSession
    ) -> None:
        """``sport_type != RUNNING`` short-circuits the service. No
        download is attempted, no observations produced."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        download_calls: list[str] = []
        original_download = object_storage.download_fit

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            sport_type=SportType.CYCLING,
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, activity.id)

        assert result == []
        assert download_calls == []

    @pytest.mark.asyncio
    async def test_missing_raw_sensor_stream_returns_empty(
        self, db_session: AsyncSession
    ) -> None:
        """A missing ``RawSensorStream`` (signal cleaning not yet
        complete) returns an empty list. Per ADR-009, downstream
        consumers handle "not yet ready" by skipping. No download
        is attempted because the gate fires first."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        download_calls: list[str] = []
        original_download = object_storage.download_fit

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        activity = await _create_running_activity(
            db_session, athlete_id=athlete.id
        )
        # Note: NO RawSensorStream row created.
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, activity.id)

        assert result == []
        assert download_calls == []

    @pytest.mark.asyncio
    async def test_missing_activity_returns_empty(
        self, db_session: AsyncSession
    ) -> None:
        """A missing activity row returns an empty list — the first
        guard in the detect() flow. No download attempted."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        download_calls: list[str] = []
        original_download = object_storage.download_fit

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, uuid.uuid4())

        assert result == []
        assert download_calls == []


# ---------------------------------------------------------------------------
# Test: cross-session natural training analysis end-to-end.
# ---------------------------------------------------------------------------


class TestDetectNaturalTrainingAnalysisEndToEnd:
    """The natural training analysis method (LT1 method 3) queries
    historical easy / recovery runs through real repositories and
    downloads their cleaned streams from real object storage.

    The integration layer exercises the cross-session path
    end-to-end:

    1. The current activity is any calibration-eligible running
       activity.
    2. The athlete has at least three historical easy / recovery
       runs, each linked to a ``PlannedSession`` with
       ``session_type = EASY_RUN`` (or ``RECOVERY_RUN``).
    3. Each historical run has a real ``RawSensorStream`` whose
       cleaned stream is uploaded to object storage with a flat
       HR profile.
    4. The detect() call must:
       a. Query ``ActivityRepository.get_recent_activities_for_athlete``
          and find the historical activities.
       b. Load each linked ``PlannedSession`` and check
          ``session_type``.
       c. Download each cleaned stream from object storage.
       d. Compute mean HR for each run.
       e. Verify consistency (±5 bpm).
       f. Produce one ``LT1_HR`` observation with source
          ``TRAINING_HR_DEFLECTION`` and weight
          ``WEIGHT_LT1_NATURAL_TRAINING`` (0.5).
    """

    @pytest.mark.asyncio
    async def test_three_consistent_easy_runs_produce_lt1_observation(
        self, db_session: AsyncSession
    ) -> None:
        """Three historical easy runs with consistent mean HR
        (±5 bpm) produce a single LT1_HR observation with weight
        0.5 — the natural training analysis method's documented
        output."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()

        # Step 1: create three historical easy runs with consistent
        # mean HR (within ±5 bpm of each other).
        easy_run_dates = [
            date(2026, 6, 8),
            date(2026, 6, 10),
            date(2026, 6, 12),
        ]
        easy_run_mean_hrs = [150.0, 152.0, 151.0]  # spread = 2 bpm

        # Track the parent chain across loop iterations so the
        # helper reuses the same TrainingGoal / TrainingPlan /
        # WeeklyPlan (the partial unique index
        # ``ix_training_goals_athlete_active`` allows only ONE
        # active goal per athlete).
        goal: Optional[object] = None
        plan: Optional[object] = None
        weekly_plan: Optional[object] = None

        for run_date, mean_hr in zip(easy_run_dates, easy_run_mean_hrs):
            parent_chain = (
                (goal, plan, weekly_plan)
                if goal is not None
                else None
            )
            goal, plan, weekly_plan, planned = (
                await _create_planned_session(
                    db_session,
                    athlete_id=athlete.id,
                    session_type=SessionType.EASY_RUN,
                    target_date=run_date,
                    parent_chain=parent_chain,
                )
            )
            historical = await _create_running_activity(
                db_session,
                athlete_id=athlete.id,
                activity_date=run_date,
                planned_session_id=planned.id,
            )
            historical_stream = _build_easy_run_stream(mean_hr)
            cleaned_key = await _upload_cleaned_stream(
                object_storage,
                athlete_id=athlete.id,
                activity_id=historical.id,
                payload_bytes=_stream_to_bytes(historical_stream),
            )
            await _create_raw_sensor_stream(
                db_session,
                activity_id=historical.id,
                fit_file_key=cleaned_key,
            )

        # Step 2: create the current activity (the one detect() is
        # called on). It does not need to be an easy run — natural
        # training analysis is supplementary.
        current = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
            has_hr=True,
            has_rr_intervals=False,
            has_power=False,
        )
        current_stream = _build_hr_deflection_stream()
        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=current.id,
            payload_bytes=_stream_to_bytes(current_stream),
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=current.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, current.id)

        # The natural-training-analysis observation is the LT1_HR
        # one with algorithm_used=ALGORITHM_NATURAL_TRAINING and
        # weight=0.5.
        natural_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_NATURAL_TRAINING
        ]
        assert len(natural_obs) == 1
        obs = natural_obs[0]
        assert obs.parameter == PhysiologyParameter.LT1_HR
        assert obs.source == MeasurementSource.TRAINING_HR_DEFLECTION
        assert obs.weight == WEIGHT_LT1_NATURAL_TRAINING
        assert obs.weight == 0.5
        # The observed value is the median of the three easy-run
        # mean HRs (150, 151, 152 → 151).
        assert obs.observed_value == pytest.approx(151.0)
        # The observation is stamped with the current activity date,
        # not the historical run dates.
        assert obs.measurement_date == current.activity_date
        assert obs.activity_id == current.id

    @pytest.mark.asyncio
    async def test_inconsistent_easy_run_hrs_produce_no_natural_observation(
        self, db_session: AsyncSession
    ) -> None:
        """If the historical easy runs have inconsistent mean HRs
        (spread > 5 bpm), the natural training analysis method
        produces no observation. The detection service still runs
        the per-session algorithms; the cross-session method
        silently returns ``[]``."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()

        # Three easy runs with mean HRs spread well beyond the
        # ±5 bpm consistency threshold
        # (``EASY_RUN_HR_TOLERANCE_BPM``). The algorithm checks
        # ``abs(hr - median_hr) > 5.0`` — a strict greater-than —
        # so the spread must exceed 5 bpm from the median for the
        # consistency filter to fire. With median 145, values
        # [130, 145, 165] give max deviation 20 bpm, which is
        # unambiguously inconsistent.
        easy_run_dates = [
            date(2026, 6, 8),
            date(2026, 6, 10),
            date(2026, 6, 12),
        ]
        easy_run_mean_hrs = [130.0, 145.0, 165.0]  # spread = 35 bpm

        # Track the parent chain across loop iterations so the
        # helper reuses the same TrainingGoal / TrainingPlan /
        # WeeklyPlan (the partial unique index
        # ``ix_training_goals_athlete_active`` allows only ONE
        # active goal per athlete).
        goal: Optional[object] = None
        plan: Optional[object] = None
        weekly_plan: Optional[object] = None

        for run_date, mean_hr in zip(easy_run_dates, easy_run_mean_hrs):
            parent_chain = (
                (goal, plan, weekly_plan)
                if goal is not None
                else None
            )
            goal, plan, weekly_plan, planned = (
                await _create_planned_session(
                    db_session,
                    athlete_id=athlete.id,
                    session_type=SessionType.EASY_RUN,
                    target_date=run_date,
                    parent_chain=parent_chain,
                )
            )
            historical = await _create_running_activity(
                db_session,
                athlete_id=athlete.id,
                activity_date=run_date,
                planned_session_id=planned.id,
            )
            historical_stream = _build_easy_run_stream(mean_hr)
            cleaned_key = await _upload_cleaned_stream(
                object_storage,
                athlete_id=athlete.id,
                activity_id=historical.id,
                payload_bytes=_stream_to_bytes(historical_stream),
            )
            await _create_raw_sensor_stream(
                db_session,
                activity_id=historical.id,
                fit_file_key=cleaned_key,
            )

        current = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        current_stream = _build_hr_deflection_stream()
        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=current.id,
            payload_bytes=_stream_to_bytes(current_stream),
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=current.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete.id, current.id)

        # No natural-training-analysis observation was produced —
        # the per-session algorithms still fire.
        natural_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_NATURAL_TRAINING
        ]
        assert natural_obs == []


# ---------------------------------------------------------------------------
# Test: cleaned-stream wire format — round-trip fidelity.
# ---------------------------------------------------------------------------


class TestCleanedStreamWireFormatRoundTrip:
    """The integration layer pins the wire format: the bytes the
    service reads back from object storage must be exactly the
    bytes the cleaning service wrote, and the service must
    deserialise them into a ``CleanedStream`` that preserves the
    data fidelity needed for threshold detection.

    If the ``_parse_cleaned_stream`` function and the serialisation
    format drift out of sync, the service raises
    ``ThresholdDetectionError``. The integration test exercises the
    full round-trip — bytes uploaded to object storage are the
    bytes the service downloads and parses."""

    @pytest.mark.asyncio
    async def test_cleaned_stream_round_trips_through_object_storage(
        self, db_session: AsyncSession
    ) -> None:
        """Bytes uploaded to ``upload_cleaned_stream`` are the same
        bytes ``download_fit`` returns. The deserialised stream
        preserves the records and channel flags."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        activity = await _create_running_activity(
            db_session, athlete_id=athlete.id
        )
        stream = _build_hr_deflection_stream()
        original_bytes = _stream_to_bytes(stream)

        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=activity.id,
            payload_bytes=original_bytes,
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=activity.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        # Download the bytes back through the real download path.
        downloaded = await object_storage.download_fit(cleaned_key)
        assert downloaded == original_bytes

        # The service can deserialise the downloaded bytes without
        # raising — the wire format matches.
        service = _build_service(db_session, object_storage)
        # The detect() call exercises the full download +
        # deserialise + algorithm chain.
        result = await service.detect(athlete.id, activity.id)
        # The service returned observations — the deserialisation
        # succeeded and at least one algorithm fired.
        assert len(result) >= 1

    @pytest.mark.asyncio
    async def test_corrupt_cleaned_bytes_raise_threshold_detection_error(
        self, db_session: AsyncSession
    ) -> None:
        """Bytes that are not gzipped JSON raise
        ``ThresholdDetectionError`` so the worker can retry per
        procrastinate backoff. The integration layer pins this
        against the real deserialisation code path."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        activity = await _create_running_activity(
            db_session, athlete_id=athlete.id
        )
        # Upload bytes that are not gzipped JSON.
        cleaned_key = await _upload_cleaned_stream(
            object_storage,
            athlete_id=athlete.id,
            activity_id=activity.id,
            payload_bytes=b"not a gzipped stream",
        )
        await _create_raw_sensor_stream(
            db_session, activity_id=activity.id, fit_file_key=cleaned_key
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        with pytest.raises(Exception) as exc_info:
            await service.detect(athlete.id, activity.id)

        # The exception is a ThresholdDetectionError (or a subclass
        # of it). We use the broad ``Exception`` to remain robust
        # against the production error type's exact name; the
        # message confirms the deserialisation failure.
        from app.services.threshold_detection_service import (
            ThresholdDetectionError,
        )
        assert isinstance(exc_info.value, ThresholdDetectionError)
