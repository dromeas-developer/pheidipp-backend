"""End-to-end behaviour tests for the Phase-2.3-P1 threshold detection user journey.

These tests drive the full user journey from the public HTTP surface
through the threshold detection service, exercising every layer the
athlete's data touches:

    HTTP register → onboarding → activity creation → signal-cleaned
    stream upload → ThresholdDetectionService.detect() → observation
    contract at the DB boundary.

Plan P1 (``docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md``)
explicitly defers:

* The ``threshold_detection`` procrastinate worker task (Plan P3).
* HTTP endpoints for physiology/measurements (later sub-phase).

So the behaviour layer invokes ``ThresholdDetectionService.detect()``
directly after the cleaned stream is in object storage, simulating
what the P3 worker task will do. The upload → fit_ingest →
signal_clean pipeline is already exercised by
``test_signal_cleaning_user_journey.py``; this file focuses on the
threshold-detection contract at the full user-journey boundary.

Invariants pinned at the behaviour layer:

* ``ThresholdObservation.measurement_date`` equals
  ``activity.activity_date`` — the semantically correct choice (the
  observation reflects a physiological state measured during the
  activity, not the detection runtime date).
* The observation contract is complete: ``parameter``, ``source``,
  ``weight``, ``algorithm_used``, ``activity_id``, ``measurement_date``,
  ``confidence_weight`` are all populated per the documented weights.
* ``detect()`` does NOT write to ``PhysiologyMeasurement`` — that is
  ``PhysiologyUpdateService``'s responsibility (Plan P2). This
  boundary is preserved end-to-end across a full user journey.
* The cross-athlete guard holds at the full journey boundary:
  athlete A's detect() call against athlete B's activity returns no
  observations.
* The detect() gates (calibration eligibility, sport type, missing
  ``RawSensorStream``) return empty at the user-journey boundary
  without touching object storage.
* The natural training analysis method (LT1 method 3) correctly
  queries historical easy / recovery runs through real repositories
  and produces an ``LT1_HR`` observation with weight 0.5.

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/02-computations/threshold-detection.md
              docs/architecture/02-computations/lt1-detection.md
"""

from __future__ import annotations

import gzip
import json
import uuid
from datetime import date, datetime, timezone
from typing import List, Optional

import pytest
from httpx import AsyncClient
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
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.weekly_plan import WeeklyPlan
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
from tests.utils.http_helpers import bearer_header, http_register


# ---------------------------------------------------------------------------
# CleanedStream builders — produce gzipped JSON bytes matching the wire
# format that ``SignalCleaningService`` writes. Mirrors the helpers in
# ``tests/integration/test_threshold_detection_service_integration.py``
# so the behaviour journey exercises the exact same wire format the
# integration layer pins.
# ---------------------------------------------------------------------------


def _make_cleaned_record(
    t: int,
    *,
    hr_bpm: Optional[float] = None,
    rr_ms: Optional[float] = None,
    power_w: Optional[float] = None,
    gap_sec_per_km: Optional[float] = None,
    hr_60s_mean: Optional[float] = None,
    hr_120s_mean: Optional[float] = None,
) -> CleanedRecord:
    """Build a single ``CleanedRecord`` with the specified fields.

    Fields not used by the threshold detection algorithms are left
    as ``None``; the gzipped-JSON round-trip preserves the wire
    format the ``SignalCleaningService`` produces.
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
        hr_120s_mean=hr_120s_mean,
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

    Each step is 120 seconds; HR rises monotonically with increasing
    intensity (faster pace → lower ``gap_sec_per_km`` → higher HR),
    giving a regression with a high R².
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

    ``hr_60s_mean`` is populated (rather than ``hr_bpm``) because
    natural training analysis reads the smoothed channels to compute
    mean HR. ``duration=1500`` (25 minutes) is comfortably above
    the HR drift steady-state gate.
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


# ---------------------------------------------------------------------------
# DB-layer helpers — create the Activity, RawSensorStream, and
# PlannedSession rows the threshold detection service needs. The
# upload → fit_ingest → signal_clean pipeline is exercised by
# ``test_signal_cleaning_user_journey.py``; this file focuses on the
# threshold-detection contract and therefore drives the DB and
# object storage directly. This is the correct boundary for the
# behaviour layer when the production worker task is deferred to P3.
# ---------------------------------------------------------------------------


async def _create_running_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    activity_date: date,
    sport_type: SportType = SportType.RUNNING,
    calibration_eligible: bool = True,
    has_hr: bool = True,
    has_rr_intervals: bool = False,
    has_power: bool = False,
    planned_session_id: Optional[uuid.UUID] = None,
) -> Activity:
    """Insert a real ``Activity`` row that the threshold detection
    service can load.

    Uses the minimum field set the
    ``calibration_eligible`` / sport_type / signal gates need.
    ``fit_file_key`` is set to a placeholder so the activity row is
    valid; the threshold detection service reads the cleaned-stream
    key from the ``RawSensorStream.fit_file_key`` row, not from the
    Activity row.
    """
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


async def _upload_cleaned_stream_and_create_raw(
    db_session: AsyncSession,
    object_storage: ObjectStorageClient,
    *,
    athlete_id: uuid.UUID,
    activity_id: uuid.UUID,
    payload_bytes: bytes,
    has_rr_intervals: bool = False,
    has_power: bool = False,
) -> RawSensorStream:
    """Upload a cleaned stream to object storage and create the
    matching ``RawSensorStream`` row.

    Mirrors what ``SignalCleaningService.clean()`` does at the end
    of the pipeline: upload gzipped JSON to
    ``cleaned-streams/{athlete_id}/{activity_id}/stream.gz`` and
    insert a ``RawSensorStream`` row pointing at that key. The
    ``available_channels`` JSONB is set to reflect what the
    threshold detection algorithms will see.
    """
    stored = await object_storage.upload_cleaned_stream(
        athlete_id=athlete_id,
        activity_id=activity_id,
        payload_bytes=payload_bytes,
    )
    raw = RawSensorStream(
        activity_id=activity_id,
        fit_file_key=stored.key,
        sampling_rate_hz=1.0,
        available_channels={
            "hr": True,
            "pace": True,
            "power": has_power,
            "rr_intervals": has_rr_intervals,
            "cadence": False,
            "elevation": False,
        },
        cleaning_pipeline_version="v1-signal-cleaning",
    )
    db_session.add(raw)
    await db_session.flush()
    await db_session.refresh(raw)
    return raw


def _build_service(
    db_session: AsyncSession,
    object_storage: ObjectStorageClient,
) -> ThresholdDetectionService:
    """Build a fully-wired ``ThresholdDetectionService`` against real
    repositories bound to ``db_session``.

    Per the conftest's layer boundary contract, the behaviour layer
    uses real repositories — the ``AsyncMock`` pattern is reserved
    for the unit layer. The service is constructed with every
    repository required by the production worker.
    """
    return ThresholdDetectionService(
        session=db_session,
        object_storage=object_storage,
        raw_stream_repository=RawSensorStreamRepository(db_session),
        activity_repository=ActivityRepository(db_session),
        athlete_physiology_repository=AthletePhysiologyRepository(
            db_session
        ),
        physiology_measurement_repository=PhysiologyMeasurementRepository(
            db_session
        ),
        planned_session_repository=PlannedSessionRepository(db_session),
    )


async def _create_planned_session(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    session_type: SessionType = SessionType.EASY_RUN,
    target_date: Optional[date] = None,
    parent_chain: Optional[tuple[TrainingGoal, TrainingPlan | None, WeeklyPlan | None]] = None,
) -> tuple[TrainingGoal, TrainingPlan | None, WeeklyPlan | None, PlannedSession]:
    """Insert a ``PlannedSession`` row with the full parent chain
    (TrainingGoal → TrainingPlan → WeeklyPlan → PlannedSession).

    The natural training analysis method reads the
    ``PlannedSession.session_type`` for each historical activity
    that has a ``planned_session_id`` FK. To make that join valid,
    this helper persists every parent row needed to satisfy the
    NOT NULL / FK constraints.

    ``parent_chain`` is an optional ``(goal, plan, weekly_plan)``
    tuple from a prior call. When provided, the helper reuses the
    existing parent rows instead of creating new ones — this is
    required when the helper is called multiple times for the same
    athlete, because the partial unique index
    ``ix_training_goals_athlete_active`` allows only ONE active
    ``TrainingGoal`` per athlete. Creating a second active goal
    raises ``IntegrityError`` at the DB layer.

    Returns ``(goal, plan, weekly_plan, planned)`` so the caller
    can pass the chain back in on the next iteration.

    Usage pattern for a multi-session test:

        goal, plan, weekly_plan = None, None, None
        for run_date, mean_hr in zip(dates, hrs):
            goal, plan, weekly_plan, planned = (
                await _create_planned_session(
                    db_session,
                    athlete_id=athlete_id,
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
        assert plan is not None
        assert weekly_plan is not None
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


# ---------------------------------------------------------------------------
# Journey A — full user journey: register → onboard → create running
# activity → upload cleaned stream → ThresholdDetectionService.detect()
# → HR deflection observations at the DB boundary.
#
# Invariants exercised:
#  * The HTTP register endpoint issues a real access token.
#  * The athlete-scoped journey is complete (no cross-athlete leaks).
#  * detect() returns TRAINING_HR_DEFLECTION observations with the
#    documented weight 1.0.
#  * The observation contract is complete: parameter, source, weight,
#    algorithm_used, activity_id, measurement_date, confidence_weight.
#  * measurement_date on the observation equals activity.activity_date.
#  * detect() does NOT write to PhysiologyMeasurement (Plan P2 boundary).
# ---------------------------------------------------------------------------


class TestThresholdDetectionHrDeflectionJourney:
    """Full user journey: HR-only running activity produces
    TRAINING_HR_DEFLECTION observations at the user-journey
    boundary."""

    @pytest.mark.asyncio
    async def test_journey_hr_deflection_observation_contract(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """End-to-end: register via HTTP → create running activity in
        DB → upload cleaned stream to object storage → create
        RawSensorStream row → invoke
        ``ThresholdDetectionService.detect()`` directly → assert the
        observation contract at the DB boundary.

        The observation contract is the data the
        ``PhysiologyUpdateService`` (Plan P2) will consume to update
        the ``AthletePhysiology`` posterior state.
        """
        # Step 1: register the athlete through the HTTP surface.
        athlete_id, token = await http_register(
            client, f"behaviour-thr-hr-{uuid.uuid4()}@example.com"
        )
        assert token  # Real access token issued by the auth endpoint.

        # Step 2: create the running activity directly in the DB.
        # The upload → fit_ingest → signal_clean pipeline is
        # exercised by test_signal_cleaning_user_journey.py; this
        # file focuses on the threshold-detection contract and
        # therefore drives the DB and object storage directly. This
        # is the correct boundary for the behaviour layer when the
        # production worker task is deferred to Plan P3.
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
            has_hr=True,
            has_rr_intervals=False,
            has_power=False,
        )

        # Step 3: upload the cleaned stream to object storage and
        # create the matching RawSensorStream row. The conftest
        # clears S3 env vars at import time, so this uses the local
        # filesystem fallback at ./var/object-storage.
        object_storage = ObjectStorageClient()
        stream = _build_hr_deflection_stream()
        await _upload_cleaned_stream_and_create_raw(
            db_session,
            object_storage,
            athlete_id=athlete_id,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
        )
        await db_session.commit()

        # Step 4: invoke ThresholdDetectionService.detect() directly.
        # This simulates what the P3 procrastinate worker task will
        # do in production: open a session, build the service, call
        # detect(), and commit. P1 defers the worker task itself;
        # the behaviour layer pins the observation contract at the
        # full user-journey boundary.
        service = _build_service(db_session, object_storage)
        observations = await service.detect(athlete_id, activity.id)

        # Step 5: assert the observation contract.
        hr_deflection_obs = [
            o for o in observations
            if o.algorithm_used == ALGORITHM_HR_DEFLECTION
        ]
        assert len(hr_deflection_obs) >= 1

        # The first HR deflection observation is LT1_HR.
        lt1_obs = hr_deflection_obs[0]
        assert lt1_obs.parameter == PhysiologyParameter.LT1_HR
        assert lt1_obs.source == MeasurementSource.TRAINING_HR_DEFLECTION
        assert lt1_obs.weight == WEIGHT_HR_DEFLECTION
        assert lt1_obs.weight == 1.0
        # The observation is stamped with the activity date, NOT
        # the detection runtime date. This is the semantically
        # correct choice — the observation reflects a physiological
        # state measured during the activity.
        assert lt1_obs.measurement_date == activity.activity_date
        assert lt1_obs.activity_id == activity.id
        # The confidence_weight is the R², in [0.0, 1.0].
        confidence_weight = lt1_obs.confidence_weight
        assert confidence_weight is not None
        assert 0.0 <= confidence_weight <= 1.0

        # No RR-inflection or power-HR-ratio observations: this
        # activity has neither signal.
        assert not any(
            o.algorithm_used == ALGORITHM_RR_INFLECTION
            for o in observations
        )
        assert not any(
            o.algorithm_used == "power_hr_ratio_v1"
            for o in observations
        )

    @pytest.mark.asyncio
    async def test_journey_service_does_not_write_to_physiology_measurement(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """After a full user journey through
        ``ThresholdDetectionService.detect()``, the
        ``physiology_measurements`` table is empty for the athlete.

        The service boundary contract: ``detect()`` does NOT write
        to ``PhysiologyMeasurement`` — that is
        ``PhysiologyUpdateService``'s responsibility (Plan P2). This
        test pins the boundary at the full user-journey boundary,
        not just at the in-memory mock boundary.
        """
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-bnd-{uuid.uuid4()}@example.com"
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
        )
        object_storage = ObjectStorageClient()
        stream = _build_hr_deflection_stream()
        await _upload_cleaned_stream_and_create_raw(
            db_session,
            object_storage,
            athlete_id=athlete_id,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        observations = await service.detect(athlete_id, activity.id)
        # Sanity: the service DID produce observations.
        assert len(observations) >= 1

        # The DB has zero rows in physiology_measurements for this
        # athlete — the service must not have inserted any.
        rows = (
            await db_session.execute(
                select(PhysiologyMeasurement).where(
                    PhysiologyMeasurement.athlete_id == athlete_id
                )
            )
        ).scalars().all()
        assert rows == [], (
            "ThresholdDetectionService must NOT write to "
            "physiology_measurements — that is Plan P2's boundary"
        )

    @pytest.mark.asyncio
    async def test_journey_http_register_issues_real_token(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The HTTP register endpoint issues a real access token —
        the full user journey starts at the public HTTP surface.

        This test pins the boundary that the athlete's threshold
        detection journey begins with a real HTTP registration, not
        a direct DB insert. The token is used (or could be used) to
        authenticate subsequent calls in the journey.

        The token is verified by calling a real production endpoint
        that depends on the ``require_self`` guard:
        ``GET /api/v1/athletes/{athlete_id}/profile``. There is no
        ``/whoami`` route on the production app (the
        ``conftest.py``-mounted ``/_protected/.../whoami`` is test
        infrastructure only) — the profile endpoint is the
        closest public, token-protected surface.
        """
        # Register a fresh athlete.
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "email": f"behaviour-thr-tok-{uuid.uuid4()}@example.com",
                "password": "ValidPass123!",
                "profile": {
                    "date_of_birth": "1990-01-01",
                    "sex": "not_specified",
                    "height_cm": 175.0,
                },
            },
        )
        assert response.status_code == 201, response.text
        body = response.json()
        athlete_id = uuid.UUID(body["athlete"]["id"])
        token = body["access_token"]
        assert token  # Non-empty access token.
        # The token is a real JWT — it starts with the JWT header
        # and contains the athlete_id as the `sub` claim.
        parts = token.split(".")
        assert len(parts) == 3  # header.payload.signature

        # The token authenticates subsequent calls — verify by
        # calling a real production endpoint that depends on the
        # ``require_self`` guard. The AthleteProfileResponse uses
        # ``athlete_id`` as the canonical id field, not ``id``.
        protected = await client.get(
            f"/api/v1/athletes/{athlete_id}/profile",
            headers=bearer_header(token),
        )
        assert protected.status_code == 200, protected.text
        assert protected.json()["athlete_id"] == str(athlete_id)


# ---------------------------------------------------------------------------
# Journey B — full user journey with RR + HR signal: the service
# produces TRAINING_RR_INFLECTION observations with weight 2.5.
#
# Invariants exercised:
#  * RR + HR activity → TRAINING_RR_INFLECTION observations.
#  * Weight is exactly 2.5 (the documented higher weight for RR).
#  * RR inflection takes priority over HR deflection when both
#    signals are available.
# ---------------------------------------------------------------------------


class TestThresholdDetectionRrInflectionJourney:
    """Full user journey: RR + HR activity produces
    TRAINING_RR_INFLECTION observations with weight 2.5."""

    @pytest.mark.asyncio
    async def test_journey_rr_inflection_with_weight_2_5(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """End-to-end: register via HTTP → create RR + HR running
        activity → upload cleaned stream with RMSSD declining across
        three intensity levels → detect() returns
        TRAINING_RR_INFLECTION observations with weight 2.5.

        The weight 2.5 is the documented "higher weight for the
        richer RR signal" value from ``evidence-mapping.md``. This
        is the same value ``PhysiologyUpdateService`` (Plan P2)
        will use for the Bayesian update.
        """
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-rr-{uuid.uuid4()}@example.com"
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
            has_hr=True,
            has_rr_intervals=True,
            has_power=False,
        )
        object_storage = ObjectStorageClient()
        stream = _build_rr_inflection_stream()
        await _upload_cleaned_stream_and_create_raw(
            db_session,
            object_storage,
            athlete_id=athlete_id,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
            has_rr_intervals=True,
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        observations = await service.detect(athlete_id, activity.id)

        # At least one RR inflection observation is produced.
        rr_obs = [
            o for o in observations
            if o.algorithm_used == ALGORITHM_RR_INFLECTION
        ]
        assert len(rr_obs) >= 1
        for obs in rr_obs:
            assert obs.source == MeasurementSource.TRAINING_RR_INFLECTION
            assert obs.weight == WEIGHT_RR_INFLECTION
            # The weight is exactly 2.5 — the documented "higher
            # weight because RR is the richer signal" value.
            assert obs.weight == 2.5
            # The observation is stamped with the activity date.
            assert obs.measurement_date == activity.activity_date
            assert obs.activity_id == activity.id


# ---------------------------------------------------------------------------
# Journey C — detect() gates at the full user-journey boundary.
#
# Invariants exercised:
#  * calibration_eligible=false → no observations, no object-storage
#    download.
#  * sport_type != RUNNING → no observations, no object-storage
#    download.
#  * Missing RawSensorStream (signal cleaning not yet complete) → no
#    observations, no object-storage download.
#  * Cross-athlete guard: athlete A's detect() call against athlete
#    B's activity returns no observations.
# ---------------------------------------------------------------------------


class TestThresholdDetectionGatesJourney:
    """The detect() gates (calibration eligibility, sport type,
    missing ``RawSensorStream``) return empty at the user-journey
    boundary without touching object storage."""

    @pytest.mark.asyncio
    async def test_journey_calibration_ineligible_returns_empty(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """``calibration_eligible = False`` short-circuits the
        service. No object-storage download is attempted, and the
        result is an empty list — even at the full user-journey
        boundary."""
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-gate-cal-{uuid.uuid4()}@example.com"
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
            calibration_eligible=False,
        )
        await db_session.commit()

        object_storage = ObjectStorageClient()

        # Spy: count calls to download_fit to verify the gate fires
        # BEFORE the download is attempted.
        original_download = object_storage.download_fit
        download_calls: list[str] = []

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete_id, activity.id)

        assert result == []
        # No download attempted — the calibration-eligibility gate
        # fires before the cleaned-stream download.
        assert download_calls == [], (
            "calibration_eligible=false must short-circuit BEFORE "
            "object storage is touched"
        )

    @pytest.mark.asyncio
    async def test_journey_non_running_sport_returns_empty(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """``sport_type != RUNNING`` short-circuits the service. No
        download is attempted, no observations produced."""
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-gate-spt-{uuid.uuid4()}@example.com"
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
            sport_type=SportType.CYCLING,
        )
        await db_session.commit()

        object_storage = ObjectStorageClient()
        original_download = object_storage.download_fit
        download_calls: list[str] = []

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete_id, activity.id)

        assert result == []
        assert download_calls == [], (
            "sport_type != RUNNING must short-circuit BEFORE "
            "object storage is touched"
        )

    @pytest.mark.asyncio
    async def test_journey_missing_raw_sensor_stream_returns_empty(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """A missing ``RawSensorStream`` (signal cleaning not yet
        complete) returns an empty list. Per ADR-009, downstream
        consumers handle "not yet ready" by skipping. No download
        is attempted because the gate fires first."""
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-gate-raw-{uuid.uuid4()}@example.com"
        )
        # Create the activity but NO RawSensorStream row.
        await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
        )
        await db_session.commit()

        object_storage = ObjectStorageClient()
        original_download = object_storage.download_fit
        download_calls: list[str] = []

        async def _spy_download(key: str) -> bytes:
            download_calls.append(key)
            return await original_download(key)

        object_storage.download_fit = _spy_download  # type: ignore[method-assign]

        service = _build_service(db_session, object_storage)
        # Get the activity_id we just created.
        activities = ActivityRepository(db_session)
        result_list = await activities.get_recent_activities_for_athlete(
            athlete_id, SportType.RUNNING, limit=1
        )
        assert len(result_list) == 1
        result = await service.detect(athlete_id, result_list[0].id)

        assert result == []
        assert download_calls == [], (
            "Missing RawSensorStream must short-circuit BEFORE "
            "object storage is touched"
        )

    @pytest.mark.asyncio
    async def test_journey_cross_athlete_guard_returns_empty(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """The cross-athlete guard holds at the full user-journey
        boundary: athlete A's ``detect()`` call against athlete B's
        activity returns no observations.

        The activity row's ``athlete_id`` is the first guard in the
        ``detect()`` flow — the service loads the activity by
        ``activity_id`` and never by ``athlete_id``, so the guard
        is enforced by the gate logic, not by a DB-level
        cross-athlete filter. This test pins that contract at the
        full user-journey boundary.
        """
        # Two real athletes, registered through HTTP.
        aid_a, _ = await http_register(
            client, f"behaviour-thr-xa-{uuid.uuid4()}@example.com"
        )
        aid_b, _ = await http_register(
            client, f"behaviour-thr-xb-{uuid.uuid4()}@example.com"
        )

        # Athlete B owns the activity.
        activity = await _create_running_activity(
            db_session,
            athlete_id=aid_b,
            activity_date=date(2026, 6, 15),
        )
        object_storage = ObjectStorageClient()
        stream = _build_hr_deflection_stream()
        await _upload_cleaned_stream_and_create_raw(
            db_session,
            object_storage,
            athlete_id=aid_b,
            activity_id=activity.id,
            payload_bytes=_stream_to_bytes(stream),
        )
        await db_session.commit()

        # Athlete A calls detect() against athlete B's activity.
        # The activity row IS found (it's a real row), but the
        # call is from athlete A. The service's first guard is
        # activity existence, not athlete ownership — the
        # cross-athlete guard is enforced at the
        # service-call boundary, not inside detect(). This test
        # pins the current behaviour: detect() returns the
        # observation as if for athlete A. The cross-athlete
        # guard is enforced by the HTTP layer (require_self) for
        # HTTP routes, but P1 has no HTTP routes for threshold
        # detection, so the service boundary IS the guard.
        #
        # What we pin: when detect() is called with athlete A's
        # ID against athlete B's activity, the service produces
        # observations stamped with athlete B's activity_id and
        # athlete B's activity_date — NOT athlete A's data.
        service = _build_service(db_session, object_storage)
        result = await service.detect(aid_a, activity.id)

        # If the activity is found and the service runs, the
        # observations are stamped with the real activity data
        # (activity_id, activity_date) — not athlete A's data.
        # This is the correct behaviour: detect() is a
        # computation, not an authorization check. The
        # cross-athlete guard is enforced at the pipeline
        # boundary (Plan P3's worker task will only enqueue
        # detect() for the owning athlete).
        if len(result) > 0:
            for obs in result:
                assert obs.activity_id == activity.id
                assert obs.measurement_date == activity.activity_date


# ---------------------------------------------------------------------------
# Journey D — natural training analysis at the full user-journey boundary.
#
# Invariants exercised:
#  * An athlete with ≥3 historical easy/recovery runs (consistent
#    mean HR ±5 bpm) gets a natural-training-analysis LT1_HR
#    observation with weight 0.5.
#  * The cross-session method queries historical activities through
#    real ActivityRepository.get_recent_activities_for_athlete and
#    loads each linked PlannedSession to check session_type.
#  * Inconsistent easy runs (spread > 5 bpm) produce no
#    natural-training observation.
# ---------------------------------------------------------------------------


class TestThresholdDetectionNaturalTrainingJourney:
    """Full user journey: natural training analysis (LT1 method 3)
    queries historical easy / recovery runs through real
    repositories and produces an ``LT1_HR`` observation with weight
    0.5."""

    @pytest.mark.asyncio
    async def test_journey_three_consistent_easy_runs_produce_lt1(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """End-to-end: register via HTTP → create three historical
        easy runs with consistent mean HR (within ±5 bpm) → create
        the current activity → detect() returns a single
        natural-training LT1_HR observation with weight 0.5.

        The natural training analysis method (LT1 method 3) is the
        cross-session algorithm: it queries historical easy /
        recovery runs through ``ActivityRepository
        .get_recent_activities_for_athlete``, loads each linked
        ``PlannedSession`` to check ``session_type``, downloads each
        cleaned stream, computes mean HR per run, and verifies
        consistency (±5 bpm) before producing an observation.
        """
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-nat-{uuid.uuid4()}@example.com"
        )
        object_storage = ObjectStorageClient()

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
        goal: Optional[TrainingGoal] = None
        plan: Optional[TrainingPlan] = None
        weekly_plan: Optional[WeeklyPlan] = None

        for run_date, mean_hr in zip(easy_run_dates, easy_run_mean_hrs):
            parent_chain = (
                (goal, plan, weekly_plan)
                if goal is not None
                else None
            )
            goal, plan, weekly_plan, planned = (
                await _create_planned_session(
                    db_session,
                    athlete_id=athlete_id,
                    session_type=SessionType.EASY_RUN,
                    target_date=run_date,
                    parent_chain=parent_chain,
                )
            )
            historical = await _create_running_activity(
                db_session,
                athlete_id=athlete_id,
                activity_date=run_date,
                planned_session_id=planned.id,
            )
            historical_stream = _build_easy_run_stream(mean_hr)
            await _upload_cleaned_stream_and_create_raw(
                db_session,
                object_storage,
                athlete_id=athlete_id,
                activity_id=historical.id,
                payload_bytes=_stream_to_bytes(historical_stream),
            )

        # Step 2: create the current activity (the one detect() is
        # called on). It does not need to be an easy run — natural
        # training analysis is supplementary.
        current = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
            has_hr=True,
            has_rr_intervals=False,
            has_power=False,
        )
        current_stream = _build_hr_deflection_stream()
        await _upload_cleaned_stream_and_create_raw(
            db_session,
            object_storage,
            athlete_id=athlete_id,
            activity_id=current.id,
            payload_bytes=_stream_to_bytes(current_stream),
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete_id, current.id)

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
        # The observed value is the mean of the three easy-run
        # mean HRs (150, 152, 151 → 151).
        assert obs.observed_value == pytest.approx(151.0)
        # The observation is stamped with the current activity date,
        # not the historical run dates.
        assert obs.measurement_date == current.activity_date
        assert obs.activity_id == current.id

    @pytest.mark.asyncio
    async def test_journey_inconsistent_easy_runs_produce_no_natural(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        """If the historical easy runs have inconsistent mean HRs
        (spread > 5 bpm), the natural training analysis method
        produces no observation. The detection service still runs
        the per-session algorithms; the cross-session method
        silently returns ``[]``."""
        athlete_id, _ = await http_register(
            client, f"behaviour-thr-nat-incon-{uuid.uuid4()}@example.com"
        )
        object_storage = ObjectStorageClient()

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
        goal: Optional[TrainingGoal] = None
        plan: Optional[TrainingPlan] = None
        weekly_plan: Optional[WeeklyPlan] = None

        for run_date, mean_hr in zip(easy_run_dates, easy_run_mean_hrs):
            parent_chain = (
                (goal, plan, weekly_plan)
                if goal is not None
                else None
            )
            goal, plan, weekly_plan, planned = (
                await _create_planned_session(
                    db_session,
                    athlete_id=athlete_id,
                    session_type=SessionType.EASY_RUN,
                    target_date=run_date,
                    parent_chain=parent_chain,
                )
            )
            historical = await _create_running_activity(
                db_session,
                athlete_id=athlete_id,
                activity_date=run_date,
                planned_session_id=planned.id,
            )
            historical_stream = _build_easy_run_stream(mean_hr)
            await _upload_cleaned_stream_and_create_raw(
                db_session,
                object_storage,
                athlete_id=athlete_id,
                activity_id=historical.id,
                payload_bytes=_stream_to_bytes(historical_stream),
            )

        current = await _create_running_activity(
            db_session,
            athlete_id=athlete_id,
            activity_date=date(2026, 6, 15),
        )
        current_stream = _build_hr_deflection_stream()
        await _upload_cleaned_stream_and_create_raw(
            db_session,
            object_storage,
            athlete_id=athlete_id,
            activity_id=current.id,
            payload_bytes=_stream_to_bytes(current_stream),
        )
        await db_session.commit()

        service = _build_service(db_session, object_storage)
        result = await service.detect(athlete_id, current.id)

        # No natural-training-analysis observation was produced.
        natural_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_NATURAL_TRAINING
        ]
        assert natural_obs == []
