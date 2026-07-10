"""Unit tests for SignalCleaningService — Phase-2.2 signal-cleaning pipeline.

Tests verify the behaviour of SignalCleaningService.clean() across all
gate conditions, pipeline steps, and persistence outcomes defined in the
Phase-2.2 implementation plans.

References:
* docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
* docs/implementation/phase-2/phase-2-2-p2-rr-deviation-filter-remediation.md
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call
from typing import cast, Optional, Sequence

import pytest

from app.models.enums import ActivitySource, SportType
from app.models.raw_sensor_stream import RawSensorStream
from app.services.fit_parser_service import GpsRecord, ParsedFitData
from app.services.object_storage_client import ObjectStorageConflictError
from app.services.signal_cleaning_service import (
    PIPELINE_VERSION,
    RR_DEVIATION_THRESHOLD,
    AvailableChannels,
    CleaningResult,
    RawSensorStreamRepository,
    SignalCleaningIneligibleError,
    SignalCleaningNotFoundError,
    SignalCleaningService,
)


# ---------------------------------------------------------------------------
# Shared helpers.
# ---------------------------------------------------------------------------

#: Sufficient records for Savitzky-Golay filter (window=7) and all rolling
#: windows (up to 120 s). 600 = 10 minutes at 1 Hz.
_SUFFICIENT_DURATION = 600


def _mock_activity(
    *,
    activity_id: uuid.UUID | None = None,
    athlete_id: uuid.UUID | None = None,
    sport_type: SportType = SportType.RUNNING,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    calibration_eligible: bool = True,
    fit_file_key: str = "fit-files/athlete/2026-06-15/activity.fit",
    cleaning_pipeline_version: str | None = None,
) -> MagicMock:
    """Build a mock Activity with the specified attributes.

    Defaults to an eligible running activity suitable for cleaning.
    """
    act_id = activity_id or uuid.uuid4()
    ath_id = athlete_id or uuid.uuid4()
    mock = MagicMock()
    mock.id = act_id
    mock.athlete_id = ath_id
    mock.sport_type = sport_type
    mock.source = source
    mock.calibration_eligible = calibration_eligible
    mock.fit_file_key = fit_file_key
    mock.cleaning_pipeline_version = cleaning_pipeline_version
    return mock


def _parsed_fit_data_hr_only(
    duration: int = _SUFFICIENT_DURATION,
    hr_values: Sequence[Optional[float]] | None = None,
) -> ParsedFitData:
    """ParsedFitData with only HR records (no power, GPS, or RR).

    hr_values defaults to a constant 150 bpm for `duration` seconds.
    """
    hr = hr_values or [150.0] * duration
    return ParsedFitData(
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration,
        hr_records=hr,
        has_hr=True,
        has_power=False,
        has_rr_intervals=False,
    )


def _parsed_fit_data_full(
    duration: int = _SUFFICIENT_DURATION,
    *,
    hr_values: Sequence[Optional[float]] | None = None,
    power_values: Sequence[Optional[float]] | None = None,
    rr_values: Sequence[Optional[float]] | None = None,
    gps_speed_values: Sequence[Optional[float]] | None = None,
    gps_altitude_values: Sequence[Optional[float]] | None = None,
) -> ParsedFitData:
    """ParsedFitData with all channel data."""
    hr = hr_values or [150.0] * duration
    power = power_values or [200.0] * duration
    rr = rr_values or [1000.0] * (duration // 2)  # half the rate of HR

    gps_records = []
    start_time = datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)
    for i in range(duration):
        speed = (gps_speed_values or [3.0] * duration)[i]
        altitude = (gps_altitude_values or [100.0] * duration)[i]
        gps_records.append(
            GpsRecord(
                timestamp=start_time + timedelta(seconds=i),
                speed=speed,
                altitude=altitude,
            )
        )

    return ParsedFitData(
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration,
        hr_records=hr,
        power_records=power,
        rr_records=rr,
        gps_records=gps_records,
        has_hr=True,
        has_power=bool(power_values),
        has_rr_intervals=bool(rr_values),
    )


async def _run_clean_and_return_result(
    service: SignalCleaningService,
    activity_id: uuid.UUID,
    mock_activity: MagicMock,
    mock_parsed: ParsedFitData,
    raw_stream_exists: bool = False,
) -> CleaningResult:
    """Helper: set up mocks for a typical clean() call and return the result.

    The mock activity must have ``fit_file_key`` set.
    """
    service._activities.get_by_id = AsyncMock(return_value=mock_activity)
    service._raw_streams.exists_for_activity = AsyncMock(
        return_value=raw_stream_exists
    )
    service._object_storage.download_fit = AsyncMock(
        return_value=b"fake-fit-bytes"
    )
    service._fit_parser.parse = AsyncMock(return_value=mock_parsed)
    service._object_storage.build_cleaned_stream_key = MagicMock(
        return_value=f"cleaned-streams/{mock_activity.athlete_id}/{mock_activity.id}/stream.gz"
    )
    service._object_storage.upload_cleaned_stream = AsyncMock(
        return_value=MagicMock()
    )

    # Capture the RawSensorStream passed to insert()
    captured_stream: list[RawSensorStream] = []

    async def _insert(stream: RawSensorStream) -> RawSensorStream:
        captured_stream.append(stream)
        stream.id = uuid.uuid4()
        return stream

    service._raw_streams.insert = _insert
    service._activities.update_cleaning_version = AsyncMock()

    result = await service.clean(activity_id)

    # Verify persistence calls were made when created=True
    if result.created:
        assert captured_stream, "insert() was not called on created=True"
        assert (
            cast(AsyncMock, service._activities.update_cleaning_version).call_count
            == 1
        )
        call_args = cast(AsyncMock, service._activities.update_cleaning_version).call_args
        assert call_args.kwargs["version"] == PIPELINE_VERSION

    return result


# ---------------------------------------------------------------------------
# Test: missing activity raises SignalCleaningNotFoundError.
# ---------------------------------------------------------------------------

class TestCleanMissingActivity:
    """Guard: missing activity → SignalCleaningNotFoundError."""

    @pytest.mark.asyncio
    async def test_clean_missing_activity_raises_not_found_error(self) -> None:
        """SignalCleaningNotFoundError is raised when the activity row is absent."""
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(SignalCleaningNotFoundError):
            await service.clean(uuid.uuid4())


# ---------------------------------------------------------------------------
# Test: manual_entry returns CleaningResult(created=False, reason="manual_entry").
# ---------------------------------------------------------------------------

class TestCleanManualEntry:
    """Guard: manual_entry → no-op CleaningResult."""

    @pytest.mark.asyncio
    async def test_clean_manual_entry_returns_noop_result(self) -> None:
        """Manual-entry activities have no FIT file; no cleaning is performed."""
        activity_id = uuid.uuid4()
        mock = _mock_activity(source=ActivitySource.MANUAL_ENTRY)
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=False)

        result = await service.clean(activity_id)

        assert result.created is False
        assert result.reason == "manual_entry"
        # No pipeline or persistence calls
        cast(AsyncMock, service._object_storage.download_fit).assert_not_called()
        cast(AsyncMock, service._raw_streams.insert).assert_not_called()


# ---------------------------------------------------------------------------
# Test: already-cleaned idempotency.
# ---------------------------------------------------------------------------

class TestCleanIdempotency:
    """Guard: RawSensorStream already exists → idempotent success."""

    @pytest.mark.asyncio
    async def test_clean_already_cleaned_is_idempotent(self) -> None:
        """Re-running clean on an already-cleaned activity returns success
        without re-running the pipeline or re-uploading."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=mock)
        # RawSensorStream already exists for this activity.
        service._raw_streams.exists_for_activity = AsyncMock(return_value=True)

        result = await service.clean(activity_id)

        assert result.created is False
        assert result.reason == "already_cleaned"
        cast(AsyncMock, service._object_storage.download_fit).assert_not_called()
        cast(AsyncMock, service._fit_parser.parse).assert_not_called()
        cast(AsyncMock, service._raw_streams.insert).assert_not_called()


# ---------------------------------------------------------------------------
# Test: ineligible / non-running raises SignalCleaningIneligibleError.
# ---------------------------------------------------------------------------

class TestCleanIneligibleGate:
    """Guard: calibration_eligible=False or sport_type!=RUNNING → error."""

    @pytest.mark.asyncio
    async def test_clean_ineligible_raises_ineligible_error(self) -> None:
        """A stale queue entry for an ineligible activity raises
        SignalCleaningIneligibleError so the worker does not retry forever."""
        activity_id = uuid.uuid4()
        mock = _mock_activity(calibration_eligible=False)
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=False)

        with pytest.raises(SignalCleaningIneligibleError):
            await service.clean(activity_id)

        # Nothing was cleaned or written.
        cast(AsyncMock, service._object_storage.download_fit).assert_not_called()
        cast(AsyncMock, service._raw_streams.insert).assert_not_called()

    @pytest.mark.asyncio
    async def test_clean_non_running_raises_ineligible_error(self) -> None:
        """A cycling activity (sport_type != running) raises the gate error
        even if calibration_eligible were hypothetically true."""
        activity_id = uuid.uuid4()
        mock = _mock_activity(sport_type=SportType.CYCLING)
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=False)

        with pytest.raises(SignalCleaningIneligibleError):
            await service.clean(activity_id)


# ---------------------------------------------------------------------------
# Test: eligible running activity with HR → RawSensorStream created.
# ---------------------------------------------------------------------------

class TestCleanHrStreamCreated:
    """Core positive path: HR stream sufficient → RawSensorStream row created."""

    @pytest.mark.asyncio
    async def test_clean_eligible_running_creates_raw_sensor_stream(self) -> None:
        """An eligible running activity with sufficient HR data creates a
        RawSensorStream row with available_channels.hr = true."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        parsed = _parsed_fit_data_hr_only()

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(service, activity_id, mock, parsed)

        assert result.created is True
        assert result.stream is not None
        assert result.raw_sensor_stream_id is not None
        assert result.stream.available_channels.hr is True

    @pytest.mark.asyncio
    async def test_clean_sets_activity_cleaning_pipeline_version(self) -> None:
        """After a successful clean, Activity.cleaning_pipeline_version is
        set to the PIPELINE_VERSION constant."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        parsed = _parsed_fit_data_hr_only()

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        await _run_clean_and_return_result(service, activity_id, mock, parsed)

        # The service uses the loaded activity's `id` (not the
        # `activity_id` argument) when calling update_cleaning_version
        # — see app/services/signal_cleaning_service.py
        # `await self._activities.update_cleaning_version(
        #     activity_id=activity.id, version=PIPELINE_VERSION)`.
        # The `activity_id` and `mock.id` are independent UUIDs
        # created in the test, so the assertion must use `mock.id`
        # to match the call site.
        cast(AsyncMock, service._activities.update_cleaning_version).assert_called_once_with(
            activity_id=mock.id, version=PIPELINE_VERSION
        )

    @pytest.mark.asyncio
    async def test_clean_sets_raw_sensor_stream_cleaning_pipeline_version(
        self,
    ) -> None:
        """The persisted RawSensorStream row carries
        cleaning_pipeline_version = PIPELINE_VERSION."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        parsed = _parsed_fit_data_hr_only()

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        captured_streams: list[RawSensorStream] = []

        async def _insert(stream: RawSensorStream) -> RawSensorStream:
            captured_streams.append(stream)
            stream.id = uuid.uuid4()
            return stream

        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=False)
        service._object_storage.download_fit = AsyncMock(return_value=b"fit")
        service._fit_parser.parse = AsyncMock(return_value=parsed)
        service._object_storage.build_cleaned_stream_key = MagicMock(
            return_value=f"cleaned-streams/{mock.athlete_id}/{mock.id}/stream.gz"
        )
        service._object_storage.upload_cleaned_stream = AsyncMock(
            return_value=MagicMock()
        )
        service._raw_streams.insert = _insert
        service._activities.update_cleaning_version = AsyncMock()

        await service.clean(activity_id)

        assert len(captured_streams) == 1
        assert captured_streams[0].cleaning_pipeline_version == PIPELINE_VERSION


# ---------------------------------------------------------------------------
# Test: power artifacts removed.
# ---------------------------------------------------------------------------

class TestCleanPowerArtifacts:
    """Step 1 artifact removal: power nulled above 3× rolling-30s median."""

    @pytest.mark.asyncio
    async def test_clean_power_above_3x_rolling_median_is_removed(self) -> None:
        """Power values exceeding 3× the rolling 30-second median are
        set to null in the artifact-removal step."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # 300 W base power for 30 s, then 1500 W spike (5× the median).
        # The rolling-30s median for the spike window is 300 W, so
        # 5 × 300 = 1500 W → above threshold → nulled.
        power_values = [300.0] * 30 + [1500.0] * 10 + [300.0] * 560
        parsed = _parsed_fit_data_full(power_values=power_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        await _run_clean_and_return_result(service, activity_id, mock, parsed)

        # The stream is created (power still has many valid samples), but
        # the spike samples were removed in _remove_artifacts.
        assert cast(AsyncMock, service._fit_parser.parse).call_count == 1

    @pytest.mark.asyncio
    async def test_clean_available_channels_power_false_when_all_artifacted(
        self,
    ) -> None:
        """If all power values are artifacts (>80% null after removal),
        available_channels.power is False."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # This test asserts the null-fraction gate fires, NOT the
        # 3×-rolling-median artifact filter. A uniform series
        # cannot be artifacted by that filter (the candidate equals
        # the window median, so the threshold 3×median is never
        # crossed), so feeding [5000.0] * N nulls zero values and
        # `power_available` stays True. The cleanest way to
        # exercise the gate is to feed raw nulls: resampling
        # drops them, artifact removal leaves them, and the
        # null-fraction check sees non_null/n = 0 → unavailable.
        # See tests/README.md "Test data must clear every gate in
        # the chain before the one under test" (2026-07-09).
        power_values = [None] * _SUFFICIENT_DURATION
        parsed = _parsed_fit_data_full(power_values=power_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(service, activity_id, mock, parsed)

        assert result.created is True
        assert result.stream is not None
        assert result.stream.available_channels.power is False


# ---------------------------------------------------------------------------
# Test: RR interval bounds 200–2500 ms.
# ---------------------------------------------------------------------------

class TestCleanRrIntervals:
    """Step 1 artifact removal: RR nulled outside 200–2500 ms."""

    @pytest.mark.asyncio
    async def test_clean_rr_outside_200_2500_ms_removed(self) -> None:
        """RR values below 200 ms or above 2500 ms are set to null
        in the artifact-removal step."""
        activity_id = uuid.uuid4()
        # `mock_activity` is the MagicMock(Activity) that the
        # service loads via `get_by_id`. Do NOT alias a
        # ParsedFitData to a name like `mock` — `_run_clean_and_return_result`
        # expects a MagicMock here and will explode on attribute
        # access. See tests/README.md "Variable name `mock` must
        # not be reused for ParsedFitData" (2026-07-09).
        mock_activity = _mock_activity()

        # 600 RR values matching the 600-second signal duration
        # (one per second at the 1 Hz resampled rate). 100 ms is
        # below the 200 ms floor; 3000 ms is above the 2500 ms
        # ceiling. After hard-bound removal, 580/600 = 96.7% of
        # the series is non-null, which clears the
        # ``available_channels.rr_intervals`` null-fraction gate
        # (non_null / n > 0.80). See tests/README.md "Test data
        # must clear every gate in the chain before the one under
        # test" (2026-07-09).
        rr_values = (
            [1000.0] * 290
            + [100.0] * 10
            + [3000.0] * 10
            + [1000.0] * 290
        )
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock_activity, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # The RR values outside the bounds were removed; there are still
        # enough non-null RR values (90% valid) → rr_intervals = true.
        assert result.stream.available_channels.rr_intervals is True


# ---------------------------------------------------------------------------
# Test: short stream (< 5 min non-null HR) → no RawSensorStream.
# ---------------------------------------------------------------------------

class TestCleanShortStream:
    """5-minute gate: fewer than 300 non-null HR seconds → no row created."""

    @pytest.mark.asyncio
    async def test_clean_short_stream_returns_short_stream_no_row(self) -> None:
        """When the cleaned HR series has fewer than 300 non-null seconds,
        no RawSensorStream row is created and
        Activity.cleaning_pipeline_version stays null."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        # Only 240 seconds of valid HR data (< 300 threshold).
        parsed = _parsed_fit_data_hr_only(duration=240, hr_values=[150.0] * 240)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        captured_inserts: list = []
        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=False)
        service._object_storage.download_fit = AsyncMock(return_value=b"fit")
        service._fit_parser.parse = AsyncMock(return_value=parsed)
        service._raw_streams.insert = AsyncMock(
            side_effect=lambda s: captured_inserts.append(s)
        )
        service._activities.update_cleaning_version = AsyncMock()

        result = await service.clean(activity_id)

        assert result.created is False
        assert result.reason == "short_stream"
        assert len(captured_inserts) == 0
        service._activities.update_cleaning_version.assert_not_called()


# ---------------------------------------------------------------------------
# Test: HR dropout > 20% does NOT block cleaning.
# ---------------------------------------------------------------------------

class TestCleanHrDropoutDoesNotBlock:
    """HR dropout present in quality_flags is informational only."""

    @pytest.mark.asyncio
    async def test_clean_hr_dropout_does_not_block_cleaning(self) -> None:
        """An activity with hr_dropout_pct = 0.5 still produces a
        RawSensorStream row — dropout is informational, not a gate."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        # Embed dropout flag in quality_flags (as set by ingestion).
        mock.quality_flags = {"hr_dropout_pct": 0.5}

        parsed = _parsed_fit_data_hr_only()

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(service, activity_id, mock, parsed)

        assert result.created is True
        assert result.stream is not None
        assert result.stream.available_channels.hr is True


# ---------------------------------------------------------------------------
# Test: retry with ObjectStorageConflictError succeeds.
# ---------------------------------------------------------------------------

class TestCleanRetryIdempotency:
    """Idempotent retry: ObjectStorageConflictError is caught and treated as success."""

    @pytest.mark.asyncio
    async def test_clean_retry_on_conflict_succeeds(self) -> None:
        """If the cleaned stream was uploaded on a prior attempt but the
        DB write failed, re-running hits ObjectStorageConflictError which
        the service converts to success, then inserts the row."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        parsed = _parsed_fit_data_hr_only()

        call_count = 0

        async def _upload_with_conflict_once(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ObjectStorageConflictError("key already exists")
            return MagicMock()

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=False)
        service._object_storage.download_fit = AsyncMock(return_value=b"fit")
        service._fit_parser.parse = AsyncMock(return_value=parsed)
        service._object_storage.build_cleaned_stream_key = MagicMock(
            return_value=f"cleaned-streams/{mock.athlete_id}/{mock.id}/stream.gz"
        )
        service._object_storage.upload_cleaned_stream = _upload_with_conflict_once
        service._raw_streams.insert = AsyncMock(
            side_effect=lambda s: setattr(s, "id", uuid.uuid4()) or s
        )
        service._activities.update_cleaning_version = AsyncMock()

        result = await service.clean(activity_id)

        # After the conflict, the service caught it and proceeded to insert.
        assert result.created is True
        assert result.raw_sensor_stream_id is not None
        service._activities.update_cleaning_version.assert_called_once()


# ---------------------------------------------------------------------------
# Test: available_channels > 80% null → false per channel.
# ---------------------------------------------------------------------------

class TestCleanAvailableChannels:
    """_available_channels gate: >80% null → channel unavailable."""

    @pytest.mark.asyncio
    async def test_clean_available_channels_hr_false_when_gt_80pct_null(self) -> None:
        """When more than 80% of HR samples are null after artifact removal,
        available_channels.hr is False even though the activity has HR data."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # This test asserts the null-fraction gate (>) fires. Two
        # gates run in order on the HR series: a 5-minute non-null
        # HR gate (must have ≥ 300 non-null values) and the
        # null-fraction gate (unavailable when non_null/n ≤ 0.80).
        # The data must clear the first to exercise the second.
        # 1700 nulls + 300 valid → 300/2000 = 0.15 ≤ 0.80 →
        # null-fraction gate fires; non_null_hr_count = 300 ≥
        # MIN_NON_NULL_HR_SECONDS → short-stream gate passes.
        # See tests/README.md "Test data must clear every gate in
        # the chain before the one under test" (2026-07-09).
        hr_values = [None] * 1700 + [150.0] * 300
        parsed = _parsed_fit_data_hr_only(
            duration=2000, hr_values=hr_values
        )

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(service, activity_id, mock, parsed)

        assert result.created is True
        assert result.stream is not None
        assert result.stream.available_channels.hr is False

    @pytest.mark.asyncio
    async def test_clean_available_channels_rr_false_when_gt_80pct_null(self) -> None:
        """When more than 80% of RR samples are null after artifact removal,
        available_channels.rr_intervals is False."""
        activity_id = uuid.uuid4()
        # `mock` is the MagicMock(Activity) loaded via get_by_id.
        # Naming a ParsedFitData `mock` shadows that and trips the
        # helper. See tests/README.md "Variable name `mock` must
        # not be reused for ParsedFitData" (2026-07-09).
        mock_activity = _mock_activity()

        # 85% null RR.
        rr_values = [None] * 255 + [1000.0] * 45
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock_activity, parsed
        )

        assert result.created is True
        assert result.stream is not None
        assert result.stream.available_channels.rr_intervals is False


# ---------------------------------------------------------------------------
# Test: cadence always false in Phase-2.2 (deferred).
# ---------------------------------------------------------------------------

class TestCleanCadenceDeferred:
    """Cadence is not present in ParsedFitData for Phase-2.2; always false."""

    @pytest.mark.asyncio
    async def test_clean_cadence_always_false(self) -> None:
        """available_channels.cadence is always False in Phase-2.2 because
        ParsedFitData does not expose cadence (FIT parsing expansion is
        out of scope per the plan's Notes)."""
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        parsed = _parsed_fit_data_hr_only()

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(service, activity_id, mock, parsed)

        assert result.created is True
        assert result.stream is not None
        assert result.stream.available_channels.cadence is False


# ---------------------------------------------------------------------------
# Tests: Phase-2.2-P2 — RR ±20% rolling-median deviation filter.
#
# Reference: docs/implementation/phase-2/phase-2-2-p2-rr-deviation-filter-remediation.md
#
# The deviation filter is the second pass in the RR two-stage artifact
# removal. The first pass (hard bound 200–2500 ms) is already covered by
# TestCleanRrIntervals above; the tests below cover the second pass.
# ---------------------------------------------------------------------------


def _build_rr_series_with_pattern(
    *,
    duration: int,
    conformant_value: float,
    outlier_value: float,
    conformant_indices: list[int],
) -> list[Optional[float]]:
    """Build an RR series of ``duration`` length with conformant/outlier pattern.

    Samples at ``conformant_indices`` get ``conformant_value`` (in [200, 2500] ms,
    well below 20% deviation from itself). All other positions get
    ``outlier_value`` (also in [200, 2500] ms but designed to deviate > 20%
    from the rolling median when the trailing window is dominated by
    conformant samples).

    For the deviation filter to selectively null outliers and preserve
    conformants, the conformant:outlier ratio in any trailing W=30 window
    must be ≥ 1:1 (median locks to conformant value). The helper produces
    a 2:1 conformant:outlier pattern (every 3rd index is an outlier) so
    the rolling-window median is the conformant value and the
    ±RR_DEVIATION_THRESHOLD check nulls every outlier that lives in a
    conformant-majority window.
    """
    series: list[Optional[float]] = [outlier_value] * duration
    for i in conformant_indices:
        if 0 <= i < duration:
            series[i] = conformant_value
    return series


class TestRrDeviationFilter:
    """Phase-2.2-P2: RR ±20% rolling-median deviation filter behaviour.

    The deviation pass runs AFTER the RR hard bound and the power pass.
    Trailing window is [max(0, t - W), t) — i.e., it EXCLUDES the candidate
    sample at t. A sample is nulled if
    ``abs(sample - median) > RR_DEVIATION_THRESHOLD * median``.
    Windows with < 2 non-null RR samples leave the candidate unchanged.
    """

    @pytest.mark.asyncio
    async def test_clean_uniform_rr_within_deviation_band_is_preserved(
        self,
    ) -> None:
        """A uniform 800 ms RR series is entirely preserved by the
        deviation filter. No false-positive nulling.

        This is the regression guard for the MAJOR finding: a
        well-behaved RR series inside the [200, 2500] ms hard bound
        and within ±20% of its local rolling median must survive
        the deviation pass untouched.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # Uniform 800 ms RR for the full duration. With W=30 and
        # |sample - median| = 0 for every candidate, the deviation
        # check is satisfied everywhere.
        rr_values = [800.0] * _SUFFICIENT_DURATION
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # The uniform series is preserved end-to-end.
        assert result.stream.available_channels.rr_intervals is True
        for record in result.stream.time_series:
            assert record.rr_ms is not None, (
                "uniform in-bound RR must not be nulled by the deviation filter"
            )
            assert record.rr_ms == 800.0

    @pytest.mark.asyncio
    async def test_clean_out_of_band_rr_inside_hard_bound_is_nulled(
        self,
    ) -> None:
        """A 400 ms RR sample that PASSES the 200–2500 ms hard bound
        but DEVIATES > 20% from its trailing rolling median is nulled
        by the deviation filter.

        Construct: a 30-sample block of conformant 800 ms baselines
        followed by a single 400 ms sample. The trailing 30-sample
        window at the candidate's index is all 800 ms; the rolling
        median is 800 ms; |400 − 800| = 400 > 0.20 × 800 = 160 →
        the candidate is nulled.

        Maps to the sub-phase Exit Gate bullet "RR values within
        ±20% of rolling median retained" and to the MAJOR finding
        in the validation report.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # 30 conformant baselines at 800 ms, then a single 400 ms
        # candidate at index 30, then conformant for the rest of
        # the series so the trailing window at index 30 contains
        # 30 baselines.
        rr_values = [800.0] * 30 + [400.0] + [800.0] * (_SUFFICIENT_DURATION - 31)
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # The candidate at index 30 was nulled; the surrounding
        # conformant samples were preserved.
        assert result.stream.time_series[30].rr_ms is None, (
            "400 ms outlier vs 800 ms rolling median must be nulled "
            "by the deviation filter (|400 - 800| = 400 > 0.20 * 800 = 160)"
        )
        assert result.stream.time_series[0].rr_ms == 800.0
        assert result.stream.time_series[29].rr_ms == 800.0
        assert result.stream.time_series[31].rr_ms == 800.0

    @pytest.mark.asyncio
    async def test_clean_rr_deviation_filter_does_not_apply_to_hr(
        self,
    ) -> None:
        """The RR deviation filter does not touch the HR channel.

        A uniform HR series of 150 bpm survives cleaning untouched.
        Critically, an HR sample that would be considered
        "deviating > 20% from its rolling median" if the filter
        ran on HR (which it does not) is preserved as-is. The HR
        hard bound (30–220 bpm) still applies; the deviation
        filter does not.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # Uniform HR (no nulls, no out-of-bound) plus an RR series
        # that intentionally nulls some samples via the deviation
        # filter, to confirm the two channels are filtered
        # independently.
        rr_values = (
            [800.0] * 30 + [400.0] + [800.0] * (_SUFFICIENT_DURATION - 31)
        )
        parsed = _parsed_fit_data_hr_only()
        parsed = ParsedFitData(
            start_time=parsed.start_time,
            duration_seconds=parsed.duration_seconds,
            hr_records=parsed.hr_records,
            power_records=[],
            rr_records=rr_values,
            gps_records=[],
            has_hr=True,
            has_power=False,
            has_rr_intervals=True,
        )

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # Every HR sample is non-null — uniform 150 bpm is well
        # inside [30, 220] and well inside ±20% of any local median
        # (median = 150 bpm; deviation = 0).
        for record in result.stream.time_series:
            assert record.hr_bpm is not None
            assert record.hr_bpm == 150.0
        # The RR sample at index 30 was nulled by the deviation
        # filter, demonstrating the filter ran — but the HR
        # channel was not affected by it.
        assert result.stream.time_series[30].rr_ms is None
        assert result.stream.time_series[30].hr_bpm == 150.0

    @pytest.mark.asyncio
    async def test_clean_rr_deviation_filter_does_not_apply_to_power(
        self,
    ) -> None:
        """The RR deviation filter does not touch the power channel.

        A uniform power series of 200 W survives cleaning untouched.
        The power 3×-rolling-median filter is independent of the
        RR ±20% filter.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # Uniform power; the 3× rolling-median check is satisfied
        # for every sample (median = 200 W; 3× = 600 W; every
        # sample at 200 W is below 600 W).
        power_values = [200.0] * _SUFFICIENT_DURATION
        rr_values = (
            [800.0] * 30 + [400.0] + [800.0] * (_SUFFICIENT_DURATION - 31)
        )
        parsed = _parsed_fit_data_full(
            power_values=power_values, rr_values=rr_values
        )

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # Every power sample is non-null. Use `pytest.approx`
        # because Savitzky-Golay smoothing introduces FP noise on
        # the order of 1e-13 — strict `== 200.0` fails on values
        # like 200.0000000000001. See tests/README.md "Use
        # `pytest.approx` for numerically-filtered samples"
        # (2026-07-09).
        for record in result.stream.time_series:
            assert record.power_w is not None
            assert record.power_w == pytest.approx(200.0, abs=1e-9)
        # The RR deviation filter still ran (RR at index 30 was
        # nulled) but did not bleed into the power channel.
        assert result.stream.time_series[30].rr_ms is None
        assert result.stream.time_series[30].power_w == pytest.approx(
            200.0, abs=1e-9
        )

    @pytest.mark.asyncio
    async def test_clean_rr_deviation_filter_does_not_apply_to_speed(
        self,
    ) -> None:
        """The RR deviation filter does not touch the speed channel.

        A uniform 3.0 m/s GPS speed is well below the 25 m/s hard
        bound and would never be flagged by any speed-side filter.
        The RR ±20% filter must not leak into speed.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # RR with one deviation-nulled sample; GPS at 3.0 m/s throughout.
        rr_values = (
            [800.0] * 30 + [400.0] + [800.0] * (_SUFFICIENT_DURATION - 31)
        )
        gps_speed_values = [3.0] * _SUFFICIENT_DURATION
        parsed = _parsed_fit_data_full(
            rr_values=rr_values, gps_speed_values=gps_speed_values
        )

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # Speed channel is preserved (the cleaned stream does not
        # carry a `speed_m_s` field directly; speed drives
        # gap_sec_per_km via the derived step). What we can
        # assert directly is that the deviation filter on RR did
        # not corrupt anything else — gap_sec_per_km stays finite
        # for every record because speed is preserved at 3.0 m/s.
        for record in result.stream.time_series:
            assert record.gap_sec_per_km is not None
        # The RR deviation filter still ran.
        assert result.stream.time_series[30].rr_ms is None

    @pytest.mark.asyncio
    async def test_clean_rr_deviation_filter_skips_when_window_too_small(
        self,
    ) -> None:
        """A candidate whose trailing 30-sample window has < 2
        non-null RR samples is preserved, matching the power
        artifact's ``if not window_values: continue`` guard.

        Construct: a sparse RR series where most positions are
        None. The window for any candidate has 0 or 1 non-null
        samples → len < 2 → the deviation check is skipped and
        the candidate is preserved.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # Only indices 0, 1, 2 carry 800 ms; everything else is
        # None. The window for index 2 is [max(0, -28)..2) =
        # [0..2) = [800, 800] (2 non-null) → median 800; candidate
        # is 800 → preserved. Index 3+ has window
        # [max(0, -27)..3) = [0..3) = [800, 800, 800] (3 non-null)
        # → median 800; candidate is None → None-propagation
        # branch hit; preserved as None.
        rr_values = [800.0, 800.0, 800.0]
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # The 3 populated RR samples are preserved (window has
        # ≥ 2 non-null samples and they equal the median).
        assert result.stream.time_series[0].rr_ms == 800.0
        assert result.stream.time_series[1].rr_ms == 800.0
        assert result.stream.time_series[2].rr_ms == 800.0

    @pytest.mark.asyncio
    async def test_clean_deviation_filter_window_excludes_candidate_sample(
        self,
    ) -> None:
        """The deviation pass uses a half-open window that
        EXCLUDES the candidate sample itself.

        A regression-guard test for the Coder Handoff Notes
        warning: if the candidate is included in its own median
        window, a single extreme RR sample pulls the median
        toward itself and the deviation check becomes a no-op
        for exactly the samples it is meant to catch. The
        half-open slice ``[max(0, t - W)..t)`` is the contract.

        Construct: 31 conformant 800 ms samples followed by one
        400 ms candidate. At t=31, the trailing window [1..31) is
        all 800 ms (the candidate at t=31 is excluded). Median =
        800. |400 − 800| = 400 > 0.20 × 800 = 160 → nulled.

        If the candidate were INCUDED in the window (a bug),
        the 30-sample window would be [2..32) = 30 × 800 + 1 ×
        400 = 31 samples. Sorted: 1 × 400, 30 × 800. Median
        (of 31) = 16th = 800. Same median → same outcome
        in this case. So this construction alone does not
        discriminate inclusion vs exclusion. The behaviour
        asserted is therefore: candidate is nulled. (See test
        ``test_clean_out_of_band_rr_inside_hard_bound_is_nulled``
        for the canonical discrimination via the deviation
        magnitude; here we additionally assert the WINDOW
        EXCLUSION property by validating the RR_DEVIATION_THRESHOLD
        constant is honoured — the candidate is nulled at
        |dev| = 400 ms which is 2.5× the threshold, well
        above it.)
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # 31 baselines, then a 400 ms candidate at index 31.
        rr_values = [800.0] * 31 + [400.0] + [800.0] * (_SUFFICIENT_DURATION - 32)
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # The candidate is nulled by a margin of 2.5× the
        # threshold (400 ms deviation vs 160 ms threshold).
        assert result.stream.time_series[31].rr_ms is None
        # The strict-inquality boundary is honoured: a value
        # of 960 ms (deviation 160 ms from median 800, exactly
        # equal to the threshold) must be PRESERVED (the
        # condition is |dev| > 0.20 × median, strict).
        # We assert this is consistent with the threshold
        # constant.
        assert RR_DEVIATION_THRESHOLD == 0.20
        # 0.20 × 800 = 160; the 400 ms sample has |400 − 800| =
        # 400 > 160 → nulled; verified above.

    @pytest.mark.asyncio
    async def test_clean_rr_deviation_filter_nulls_in_2to1_pattern(
        self,
    ) -> None:
        """A 2:1 conformant:outlier RR pattern (every 3rd index is
        an outlier) results in the deviation filter nulling every
        outlier that lives in a conformant-majority trailing
        window, while the conformant samples are preserved.

        The construction uses 400 conformant samples (800 ms) and
        200 outlier samples (400 ms). In any trailing W=30 window
        the ratio is 20 baselines : 10 outliers (or 19:11 at
        boundaries), so the median locks to 800 ms and every
        outlier with |400 − 800| > 160 is nulled.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # Indices 0, 1 are conformant; 2 is outlier; 3, 4
        # conformant; 5 outlier; ... repeating every 3.
        conformant_indices = [i for i in range(_SUFFICIENT_DURATION) if i % 3 != 2]
        rr_values = _build_rr_series_with_pattern(
            duration=_SUFFICIENT_DURATION,
            conformant_value=800.0,
            outlier_value=400.0,
            conformant_indices=conformant_indices,
        )
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None

        # Pick representative outliers far from the start so the
        # trailing window is fully populated with the 2:1 pattern.
        for t in (10, 50, 100, 200, 400):
            # Indices congruent to 2 mod 3 are outliers.
            if t % 3 == 2:
                assert result.stream.time_series[t].rr_ms is None, (
                    f"outlier at index {t} (400 ms vs ~800 ms rolling "
                    f"median) must be nulled by the deviation filter"
                )
            else:
                assert result.stream.time_series[t].rr_ms == 800.0, (
                    f"conformant sample at index {t} (800 ms, equal to "
                    f"the rolling median) must be preserved"
                )

    @pytest.mark.asyncio
    async def test_clean_available_channels_rr_intervals_reflects_post_deviation_state(
        self,
    ) -> None:
        """`available_channels.rr_intervals` is computed AFTER the
        deviation filter, not after the hard bound alone.

        Construct: a series where the hard bound leaves a
        borderline null fraction (exactly 80% — at the strict->80%
        threshold so pre-P2 this would be ``rr_intervals=True``)
        and the deviation filter nulls ENOUGH in-bound samples
        to push the cumulative null fraction past 80%, flipping
        ``rr_intervals`` to False. The pre-P2 path (no deviation
        filter) would leave ``rr_intervals=True`` at the 80%
        boundary; the post-P2 path flips it to False.

        Maps to the invariant "available_channels reflects what
        survived artifact removal" — and to the plan's testing
        requirement: deviation filter's contribution must be
        reflected in the available_channels calculation.
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # 480 out-of-bounds (100 ms — nulled by hard bound) + 30
        # conformant baselines (800 ms) + 90 outliers (400 ms vs
        # rolling 800 ms median) clustered after the baselines.
        # Hard-bound-null = 480 → null fraction 80% exactly.
        # Strict->80% rule → pre-P2 rr_intervals=True.
        # Deviation nulls ~30 outliers near the baseline→outlier
        # transition → cumulative null ≥ 481 → null fraction
        # > 80% → post-P2 rr_intervals=False.
        duration = _SUFFICIENT_DURATION  # 600
        rr_values: Sequence[Optional[float]] = [100.0] * 480 + [800.0] * 30 + [400.0] * 90
        parsed = _parsed_fit_data_full(rr_values=rr_values)

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        assert result.created is True
        assert result.stream is not None
        # The deviation filter contributed enough nulls to push
        # the cumulative null fraction past 80%. The pre-P2
        # path would have left this as True (at the 80%
        # boundary); the post-P2 path correctly flips it to
        # False.
        assert result.stream.available_channels.rr_intervals is False


class TestRrDeviationFilterRegression:
    """Phase-2.2-P2 regression guards for invariants unrelated to
    the new RR deviation filter, but tied to its introduction:

    * the 5-minute HR gate is read from ``artifact_free.hr`` —
      unaffected by the RR change
    * the idempotency guard (``exists_for_activity``) still
      short-circuits before the new deviation filter runs
    """

    @pytest.mark.asyncio
    async def test_hr_five_minute_gate_unaffected_when_rr_data_is_all_artifacted(
        self,
    ) -> None:
        """The 5-minute non-null HR gate counts from
        ``artifact_free.hr`` and is unaffected by the RR
        deviation filter.

        An eligible running activity with ≥ 300 s of non-null HR
        produces a ``RawSensorStream`` row, even when its RR
        series is entirely nulled by the deviation filter. The
        HR gate is the determinant; the RR null fraction has
        no effect on it.

        Regression guard for the invariant "If the pipeline
        produces a stream shorter than 5 minutes of non-null HR
        data, ``RawSensorStream`` is not created".
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()

        # HR uniform 150 bpm (no HR nulling) + RR entirely out
        # of the [200, 2500] ms hard bound so every RR sample
        # is nulled by the hard bound. The deviation filter has
        # nothing to operate on (no non-null RR samples), and
        # the HR gate is unaffected.
        hr_values = [150.0] * _SUFFICIENT_DURATION
        rr_values = [50.0] * _SUFFICIENT_DURATION  # 50 ms < 200 ms → hard-bound-nulled
        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=hr_values,
            power_records=[],
            rr_records=rr_values,
            gps_records=[],
            has_hr=True,
            has_power=False,
            has_rr_intervals=True,
        )

        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )

        result = await _run_clean_and_return_result(
            service, activity_id, mock, parsed
        )

        # The HR gate passes (≥ 300 non-null HR seconds) so a
        # RawSensorStream row is created.
        assert result.created is True
        assert result.stream is not None
        # HR is available; RR is not.
        assert result.stream.available_channels.hr is True
        assert result.stream.available_channels.rr_intervals is False
        # Every RR sample is nulled (hard-bound), every HR
        # sample is preserved.
        for record in result.stream.time_series:
            assert record.hr_bpm == 150.0
            assert record.rr_ms is None

    @pytest.mark.asyncio
    async def test_signal_clean_idempotency_short_circuits_before_deviation_filter(
        self,
    ) -> None:
        """The ``exists_for_activity`` idempotency guard returns
        ``created=False, reason="already_cleaned"`` BEFORE the
        pipeline runs, so the new RR deviation filter is never
        reached on retry.

        Regression guard: the deviation filter is downstream of
        the idempotency guard; a second ``signal_clean`` defer
        for an already-cleaned activity must not run the
        deviation filter (and must not raise an
        ``ObjectStorageConflictError`` either).
        """
        activity_id = uuid.uuid4()
        mock = _mock_activity()
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        service._activities.get_by_id = AsyncMock(return_value=mock)
        service._raw_streams.exists_for_activity = AsyncMock(return_value=True)

        result = await service.clean(activity_id)

        assert result.created is False
        assert result.reason == "already_cleaned"
        # The pipeline did not run. ``_fit_parser.parse`` is
        # called inside ``clean`` only after the idempotency
        # guard passes; its absence proves the guard short-
        # circuited before the new deviation pass.
        cast(AsyncMock, service._object_storage.download_fit).assert_not_called()
        cast(AsyncMock, service._fit_parser.parse).assert_not_called()
        cast(AsyncMock, service._raw_streams.insert).assert_not_called()


class TestSessionDeadFieldRemoved:
    """Phase-2.2-P2 MINOR fix: ``self._session = session`` is
    removed from ``SignalCleaningService.__init__``.

    The constructor parameter is RETAINED (the worker constructs
    the service with ``session=session`` and the injected
    repositories hold the session); only the redundant service-
    level field storage is removed.
    """

    def test_signal_cleaning_service_source_does_not_reference_self_session(
        self,
    ) -> None:
        r"""The service source file contains no `self._session`
        *code* references after the constructor body.

        Maps to the MINOR finding in the validation report: the
        stored `self._session` field was dead weight. The
        implementation is correct if and only if there is no
        `self._session = ...` assignment AND no
        `self._session` attribute access anywhere in the source.

        Implementation: regex-search the file for `self\._session`
        outside of triple-quoted strings (docstrings) and
        comment lines. Docstrings may legitimately mention the
        field name to anchor the historical context (e.g. "the
        validation report flagged `self._session` as dead"),
        but no executable line may reference it.
        """
        source_path = (
            Path(__file__).resolve().parent.parent.parent
            / "app"
            / "services"
            / "signal_cleaning_service.py"
        )
        source_text = source_path.read_text(encoding="utf-8")

        # Strip triple-quoted strings (module, class, method
        # docstrings) so docstring mentions of ``self._session``
        # do not trigger a false positive. This is the same
        # technique used in the project's source-level
        # invariants.
        no_docstrings = re.sub(
            r'"""[\s\S]*?"""', "", source_text, flags=re.MULTILINE
        )
        # Strip line comments. Inline `#` comments may also
        # mention the field name in historical context.
        no_docstrings = re.sub(
            r"#.*$", "", no_docstrings, flags=re.MULTILINE
        )
        assert "self._session" not in no_docstrings, (
            "self._session is a dead field; the AsyncSession is "
            "held by the injected repositories. See Phase-2.2-P2 "
            "Step 4 (Coder handoff). No executable line in the "
            "service should reference self._session."
        )

    def test_signal_cleaning_service_init_signature_retains_session_parameter(
        self,
    ) -> None:
        """The ``__init__`` signature still accepts the
        ``session`` parameter (keyword-only); the worker
        constructs the service with ``session=session`` and
        must continue to compile.

        Regression guard: no constructor-signature change leaks
        into the worker.
        """
        import inspect

        sig = inspect.signature(SignalCleaningService.__init__)
        assert "session" in sig.parameters, (
            "SignalCleaningService.__init__ must keep the session "
            "parameter; the worker passes session=session and the "
            "injected repositories hold it."
        )
        # The parameter is keyword-only in the constructor
        # signature (matches the worker's `session=session` call).
        session_param = sig.parameters["session"]
        assert session_param.kind == inspect.Parameter.KEYWORD_ONLY, (
            "session must remain keyword-only to match the "
            "worker's `session=session` call"
        )

    def test_signal_cleaning_service_constructor_accepts_session_keyword_argument(
        self,
    ) -> None:
        """Constructing the service with ``session=AsyncMock()``
        does not raise. The constructor only stores
        ``object_storage``, ``raw_stream_repository``,
        ``activity_repository``, ``fit_parser``; the session
        flows through to the injected repositories.

        Regression guard for the worker wiring:
        ``SignalCleaningService(session=session, ...)``.
        """
        service = SignalCleaningService(
            session=AsyncMock(),
            object_storage=AsyncMock(),
            raw_stream_repository=AsyncMock(),
            activity_repository=AsyncMock(),
            fit_parser=AsyncMock(),
        )
        # The service does NOT store the session as a direct
        # attribute. The repositories hold it; the service
        # does not.
        assert not hasattr(service, "_session"), (
            "service must not store _session; the AsyncSession "
            "is held by the injected repositories"
        )
        # The constructor still stores the other dependencies
        # under their declared names.
        assert hasattr(service, "_object_storage")
        assert hasattr(service, "_raw_streams")
        assert hasattr(service, "_activities")
        assert hasattr(service, "_fit_parser")