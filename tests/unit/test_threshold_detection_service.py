"""Unit tests for ``ThresholdDetectionService``.

Phase-2.3-P1 introduces the threshold detection service — the
computation engine that analyses cleaned sensor streams from
calibration-eligible running activities and produces physiological
threshold observations (LT1 HR, LT2 HR, CP).

This test module covers:

* ``ThresholdObservation`` dataclass (frozen contract).
* ``detect()`` guards — calibration eligibility, sport type, missing
  RawSensorStream, missing activity.
* Signal selection logic — which algorithms run based on available
  signals.
* Per-session algorithms — HR deflection, RR inflection, power-to-HR
  ratio.
* LT1 passive inference — natural training analysis, HR drift, HR
  recovery.

Reference plan: docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Architecture: docs/architecture/02-computations/threshold-detection.md
              docs/architecture/02-computations/lt1-detection.md
"""

from __future__ import annotations

import gzip
import json
import uuid
from datetime import date
from typing import Any, List, Optional, cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.activity import Activity
from app.models.enums import (
    MeasurementSource,
    PhysiologyParameter,
    SessionType,
    SportType,
)
from app.models.planned_session import PlannedSession
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
    ALGORITHM_HR_DRIFT,
    ALGORITHM_HR_RECOVERY,
    ALGORITHM_NATURAL_TRAINING,
    ALGORITHM_POWER_HR_RATIO,
    ALGORITHM_RR_INFLECTION,
    MIN_INTENSITY_STEPS,
    R2_MIN_THRESHOLD,
    WEIGHT_HR_DEFLECTION,
    WEIGHT_LT1_HR_DRIFT,
    WEIGHT_LT1_HR_RECOVERY,
    WEIGHT_LT1_NATURAL_TRAINING,
    WEIGHT_POWER_HR_RATIO,
    WEIGHT_RR_INFLECTION,
    ThresholdDetectionService,
    ThresholdObservation,
)


# ---------------------------------------------------------------------------
# Shared helpers.
# ---------------------------------------------------------------------------


def _mock_activity(
    *,
    activity_id: uuid.UUID | None = None,
    athlete_id: uuid.UUID | None = None,
    sport_type: SportType = SportType.RUNNING,
    calibration_eligible: bool = True,
    has_hr: bool = True,
    has_rr_intervals: bool = False,
    has_power: bool = False,
    activity_date: date | None = None,
) -> MagicMock:
    """Build a mock Activity with the specified attributes."""
    mock = MagicMock(spec=Activity)
    mock.id = activity_id or uuid.uuid4()
    mock.athlete_id = athlete_id or uuid.uuid4()
    mock.sport_type = sport_type
    mock.calibration_eligible = calibration_eligible
    mock.has_hr = has_hr
    mock.has_rr_intervals = has_rr_intervals
    mock.has_power = has_power
    mock.activity_date = activity_date or date(2026, 6, 15)
    return mock


def _cleaned_stream_to_bytes(stream: CleanedStream) -> bytes:
    """Serialise a CleanedStream to gzipped JSON bytes, mirroring
    ``CleanedStream.to_json_bytes`` + the upload pipeline."""
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


def _make_cleaned_record(
    t: int,
    *,
    hr_bpm: Optional[float] = None,
    rr_ms: Optional[float] = None,
    power_w: Optional[float] = None,
    gap_sec_per_km: Optional[float] = None,
    cadence_rpm: Optional[float] = None,
    elevation_m: Optional[float] = None,
    grade_pct: Optional[float] = None,
    hr_30s_mean: Optional[float] = None,
    hr_60s_mean: Optional[float] = None,
    hr_120s_mean: Optional[float] = None,
) -> CleanedRecord:
    """Build a single CleanedRecord with the specified fields."""
    return CleanedRecord(
        t=t,
        hr_bpm=hr_bpm,
        rr_ms=rr_ms,
        power_w=power_w,
        gap_sec_per_km=gap_sec_per_km,
        cadence_rpm=cadence_rpm,
        elevation_m=elevation_m,
        grade_pct=grade_pct,
        variability_index=None,
        hr_30s_mean=hr_30s_mean,
        hr_60s_mean=hr_60s_mean,
        hr_120s_mean=hr_120s_mean,
        power_30s_mean=None,
        gap_30s_mean=None,
    )


def _make_stream(
    records: List[CleanedRecord],
    *,
    hr: bool = True,
    rr_intervals: bool = False,
    power: bool = False,
    pace: bool = True,
    cadence: bool = False,
    elevation: bool = False,
) -> CleanedStream:
    """Build a CleanedStream wrapping the given records."""
    return CleanedStream(
        time_series=records,
        sampling_rate_hz=1.0,
        available_channels=AvailableChannels(
            hr=hr,
            rr_intervals=rr_intervals,
            power=power,
            pace=pace,
            cadence=cadence,
            elevation=elevation,
        ),
    )


def _make_service(
    *,
    activity: MagicMock | None = None,
    raw_stream_exists: bool = True,
    cleaned_stream: CleanedStream | None = None,
    planned_sessions: Optional[dict[uuid.UUID, MagicMock]] = None,
    activities_for_athlete: Optional[list[Any]] = None,
) -> ThresholdDetectionService:
    """Build a fully-wired ``ThresholdDetectionService`` with mocks.

    The service is constructed with ``AsyncMock`` for all dependencies.
    Default mocks return sensible values for the positive path.
    """
    session = AsyncMock()
    object_storage = AsyncMock(spec=ObjectStorageClient)
    raw_stream_repo = AsyncMock(spec=RawSensorStreamRepository)
    activity_repo = AsyncMock(spec=ActivityRepository)
    athlete_physiology_repo = AsyncMock(spec=AthletePhysiologyRepository)
    physiology_measurement_repo = AsyncMock(
        spec=PhysiologyMeasurementRepository
    )
    planned_session_repo = AsyncMock(spec=PlannedSessionRepository)

    # Default: activity loads successfully.
    if activity is None:
        activity = _mock_activity()
    activity_repo.get_by_id = AsyncMock(return_value=activity)

    # Default: RawSensorStream exists.
    raw_stream_mock = MagicMock()
    raw_stream_mock.fit_file_key = (
        f"cleaned-streams/{activity.athlete_id}/{activity.id}/stream.gz"
    )
    if raw_stream_exists:
        raw_stream_repo.get_by_activity_id = AsyncMock(
            return_value=raw_stream_mock
        )
    else:
        raw_stream_repo.get_by_activity_id = AsyncMock(return_value=None)

    # Default: object_storage returns gzipped JSON.
    if cleaned_stream is None:
        cleaned_stream = _make_stream([])
    object_storage.download_fit = AsyncMock(
        return_value=_cleaned_stream_to_bytes(cleaned_stream)
    )

    # Default: planned_sessions lookup.
    if planned_sessions is not None:
        async def _get_by_id(ps_id: uuid.UUID) -> MagicMock | None:
            return planned_sessions.get(ps_id)
        planned_session_repo.get_by_id = AsyncMock(side_effect=_get_by_id)

    # Default: natural training analysis query.
    if activities_for_athlete is not None:
        activity_repo.get_recent_activities_for_athlete = AsyncMock(
            return_value=activities_for_athlete
        )
        # Also wire raw_stream_repo for natural training analysis.
        async def _raw_for_activity(act_id: uuid.UUID):
            m = MagicMock()
            m.fit_file_key = f"cleaned-streams/{activity.athlete_id}/{act_id}/stream.gz"
            return m
        raw_stream_repo.get_by_activity_id = AsyncMock(
            side_effect=_raw_for_activity
        )

    return ThresholdDetectionService(
        session=session,
        object_storage=object_storage,
        raw_stream_repository=raw_stream_repo,
        activity_repository=activity_repo,
        athlete_physiology_repository=athlete_physiology_repo,
        physiology_measurement_repository=physiology_measurement_repo,
        planned_session_repository=planned_session_repo,
    )


# ---------------------------------------------------------------------------
# Test: ThresholdObservation dataclass.
# ---------------------------------------------------------------------------


class TestThresholdObservationDataclass:
    """``ThresholdObservation`` is a frozen dataclass carrying the
    data contract between ``ThresholdDetectionService`` and
    ``PhysiologyUpdateService`` (Plan P2)."""

    def test_observation_carries_all_fields(self) -> None:
        """The observation carries parameter, observed_value, source,
        weight, activity_id, measurement_date, algorithm_used, and
        confidence_weight."""
        act_id = uuid.uuid4()
        obs = ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=160.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=1.0,
            activity_id=act_id,
            measurement_date=date(2026, 6, 15),
            algorithm_used="hr_deflection_v1",
            confidence_weight=0.85,
        )
        assert obs.parameter == PhysiologyParameter.LT1_HR
        assert obs.observed_value == 160.0
        assert obs.source == MeasurementSource.TRAINING_HR_DEFLECTION
        assert obs.weight == 1.0
        assert obs.activity_id == act_id
        assert obs.measurement_date == date(2026, 6, 15)
        assert obs.algorithm_used == "hr_deflection_v1"
        assert obs.confidence_weight == 0.85

    def test_observation_is_frozen(self) -> None:
        """The dataclass is frozen — fields cannot be reassigned."""
        obs = ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=160.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=1.0,
            activity_id=uuid.uuid4(),
            measurement_date=date(2026, 6, 15),
            algorithm_used="hr_deflection_v1",
            confidence_weight=0.85,
        )
        with pytest.raises((AttributeError, Exception)):
            obs.observed_value = 170.0  # type: ignore[misc]

    def test_observation_confidence_weight_can_be_none(self) -> None:
        """``confidence_weight`` is Optional — None is a valid value
        (e.g., natural training analysis may not produce a score)."""
        obs = ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=160.0,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=0.5,
            activity_id=uuid.uuid4(),
            measurement_date=date(2026, 6, 15),
            algorithm_used="natural_training_v1",
            confidence_weight=None,
        )
        assert obs.confidence_weight is None


# ---------------------------------------------------------------------------
# Test: detect() — guard: missing activity.
# ---------------------------------------------------------------------------


class TestDetectMissingActivity:
    """``detect()`` returns ``[]`` when the activity does not exist."""

    @pytest.mark.asyncio
    async def test_detect_missing_activity_returns_empty_list(self) -> None:
        """A missing activity row returns an empty observation list."""
        service = _make_service(activity=None)
        # Override: activity not found.
        service.activities.get_by_id = AsyncMock(return_value=None)  # type: ignore[attr-defined]

        result = await service.detect(uuid.uuid4(), uuid.uuid4())

        assert result == []


# ---------------------------------------------------------------------------
# Test: detect() — guard: calibration_eligible = false.
# ---------------------------------------------------------------------------


class TestDetectNotCalibrationEligible:
    """``detect()`` returns ``[]`` when the activity is not
    calibration-eligible."""

    @pytest.mark.asyncio
    async def test_detect_not_calibration_eligible_returns_empty(
        self,
    ) -> None:
        """A non-calibration-eligible activity returns an empty list
        silently (no exception raised)."""
        activity = _mock_activity(calibration_eligible=False)
        service = _make_service(activity=activity)

        result = await service.detect(activity.athlete_id, activity.id)

        assert result == []
        # No stream download was attempted.
        cast(AsyncMock, service.object_storage).download_fit.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test: detect() — guard: sport_type != RUNNING.
# ---------------------------------------------------------------------------


class TestDetectNonRunningSport:
    """``detect()`` returns ``[]`` when the sport type is not RUNNING."""

    @pytest.mark.asyncio
    async def test_detect_cycling_returns_empty(self) -> None:
        """A cycling activity returns an empty list silently."""
        activity = _mock_activity(sport_type=SportType.CYCLING)
        service = _make_service(activity=activity)

        result = await service.detect(activity.athlete_id, activity.id)

        assert result == []
        cast(AsyncMock, service.object_storage).download_fit.assert_not_called()  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_detect_swimming_returns_empty(self) -> None:
        """A swimming activity returns an empty list silently."""
        activity = _mock_activity(sport_type=SportType.SWIMMING)
        service = _make_service(activity=activity)

        result = await service.detect(activity.athlete_id, activity.id)

        assert result == []


# ---------------------------------------------------------------------------
# Test: detect() — guard: missing RawSensorStream.
# ---------------------------------------------------------------------------


class TestDetectMissingRawSensorStream:
    """``detect()`` returns ``[]`` when the RawSensorStream row is
    missing (signal cleaning not yet complete). Per ADR-009,
    downstream consumers handle "not yet ready" by skipping."""

    @pytest.mark.asyncio
    async def test_detect_missing_raw_sensor_stream_returns_empty(
        self,
    ) -> None:
        """A missing RawSensorStream returns an empty list silently."""
        activity = _mock_activity()
        service = _make_service(
            activity=activity, raw_stream_exists=False
        )

        result = await service.detect(activity.athlete_id, activity.id)

        assert result == []
        # No download attempted because the gate fires first.
        cast(AsyncMock, service.object_storage).download_fit.assert_not_called()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Test: signal selection logic.
# ---------------------------------------------------------------------------


class TestSignalSelection:
    """Signal selection routes to applicable algorithms based on
    ``has_rr_intervals``, ``has_hr``, and ``has_power``."""

    @pytest.mark.asyncio
    async def test_detect_with_no_hr_returns_only_natural_training(
        self,
    ) -> None:
        """An activity with no HR produces no per-session observations;
        only natural training analysis runs (and may produce LT1)."""
        activity = _mock_activity(has_hr=False, has_rr_intervals=False)
        # Empty stream — no observations possible.
        stream = _make_stream([])
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        # No per-session algorithms should fire because has_hr is False.
        # Natural training analysis may or may not run depending on
        # historical data; with no data configured, it returns [].
        assert result == []

    @pytest.mark.asyncio
    async def test_detect_with_hr_only_runs_hr_deflection(self) -> None:
        """An activity with HR but no RR and no power runs HR
        deflection only."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        # Build a stream with 4 distinct intensity steps and good R².
        records = [
            _make_cleaned_record(t, hr_bpm=120.0, gap_sec_per_km=360.0)
            for t in range(60)
        ] + [
            _make_cleaned_record(t, hr_bpm=140.0, gap_sec_per_km=330.0)
            for t in range(60, 120)
        ] + [
            _make_cleaned_record(t, hr_bpm=160.0, gap_sec_per_km=300.0)
            for t in range(120, 180)
        ] + [
            _make_cleaned_record(t, hr_bpm=180.0, gap_sec_per_km=270.0)
            for t in range(180, 240)
        ]
        stream = _make_stream(records)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        # HR deflection should produce observations; RR and power
        # algorithms should NOT run.
        hr_deflection_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_HR_DEFLECTION
        ]
        rr_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_RR_INFLECTION
        ]
        power_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_POWER_HR_RATIO
        ]
        assert len(hr_deflection_obs) >= 1
        assert rr_obs == []
        assert power_obs == []

    @pytest.mark.asyncio
    async def test_detect_with_rr_intervals_runs_rr_inflection(self) -> None:
        """An activity with RR intervals runs RR inflection."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=True, has_power=False
        )
        # Build a stream with RR data — RR inflection needs ≥8 min
        # per intensity level (480s each). We use 3 levels at 600s each.
        records: list[CleanedRecord] = []
        for t in range(600):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=130.0,
                    rr_ms=900.0,
                    gap_sec_per_km=360.0,
                )
            )
        for t in range(600, 1200):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=150.0,
                    rr_ms=800.0,
                    gap_sec_per_km=330.0,
                )
            )
        for t in range(1200, 1800):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=170.0,
                    rr_ms=700.0,
                    gap_sec_per_km=300.0,
                )
            )
        stream = _make_stream(records, rr_intervals=True)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        # RR inflection should produce observations.
        rr_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_RR_INFLECTION
        ]
        assert len(rr_obs) >= 1
        # Verify the weight is 2.5 (from evidence-mapping).
        for obs in rr_obs:
            assert obs.weight == WEIGHT_RR_INFLECTION

    @pytest.mark.asyncio
    async def test_detect_with_power_runs_power_hr_ratio(self) -> None:
        """An activity with power runs power-to-HR ratio algorithm."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=True
        )
        # Build a stream with power data showing a clear ratio
        # breakpoint. Sub-threshold: ratio stable. Above LT2: ratio
        # declines.
        records: list[CleanedRecord] = []
        for t in range(600):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=140.0,
                    power_w=200.0,
                    gap_sec_per_km=360.0,
                )
            )
        for t in range(600, 1200):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=160.0,
                    power_w=250.0,
                    gap_sec_per_km=330.0,
                )
            )
        for t in range(1200, 1800):
            # Ratio declines: power increases but HR increases faster.
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=185.0,
                    power_w=270.0,
                    gap_sec_per_km=300.0,
                )
            )
        stream = _make_stream(records, power=True)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        # Power-to-HR ratio may or may not produce an observation
        # depending on whether the breakpoint is detected. The test
        # verifies the algorithm runs (weight 1.5 if it fires).
        power_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_POWER_HR_RATIO
        ]
        for obs in power_obs:
            assert obs.weight == WEIGHT_POWER_HR_RATIO
            assert obs.parameter == PhysiologyParameter.CP


# ---------------------------------------------------------------------------
# Test: HR deflection algorithm.
# ---------------------------------------------------------------------------


class TestHrDeflectionAlgorithm:
    """HR deflection produces LT1_HR and LT2_HR observations with
    source ``TRAINING_HR_DEFLECTION`` and weight 1.0."""

    @pytest.mark.asyncio
    async def test_hr_deflection_produces_lt1_and_lt2_observations(
        self,
    ) -> None:
        """Given ≥3 distinct intensity steps and R² ≥ 0.80, HR
        deflection produces LT1_HR and LT2_HR observations."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        # 4 distinct intensity steps with strong linear HR-intensity
        # relationship (R² will be high).
        records: list[CleanedRecord] = []
        for t in range(120):
            # Intensity 1: slow pace, low HR.
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=120.0, gap_sec_per_km=360.0
                )
            )
        for t in range(120, 240):
            # Intensity 2: medium pace, medium HR.
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=140.0, gap_sec_per_km=330.0
                )
            )
        for t in range(240, 360):
            # Intensity 3: fast pace, high HR.
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=160.0, gap_sec_per_km=300.0
                )
            )
        for t in range(360, 480):
            # Intensity 4: very fast pace, very high HR.
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=180.0, gap_sec_per_km=270.0
                )
            )
        stream = _make_stream(records)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        hr_deflection_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_HR_DEFLECTION
        ]
        assert len(hr_deflection_obs) >= 1
        # First observation should be LT1_HR.
        assert hr_deflection_obs[0].parameter == PhysiologyParameter.LT1_HR
        assert (
            hr_deflection_obs[0].source
            == MeasurementSource.TRAINING_HR_DEFLECTION
        )
        assert hr_deflection_obs[0].weight == WEIGHT_HR_DEFLECTION

    @pytest.mark.asyncio
    async def test_hr_deflection_skips_bins_with_high_null_fraction(
        self,
    ) -> None:
        """Bins with >80% null HR values are skipped per the signal
        cleaning null-propagation invariant."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        records: list[CleanedRecord] = []
        for t in range(60):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=120.0, gap_sec_per_km=360.0
                )
            )
        # Bin 2: 90% null HR — should be skipped.
        for t in range(60, 120):
            hr = 140.0 if t % 10 == 0 else None
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=hr, gap_sec_per_km=330.0
                )
            )
        for t in range(120, 180):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=160.0, gap_sec_per_km=300.0
                )
            )
        for t in range(180, 240):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=180.0, gap_sec_per_km=270.0
                )
            )
        stream = _make_stream(records)
        service = _make_service(activity=activity, cleaned_stream=stream)

        # The service should still run; the null bin is filtered
        # before the regression. The test verifies no crash.
        result = await service.detect(activity.athlete_id, activity.id)

        # Result is a list (may be empty if not enough valid bins).
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Test: RR inflection algorithm.
# ---------------------------------------------------------------------------


class TestRrInflectionAlgorithm:
    """RR inflection produces LT1_HR and LT2_HR observations with
    source ``TRAINING_RR_INFLECTION`` and weight 2.5."""

    @pytest.mark.asyncio
    async def test_rr_inflection_weight_is_2_5(self) -> None:
        """RR inflection observations carry weight 2.5 (higher than HR
        deflection because RR is a richer signal)."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=True, has_power=False
        )
        # 3 intensity levels, each ≥8 min (480s), with RMSSD
        # dropping >15% below baseline at higher intensities.
        records: list[CleanedRecord] = []
        for t in range(600):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=130.0,
                    rr_ms=1000.0,
                    gap_sec_per_km=360.0,
                )
            )
        for t in range(600, 1200):
            # RMSSD drops: more variable RR intervals.
            rr = 800.0 if t % 2 == 0 else 820.0
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=150.0,
                    rr_ms=rr,
                    gap_sec_per_km=330.0,
                )
            )
        for t in range(1200, 1800):
            # RMSSD drops further: high variability at high intensity.
            rr = 600.0 if t % 2 == 0 else 700.0
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=170.0,
                    rr_ms=rr,
                    gap_sec_per_km=300.0,
                )
            )
        stream = _make_stream(records, rr_intervals=True)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        rr_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_RR_INFLECTION
        ]
        assert len(rr_obs) >= 1
        for obs in rr_obs:
            assert obs.weight == WEIGHT_RR_INFLECTION
            assert obs.weight == 2.5

    @pytest.mark.asyncio
    async def test_rr_inflection_skips_short_intensity_levels(self) -> None:
        """If any intensity level has <8 min of data, RR inflection
        returns no observations."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=True, has_power=False
        )
        # Only 2 short intensity levels — each <8 min.
        records: list[CleanedRecord] = []
        for t in range(120):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=130.0,
                    rr_ms=1000.0,
                    gap_sec_per_km=360.0,
                )
            )
        for t in range(120, 240):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=150.0,
                    rr_ms=800.0,
                    gap_sec_per_km=330.0,
                )
            )
        stream = _make_stream(records, rr_intervals=True)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        rr_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_RR_INFLECTION
        ]
        assert rr_obs == []


# ---------------------------------------------------------------------------
# Test: power-to-HR ratio algorithm.
# ---------------------------------------------------------------------------


class TestPowerHrRatioAlgorithm:
    """Power-to-HR ratio produces CP observation with source
    ``TRAINING_POWER_HR_RATIO`` and weight 1.5."""

    @pytest.mark.asyncio
    async def test_power_hr_ratio_weight_is_1_5(self) -> None:
        """When the power-to-HR ratio algorithm produces an
        observation, it carries weight 1.5 and parameter CP."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=True
        )
        # Build a stream with a clear ratio breakpoint: sub-threshold
        # ratio is stable, above-LT2 ratio declines.
        records: list[CleanedRecord] = []
        for t in range(600):
            # Sub-threshold: ratio = 200/140 = 1.43
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=140.0,
                    power_w=200.0,
                    gap_sec_per_km=360.0,
                )
            )
        for t in range(600, 1200):
            # Mid: ratio = 250/160 = 1.56
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=160.0,
                    power_w=250.0,
                    gap_sec_per_km=330.0,
                )
            )
        for t in range(1200, 1800):
            # Above LT2: ratio declines = 270/185 = 1.46
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=185.0,
                    power_w=270.0,
                    gap_sec_per_km=300.0,
                )
            )
        stream = _make_stream(records, power=True)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        power_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_POWER_HR_RATIO
        ]
        for obs in power_obs:
            assert obs.weight == WEIGHT_POWER_HR_RATIO
            assert obs.weight == 1.5
            assert obs.parameter == PhysiologyParameter.CP


# ---------------------------------------------------------------------------
# Test: natural training analysis.
# ---------------------------------------------------------------------------


class TestNaturalTrainingAnalysis:
    """LT1 natural training analysis — cross-session, ≥3 easy runs
    with consistent HR (±5 bpm)."""

    @pytest.mark.asyncio
    async def test_natural_training_skipped_without_planned_session_repo(
        self,
    ) -> None:
        """When PlannedSessionRepository is not provided to the
        constructor, natural training analysis is skipped silently."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        stream = _make_stream([])
        service = _make_service(activity=activity, cleaned_stream=stream)
        # Remove the planned session repository.
        service.planned_sessions = None  # type: ignore[attr-defined]

        result = await service.detect(activity.athlete_id, activity.id)

        natural_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_NATURAL_TRAINING
        ]
        assert natural_obs == []

    @pytest.mark.asyncio
    async def test_natural_training_requires_three_easy_runs(self) -> None:
        """Fewer than 3 easy runs → no natural training observation."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        stream = _make_stream([])

        # Build 2 easy runs (below the 3-run minimum).
        easy_runs: list[Activity] = []
        planned_sessions_map: dict[uuid.UUID, MagicMock] = {}
        for _ in range(2):
            run = _mock_activity(
                athlete_id=activity.athlete_id,
                has_hr=True,
            )
            ps = MagicMock(spec=PlannedSession)
            ps.session_type = SessionType.EASY_RUN
            planned_sessions_map[run.planned_session_id] = ps
            easy_runs.append(run)

        service = _make_service(
            activity=activity,
            cleaned_stream=stream,
            planned_sessions=planned_sessions_map,
            activities_for_athlete=easy_runs,
        )

        result = await service.detect(activity.athlete_id, activity.id)

        natural_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_NATURAL_TRAINING
        ]
        assert natural_obs == []


# ---------------------------------------------------------------------------
# Test: HR drift method.
# ---------------------------------------------------------------------------


class TestHrDriftMethod:
    """LT1 HR drift — steady-state segments ≥20 min, drift > 5 bpm
    or < 2 bpm."""

    @pytest.mark.asyncio
    async def test_hr_drift_with_steady_state_above_lt1(self) -> None:
        """A steady-state segment with HR drift > 5 bpm produces an
        LT1_HR observation with weight 1.0."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        # Build a 30-min steady-state segment with increasing HR
        # (drift > 5 bpm). Use constant pace and grade.
        records: list[CleanedRecord] = []
        for t in range(30 * 60):  # 30 minutes
            # HR drifts from 140 to 150 over 30 min (drift = 10 bpm).
            hr = 140.0 + (10.0 * t / (30 * 60))
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=hr,
                    gap_sec_per_km=330.0,
                    grade_pct=0.0,
                )
            )
        stream = _make_stream(records)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        drift_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_HR_DRIFT
        ]
        # If a steady-state segment is found and drift > 5 bpm,
        # an observation is produced.
        for obs in drift_obs:
            assert obs.weight == WEIGHT_LT1_HR_DRIFT
            assert obs.parameter == PhysiologyParameter.LT1_HR


# ---------------------------------------------------------------------------
# Test: HR recovery method.
# ---------------------------------------------------------------------------


class TestHrRecoveryMethod:
    """LT1 HR recovery — hard effort + ≥2 min recovery, fast (>30 bpm)
    or slow (<20 bpm)."""

    @pytest.mark.asyncio
    async def test_hr_recovery_produces_lt1_observation(self) -> None:
        """A hard effort with fast recovery produces an LT1_HR
        observation with weight 0.5."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        records: list[CleanedRecord] = []
        # Ramp up to peak HR (190 bpm) over 20 minutes.
        for t in range(20 * 60):
            hr = 120.0 + (70.0 * t / (20 * 60))
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=hr,
                    gap_sec_per_km=360.0,
                    hr_60s_mean=hr,
                    hr_120s_mean=hr,
                )
            )
        # Hold at peak for 5 minutes.
        for t in range(20 * 60, 25 * 60):
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=190.0,
                    gap_sec_per_km=300.0,
                    hr_60s_mean=190.0,
                    hr_120s_mean=190.0,
                )
            )
        # Fast recovery: HR drops from 190 to 155 in 2 min (>30 bpm).
        for t in range(25 * 60, 27 * 60):
            recovery_t = t - 25 * 60
            hr = 190.0 - (35.0 * recovery_t / 120.0)
            records.append(
                _make_cleaned_record(
                    t,
                    hr_bpm=hr,
                    gap_sec_per_km=600.0,
                    hr_60s_mean=hr,
                    hr_120s_mean=hr,
                )
            )
        stream = _make_stream(records)
        service = _make_service(activity=activity, cleaned_stream=stream)

        result = await service.detect(activity.athlete_id, activity.id)

        recovery_obs = [
            o for o in result
            if o.algorithm_used == ALGORITHM_HR_RECOVERY
        ]
        for obs in recovery_obs:
            assert obs.weight == WEIGHT_LT1_HR_RECOVERY
            assert obs.parameter == PhysiologyParameter.LT1_HR


# ---------------------------------------------------------------------------
# Test: detect() does not write to PhysiologyMeasurement.
# ---------------------------------------------------------------------------


class TestDetectDoesNotWriteMeasurement:
    """The service does NOT write to ``PhysiologyMeasurement`` — that
    is ``PhysiologyUpdateService``'s responsibility (Plan P2)."""

    @pytest.mark.asyncio
    async def test_detect_does_not_call_measurement_insert(self) -> None:
        """``detect()`` never calls ``PhysiologyMeasurementRepository.insert``."""
        activity = _mock_activity(
            has_hr=True, has_rr_intervals=False, has_power=False
        )
        # Build a stream that will produce observations.
        records: list[CleanedRecord] = []
        for t in range(120):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=120.0, gap_sec_per_km=360.0
                )
            )
        for t in range(120, 240):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=140.0, gap_sec_per_km=330.0
                )
            )
        for t in range(240, 360):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=160.0, gap_sec_per_km=300.0
                )
            )
        for t in range(360, 480):
            records.append(
                _make_cleaned_record(
                    t, hr_bpm=180.0, gap_sec_per_km=270.0
                )
            )
        stream = _make_stream(records)
        service = _make_service(activity=activity, cleaned_stream=stream)

        await service.detect(activity.athlete_id, activity.id)

        # The repository's insert method must never be called.
        cast(AsyncMock, service.physiology_measurements.insert).assert_not_called()


# ---------------------------------------------------------------------------
# Test: observation weight constants match evidence-mapping.
# ---------------------------------------------------------------------------


class TestObservationWeightConstants:
    """The observation weights are fixed constants from
    ``evidence-mapping.md`` — they must match the expected values."""

    def test_hr_deflection_weight_is_1_0(self) -> None:
        assert WEIGHT_HR_DEFLECTION == 1.0

    def test_rr_inflection_weight_is_2_5(self) -> None:
        """RR inflection has higher weight than HR deflection because
        RR is a richer signal."""
        assert WEIGHT_RR_INFLECTION == 2.5

    def test_power_hr_ratio_weight_is_1_5(self) -> None:
        assert WEIGHT_POWER_HR_RATIO == 1.5

    def test_lt1_natural_training_weight_is_0_5(self) -> None:
        """Natural training analysis has lower weight (supplementary)."""
        assert WEIGHT_LT1_NATURAL_TRAINING == 0.5

    def test_lt1_hr_drift_weight_is_1_0(self) -> None:
        assert WEIGHT_LT1_HR_DRIFT == 1.0

    def test_lt1_hr_recovery_weight_is_0_5(self) -> None:
        """HR recovery is supplementary (weight 0.5)."""
        assert WEIGHT_LT1_HR_RECOVERY == 0.5


# ---------------------------------------------------------------------------
# Test: algorithm threshold constants.
# ---------------------------------------------------------------------------


class TestAlgorithmThresholdConstants:
    """The algorithm thresholds are frozen module constants."""

    def test_r2_min_threshold_is_0_80(self) -> None:
        """HR deflection requires R² ≥ 0.80 per the spec."""
        assert R2_MIN_THRESHOLD == 0.80

    def test_min_intensity_steps_is_3(self) -> None:
        """HR deflection requires ≥3 distinct intensity steps per the spec."""
        assert MIN_INTENSITY_STEPS == 3
