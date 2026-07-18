"""Integration tests for ``SignalCleaningService`` — service ↔ repository ↔ object-storage transaction contract.

These tests exercise the Phase-2.2 service end-to-end against the real
test database and the real local-fallback ``ObjectStorageClient``. The
``FitParserService`` is replaced with a stub returning engineered
``ParsedFitData`` so this test layer focuses on the **persistence and
storage transaction contract** rather than FIT parsing — that is the
distinction between the unit tests (in ``tests/unit/``) and this
integration layer.

The unit-test pack explicitly defers two invariants to the integration
layer; both are covered here:

* **RR ±20% rolling-median deviation filter** — engineered RR series
  with a known median and a single ±25% deviation. The deviation is
  filtered; the median is preserved. The 200/2500 ms bound is
  exercised at the unit level; this test exercises the
  rolling-median criterion.
* **Gen-1 population GAP formula numerical accuracy** — engineered
  GPS series with a known grade; the resulting ``gap_sec_per_km`` is
  computed by the service and compared to the formula
  ``raw_pace / (1 + a*grade + b*grade²)`` with the documented
  coefficients ``a=0.033, b=0.00012``.

Reference plan: ``docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md``
"""

from __future__ import annotations

import gzip
import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional, cast

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from app.models.raw_sensor_stream import RawSensorStream
from app.repositories.activity_repository import ActivityRepository
from app.repositories.raw_sensor_stream_repository import (
    RawSensorStreamRepository,
)
from app.services.fit_parser_service import (
    GpsRecord,
    ParsedFitData,
)
from app.services.object_storage_client import (
    ObjectStorageClient,
)
from app.services.signal_cleaning_service import (
    GAP_COEFFICIENT_A,
    GAP_COEFFICIENT_B,
    PIPELINE_VERSION,
    RR_DEVIATION_THRESHOLD,
    RR_MIN_MS,
    RR_MAX_MS,
    RR_ROLLING_WINDOW_S,
    SignalCleaningService,
)
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

#: 10 minutes at 1 Hz — comfortably above the 5-minute gate.
_SUFFICIENT_DURATION = 600
#: 4 minutes — below the 5-minute non-null HR gate.
_SHORT_DURATION = 240


class _StubFitParser:
    """FitParserService stub returning a fixed ``ParsedFitData``.

    The ``parse`` call records its argument so tests can assert the
    service downloaded the correct FIT bytes. The returned
    ``ParsedFitData`` is the one passed to the constructor.
    """

    def __init__(self, parsed: ParsedFitData) -> None:
        self._parsed = parsed
        self.calls: list[bytes] = []

    async def parse(self, file_bytes: bytes) -> ParsedFitData:
        self.calls.append(file_bytes)
        return self._parsed


def _build_real_object_storage() -> ObjectStorageClient:
    """Build a real ``ObjectStorageClient`` configured for the local fallback.

    The conftest clears S3 env vars at import time, so a fresh
    ``ObjectStorageClient`` instance always uses the local
    filesystem at ``./var/object-storage`` — the same path the
    ingestion pipeline writes to.
    """
    return ObjectStorageClient()


async def _upload_raw_fit(
    object_storage: ObjectStorageClient,
    *,
    athlete_id: uuid.UUID,
    activity_date: date,
) -> str:
    """Upload a stub raw FIT file to object storage and return the key.

    The bytes are arbitrary; the parser stub does not look at them.
    The upload goes through the real local-fallback path so the
    service's ``download_fit`` call works without mocking.
    """
    stored = await object_storage.upload_fit(
        athlete_id=athlete_id,
        activity_date=activity_date,
        file_bytes=b"FAKE-FIT-BYTES-FOR-INTEGRATION-TEST",
    )
    return stored.key


async def _create_running_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    fit_file_key: Optional[str] = None,
    calibration_eligible: bool = True,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
    sport_type: SportType = SportType.RUNNING,
    cleaning_pipeline_version: Optional[str] = None,
    quality_flags: Optional[dict[str, Any]] = None,
) -> Activity:
    """Insert a real ``Activity`` row that is eligible for cleaning."""
    activity = Activity(
        athlete_id=athlete_id,
        source=source,
        activity_date=date(2026, 6, 15),
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=_SUFFICIENT_DURATION,
        aerobic_load=85.0,
        has_hr=True,
        has_rr_intervals=False,
        has_power=False,
        has_gps=True,
        sport_type=sport_type,
        calibration_eligible=calibration_eligible,
        quality_flags=quality_flags or {},
        fit_file_key=fit_file_key,
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version=cleaning_pipeline_version,
    )
    db_session.add(activity)
    await db_session.flush()
    await db_session.refresh(activity)
    return activity


def _hr_only_parsed(
    duration: int,
    hr_values: Optional[List[float]] = None,
) -> ParsedFitData:
    """ParsedFitData with HR only (no power, no GPS, no RR)."""
    hr: list[float | None] = list(hr_values) if hr_values is not None else [150.0] * duration
    return ParsedFitData(
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration,
        hr_records=hr,
        has_hr=True,
        has_power=False,
        has_rr_intervals=False,
    )


def _gps_running_flat(
    duration: int,
    *,
    speed_m_s: float = 3.0,
) -> List[GpsRecord]:
    """Flat GPS series: constant speed, constant altitude.

    A flat grade (elevation_delta = 0 across the window) makes
    ``grade_pct = 0`` for every record, which is the cleanest
    setting for GAP-formula accuracy tests.
    """
    return [
        GpsRecord(
            timestamp=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            altitude=100.0,
            speed=speed_m_s,
        )
        for _ in range(duration)
    ]


def _gps_running_uphill(
    duration: int,
    *,
    speed_m_s: float = 3.0,
    elevation_gain_m: float = 30.0,
) -> List[GpsRecord]:
    """Constant-speed GPS series with a linear uphill grade.

    ``elevation_gain_m`` is distributed evenly across ``duration``
    records, giving a constant ``grade_pct = (gain / distance) * 100``
    where ``distance = speed * duration``.
    """
    altitude_step = elevation_gain_m / max(duration - 1, 1)
    return [
        GpsRecord(
            timestamp=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            altitude=100.0 + altitude_step * t,
            speed=speed_m_s,
        )
        for t in range(duration)
    ]


def _build_service(
    db_session: AsyncSession,
    parsed: ParsedFitData,
    object_storage: ObjectStorageClient,
) -> tuple[SignalCleaningService, _StubFitParser, RawSensorStreamRepository, ActivityRepository]:
    """Build a service with real DB and real local-fallback object storage.

    The parser is the only stubbed dependency. The
    ``RawSensorStreamRepository`` and ``ActivityRepository`` are
    real (bound to ``db_session``).
    """
    parser = _StubFitParser(parsed)
    raw_repo = RawSensorStreamRepository(db_session)
    activity_repo = ActivityRepository(db_session)
    service = SignalCleaningService(
        session=db_session,
        object_storage=object_storage,
        raw_stream_repository=raw_repo,
        activity_repository=activity_repo,
        fit_parser=parser,  # type: ignore[arg-type]
    )
    return service, parser, raw_repo, activity_repo


# ---------------------------------------------------------------------------
# Test: end-to-end happy path — service+repo+object-storage transaction.
# ---------------------------------------------------------------------------

class TestCleanHappyPath:
    """Service ↔ real repo ↔ real local-fallback object storage."""

    @pytest.mark.asyncio
    async def test_clean_persists_raw_sensor_stream_with_cleaned_key(
        self, db_session: AsyncSession
    ) -> None:
        """End-to-end: the service uploads the cleaned stream to object
        storage, inserts a ``RawSensorStream`` row whose
        ``fit_file_key`` is the cleaned-stream key, and updates
        ``Activity.cleaning_pipeline_version`` — all in the same
        transaction."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        service, parser, raw_repo, _ = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )

        result = await service.clean(activity.id)

        assert result.created is True
        assert result.raw_sensor_stream_id is not None
        assert result.stream is not None

        # The parser was called with the downloaded bytes.
        assert parser.calls == [b"FAKE-FIT-BYTES-FOR-INTEGRATION-TEST"]

        # The row exists with the cleaned-stream key, NOT the raw FIT key.
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None
        assert row.activity_id == activity.id
        assert row.cleaning_pipeline_version == PIPELINE_VERSION
        assert row.sampling_rate_hz == 1.0
        assert row.fit_file_key.startswith("cleaned-streams/")
        assert row.fit_file_key.endswith("/stream.gz")
        # The cleaned-stream key MUST be different from the raw FIT key.
        assert row.fit_file_key != fit_key

    @pytest.mark.asyncio
    async def test_cleaned_stream_bytes_are_gzipped_and_parseable(
        self, db_session: AsyncSession
    ) -> None:
        """The uploaded payload is gzipped JSON that, once
        decompressed, parses into the documented ``CleanedStream``
        structure with the right ``sampling_rate_hz`` and
        ``available_channels``."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        service, _, raw_repo, _ = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        await service.clean(activity.id)
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None

        # Download the cleaned stream back and confirm it is a
        # valid gzipped JSON document.
        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        decompressed = gzip.decompress(cleaned_bytes)
        payload = json.loads(decompressed.decode("utf-8"))

        assert payload["sampling_rate_hz"] == 1.0
        assert "time_series" in payload
        assert "available_channels" in payload
        assert payload["available_channels"]["hr"] is True
        assert payload["available_channels"]["cadence"] is False  # deferred

    @pytest.mark.asyncio
    async def test_clean_sets_activity_cleaning_pipeline_version_persists(
        self, db_session: AsyncSession
    ) -> None:
        """``Activity.cleaning_pipeline_version`` lands in the DB
        after commit and is queryable through a fresh repository call."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
            cleaning_pipeline_version=None,
        )
        assert activity.cleaning_pipeline_version is None
        await db_session.commit()

        service, _, _, activity_repo = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        await service.clean(activity.id)
        await db_session.commit()

        # Fresh query — the previous in-memory object is stale.
        refreshed = await activity_repo.get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version == PIPELINE_VERSION


# ---------------------------------------------------------------------------
# Test: short stream — gate fires, no row, no version.
# ---------------------------------------------------------------------------

class TestCleanShortStreamGate:
    """The 5-minute / 300-second non-null HR gate fires at the DB level."""

    @pytest.mark.asyncio
    async def test_short_stream_does_not_persist_row_or_update_version(
        self, db_session: AsyncSession
    ) -> None:
        """A 4-minute stream (< 5 minutes of non-null HR) returns
        ``created=False, reason="short_stream"`` and writes nothing
        to the ``raw_sensor_streams`` table. ``Activity.cleaning_pipeline_version``
        stays ``None``."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
            cleaning_pipeline_version=None,
        )
        await db_session.commit()

        service, _, raw_repo, activity_repo = _build_service(
            db_session,
            _hr_only_parsed(_SHORT_DURATION),
            object_storage,
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        assert result.created is False
        assert result.reason == "short_stream"

        # No row, no version transition.
        assert await raw_repo.get_by_activity_id(activity.id) is None
        refreshed = await activity_repo.get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version is None


# ---------------------------------------------------------------------------
# Test: idempotency against real DB — UNIQUE constraint enforcement.
# ---------------------------------------------------------------------------

class TestCleanIdempotencyAtDb:
    """A second clean() call against an already-cleaned activity is
    idempotent at the DB layer — the UNIQUE constraint on
    ``activity_id`` would otherwise reject the second insert."""

    @pytest.mark.asyncio
    async def test_second_clean_returns_already_cleaned_no_second_row(
        self, db_session: AsyncSession
    ) -> None:
        """Two consecutive ``clean()`` calls produce exactly one
        ``RawSensorStream`` row. The second call returns
        ``created=False, reason="already_cleaned"``."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        service1, _, _, _ = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        first = await service1.clean(activity.id)
        await db_session.commit()
        assert first.created is True

        # A fresh service for the second call (simulating a retry task).
        service2, _, _, _ = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        second = await service2.clean(activity.id)
        await db_session.commit()

        assert second.created is False
        assert second.reason == "already_cleaned"

        # Exactly one row.
        result = await db_session.execute(
            select(RawSensorStream).where(
                RawSensorStream.activity_id == activity.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Test: retry idempotency — ObjectStorageConflictError on second upload.
# ---------------------------------------------------------------------------

class TestCleanRetryIdempotencyAtStorage:
    """The retry path: cleaned stream already exists in object storage
    (from a partial commit) — the second ``clean`` call hits
    ``ObjectStorageConflictError`` on upload, which the service
    converts to success and continues to insert/update."""

    @pytest.mark.asyncio
    async def test_object_storage_conflict_is_treated_as_idempotent_success(
        self, db_session: AsyncSession
    ) -> None:
        """Pre-stage the cleaned-stream key in object storage, then
        run the service. The first ``upload_cleaned_stream`` call
        raises ``ObjectStorageConflictError``; the service treats
        it as success, inserts the row, and updates the version."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # Pre-upload the cleaned stream to the deterministic key.
        pre_key = object_storage.build_cleaned_stream_key(
            athlete_id=athlete.id, activity_id=activity.id
        )
        await object_storage.upload_cleaned_stream(
            athlete_id=athlete.id,
            activity_id=activity.id,
            payload_bytes=b"PRE-EXISTING CLEANED STREAM",
        )

        service, _, raw_repo, activity_repo = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        # The conflict IS the idempotency outcome — the service
        # must still create the row and update the version.
        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None
        refreshed = await activity_repo.get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version == PIPELINE_VERSION

        # The pre-staged payload is preserved — the conflict
        # path does NOT overwrite the existing object.
        preserved = await object_storage.download_cleaned_stream(pre_key)
        assert preserved == b"PRE-EXISTING CLEANED STREAM"


# ---------------------------------------------------------------------------
# Test: RR ±20% rolling-median deviation filter (integration target).
# ---------------------------------------------------------------------------

class TestCleanRrRollingMedianFilter:
    """The ±20% rolling-median deviation criterion for RR intervals
    (Phase-2.2-P2 MAJOR fix).

    Engineered RR series: 299 conformant 1000 ms baselines, one
    1300 ms spike at index 299 (+30% deviation), then 300
    conformant 1000 ms baselines. The first-stage 200/2500 ms
    hard bound is not violated by the spike (1300 ms is well
    within [200, 2500]), so the only way the spike is filtered
    out is the ±20% rolling-median deviation rule.

    The deviation check lives inside ``_remove_artifacts`` (the
    architecture contract states the ±20% rule is a follow-on to
    the bounds check, not a separately-named pipeline step). RR
    is NOT smoothed by the pipeline, so the deviation-filtered
    series is what the cleaned record carries directly — there
    is no null-propagation through smoothing to confound the
    assertions.

    Layer contract: real DB, real local-fallback
    ``ObjectStorageClient``, real ``SignalCleaningService``.
    Only the ``FitParserService`` is stubbed at the constructor
    boundary so the test can drive known ``ParsedFitData``
    scenarios. Persistence is verified by re-reading the
    cleaned stream from object storage and the ``RawSensorStream``
    row from the database.
    """

    @pytest.mark.asyncio
    async def test_rr_above_20pct_rolling_median_is_nulled(
        self, db_session: AsyncSession
    ) -> None:
        """An RR value that exceeds the rolling median by more than
        ±20% is nulled in the **persisted** cleaned stream, AND
        the records immediately before/after the spike are
        preserved (proving the filter, not smoothing, nulled it).

        Concretely: the spike is at index 299 (the 300th record
        in a 600-record series, 0-based). Its trailing
        ``RR_ROLLING_WINDOW_S``-sample window
        ``[max(0, 299-30):299] = [269:299]`` is 30 conformant
        1000 ms samples. The candidate (1300 ms) is excluded
        from the window per the architecture contract
        (the half-open slice ``[window_start:t]``). The median
        is 1000 ms, the deviation is
        ``|1300 − 1000| = 300 ms``, and the threshold is
        ``RR_DEVIATION_THRESHOLD × 1000 = 200 ms``. Since
        ``300 > 200`` the spike is nulled.

        Conforming records at indices 298, 300, 0, and 599 are
        all preserved because their windows lock to a median of
        1000 ms and the candidate equals the median (deviation
        = 0 < 200 ms).

        ``available_channels.rr_intervals`` stays ``True`` because
        only 1/600 records is nulled — well below the 80%
        unavailability threshold.
        """
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # 299 conformant baselines, 1 spike at index 299, 300
        # conformant baselines.
        spike_index = 299
        spike_value = 1300.0
        conformant = 1000.0
        rr_records: list[float] = (
            [conformant] * spike_index
            + [spike_value]
            + [conformant] * (_SUFFICIENT_DURATION - spike_index - 1)
        )
        # HR must be sufficient to pass the 5-minute gate; 600
        # samples of 150 bpm are well above the 300-second
        # minimum.
        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=[150.0] * _SUFFICIENT_DURATION,
            rr_records=cast(list[float | None], rr_records),
            has_hr=True,
            has_rr_intervals=True,
        )

        service, _, raw_repo, _ = _build_service(
            db_session, parsed, object_storage
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None

        # The cleaned stream's available_channels.rr_intervals
        # stays True because only 1/600 RR records is nulled —
        # well below the 80% unavailability threshold.
        available = row.available_channels
        assert available["rr_intervals"] is True

        # Direct proof at the persistence boundary: re-read the
        # cleaned stream from object storage and assert the
        # specific record at the spike position is null AND the
        # records at the indices immediately before and after
        # the spike are non-null.
        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        payload = json.loads(gzip.decompress(cleaned_bytes).decode("utf-8"))
        rr_series = [r["rr_ms"] for r in payload["time_series"]]

        # The spike at index 299 is nulled by the deviation filter.
        assert rr_series[spike_index] is None, (
            f"RR sample at index {spike_index} (the {spike_value} ms "
            f"spike, +{100*(spike_value-conformant)/conformant:.0f}% "
            f"deviation from {conformant} ms median) must be nulled "
            f"by the ±{RR_DEVIATION_THRESHOLD*100:.0f}% rolling-median "
            f"deviation filter"
        )

        # The record immediately BEFORE the spike (index 298) is
        # preserved — its trailing window is the same 30
        # conformant baselines, candidate equals the median,
        # deviation = 0.
        assert rr_series[spike_index - 1] == conformant, (
            f"RR sample at index {spike_index - 1} (a {conformant} ms "
            f"conformant baseline immediately before the spike) must "
            f"be preserved by the deviation filter"
        )

        # The record immediately AFTER the spike (index 300) is
        # preserved — its trailing window includes the (now-nulled)
        # spike at index 299, but the window filter strips None
        # values so the median over the remaining 29 baselines is
        # still {conformant} ms.
        assert rr_series[spike_index + 1] == conformant, (
            f"RR sample at index {spike_index + 1} (a {conformant} ms "
            f"conformant baseline immediately after the spike) must "
            f"be preserved — the nulled spike at index {spike_index} "
            f"is filtered out of the window before median computation"
        )

        # Records FAR from the spike are also preserved. The first
        # and last record are well outside the spike's ±30-sample
        # influence zone.
        assert rr_series[0] == conformant
        assert rr_series[_SUFFICIENT_DURATION - 1] == conformant

        # Sanity check on the constants used in the assertion —
        # if either changes, the test design changes with it.
        assert RR_DEVIATION_THRESHOLD == 0.20
        assert RR_ROLLING_WINDOW_S == 30
        # Threshold: 0.20 × 1000 = 200 ms; the spike's 300 ms
        # deviation strictly exceeds it.
        assert abs(spike_value - conformant) > RR_DEVIATION_THRESHOLD * conformant

    @pytest.mark.asyncio
    async def test_rr_deviation_filter_pushed_rr_intervals_to_unavailable(
        self, db_session: AsyncSession
    ) -> None:
        """The deviation filter's nulls are correctly counted in the
        ``available_channels.rr_intervals`` computation at the
        persistence boundary.

        This protects the invariant *"available_channels reflects
        what survived artifact removal"* and is Phase-2.2-P2
        Testing Requirement 5. The test exercises the
        integration-layer transaction contract: the deviation
        filter's nulls (computed in-memory) must propagate to
        the persisted ``available_channels`` JSONB column and
        contribute to the null-fraction gate.

        Construction: 480 hard-bound-null samples (``100 ms``,
        below the 200 ms lower bound) + 30 conformant baselines
        (800 ms) + 90 outliers (400 ms vs the 800 ms rolling
        median — a 50% deviation, well past the 20% threshold).

        Hard-bound pass nulls 480/600 = 80% strictly. The
        deviation pass then nulls every outlier whose trailing
        30-sample window contains enough conformant baselines
        to lock the median at 800 ms. With 30 baselines all at
        index 480–509 and 90 outliers at 510–599, every outlier
        at index 510–538 has a window with ≥ 1 conformant
        baseline and ≥ 2 non-null samples → median = 800 →
        candidate 400 ms deviates 50% → nulled. The last 61
        outliers (indices 539–599) have windows that contain
        only already-nulled outliers, so the ``len < 2`` guard
        fires and the candidates are preserved.

        Net effect: hard-bound nulls (480) + deviation nulls
        (~29) ≈ 509 nulls out of 600 ≈ 84.8% null. The
        available-channels rule ``non_null_fraction > 80%``
        fails, so ``rr_intervals=False``. The test asserts this
        at the persistence boundary (the row in the DB and the
        ``available_channels`` JSONB column).
        """
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # 480 hard-bound-null (100 ms < 200 ms lower bound) +
        # 30 conformant baselines (800 ms) + 90 outliers
        # (400 ms vs ~800 ms median → deviation 50%, well past
        # the 20% threshold).
        n_hard_null = 480
        n_baseline = 30
        n_outlier = 90
        assert n_hard_null + n_baseline + n_outlier == _SUFFICIENT_DURATION
        rr_records: list[float] = (
            [100.0] * n_hard_null
            + [800.0] * n_baseline
            + [400.0] * n_outlier
        )
        # HR must be sufficient to pass the 5-minute gate.
        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=[150.0] * _SUFFICIENT_DURATION,
            rr_records=cast(list[float | None], rr_records),
            has_hr=True,
            has_rr_intervals=True,
        )

        service, _, raw_repo, _ = _build_service(
            db_session, parsed, object_storage
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        # The HR gate is unaffected by the RR change, so a row
        # IS created. The persistence boundary is exercised.
        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None

        # The discriminator: the deviation filter's nulls ARE
        # counted in the available_channels JSONB column. The
        # post-P2 null fraction is 509/600 = 84.8%, well past
        # the strict 80% non-null threshold → ``rr_intervals``
        # is False. This is a direct, isolated proof that the
        # deviation filter's nulls propagate to the persistence
        # boundary (the only thing the P2 plan changed in the
        # pipeline is the addition of the deviation pass).
        available = row.available_channels
        assert available["rr_intervals"] is False, (
            "available_channels.rr_intervals must be False when the "
            "deviation filter nulls enough in-bound samples to push "
            "the post-artifact null fraction past 80% (Phase-2.2-P2 "
            "Testing Requirement 5). The deviation filter's nulls "
            "must propagate to the available_channels JSONB column "
            "at the persistence boundary."
        )

        # Direct proof: re-read the cleaned stream from object
        # storage and assert the cumulative null fraction is
        # well past 80%. This confirms the deviation filter
        # fired at the persistence boundary (not just
        # in-memory).
        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        payload = json.loads(gzip.decompress(cleaned_bytes).decode("utf-8"))
        rr_series = [r["rr_ms"] for r in payload["time_series"]]
        null_count = sum(1 for v in rr_series if v is None)
        # Pre-P2: only the 480 hard-bound nulls → 480/600 = 80%
        # null. Post-P2: 480 hard-bound + ~29 deviation nulls
        # → 509/600 = 84.8% null. The test asserts the
        # post-P2 state at the persistence boundary.
        assert null_count > 480, (
            f"expected the deviation filter to null at least one "
            f"in-bound sample (post-P2 null count > 480); got "
            f"{null_count} nulls out of {len(rr_series)} records"
        )
        assert null_count / len(rr_series) > 0.80, (
            f"expected the cumulative post-P2 null fraction to "
            f"exceed 80%; got {null_count}/{len(rr_series)} = "
            f"{100*null_count/len(rr_series):.2f}%"
        )

    @pytest.mark.asyncio
    async def test_rr_deviation_filter_skips_when_window_too_small(
        self, db_session: AsyncSession
    ) -> None:
        """The deviation filter's ``len(window_values) < 2`` guard
        preserves the candidate when the trailing 30-sample window
        has fewer than 2 non-null RR samples.

        This is Phase-2.2-P2 Testing Requirement 4 (null-propagation
        guard) — the test exercises the integration-layer transaction
        contract for the rule, not just the in-memory logic. The
        service must NOT write nulled values to the persisted
        cleaned stream for samples that the guard skipped.

        Construction: 30 leading nulls (so the trailing window for
        any early candidate is empty or has 1 sample → guard fires)
        + 5 conformant 800 ms samples (clustered so the candidates
        are tested against the window guard) + 565 trailing nulls.

        The 5 conformant samples are preserved because their
        trailing windows have < 2 non-null samples at the start of
        the cluster and exactly 2-5 non-null samples within the
        cluster — every conformant candidate equals its window
        median (800 ms), so the deviation check is satisfied even
        when it does fire. The test's primary assertion is on the
        FIRST sample at index 30: the deviation check is skipped
        for it (``len < 2``), the candidate is preserved.
        """
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # 30 leading nulls + 5 conformant 800 ms + 565 trailing
        # nulls. The 5 conformant samples live at indices
        # 30, 31, 32, 33, 34.
        n_leading_nulls = 30
        n_conformant = 5
        conformant = 800.0
        n_trailing_nulls = (
            _SUFFICIENT_DURATION - n_leading_nulls - n_conformant
        )
        rr_records: list[Optional[float]] = (
            [None] * n_leading_nulls
            + [conformant] * n_conformant
            + [None] * n_trailing_nulls
        )
        # HR must be sufficient to pass the 5-minute gate.
        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=[150.0] * _SUFFICIENT_DURATION,
            rr_records=rr_records,  # type: ignore[arg-type]
            has_hr=True,
            has_rr_intervals=True,
        )

        service, _, raw_repo, _ = _build_service(
            db_session, parsed, object_storage
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        # HR gate satisfied → row created. The 5 conformant RR
        # samples alone are insufficient for the > 20% non-null
        # rule, so rr_intervals will be False — that's correct,
        # the channel IS effectively unavailable. The test
        # asserts the persistence boundary:
        # the 5 candidates are preserved as 800.0 in the
        # cleaned stream, not nulled by the deviation filter.
        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None
        # Channel availability reflects the high null fraction.
        assert row.available_channels["rr_intervals"] is False

        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        payload = json.loads(gzip.decompress(cleaned_bytes).decode("utf-8"))
        rr_series = [r["rr_ms"] for r in payload["time_series"]]

        # All 5 conformant samples are preserved at the
        # persistence boundary. The deviation filter's
        # ``len(window_values) < 2`` guard prevented any of them
        # from being nulled.
        for i in range(n_leading_nulls, n_leading_nulls + n_conformant):
            assert rr_series[i] == conformant, (
                f"RR sample at index {i} (a {conformant} ms conformant "
                f"baseline) must be preserved by the deviation filter — "
                f"its trailing window has < 2 non-null samples at the "
                f"start of the cluster, triggering the guard, and "
                f"equal-to-median samples within the cluster pass the "
                f"deviation check"
            )

        # The nulls propagate as nulls — the candidate is not
        # filled in by any pipeline step. The deviation filter
        # is the only artifact-removal touch on RR, and it
        # never overwrites a None with a value.
        assert rr_series[0] is None
        assert rr_series[n_leading_nulls - 1] is None
        assert (
            rr_series[n_leading_nulls + n_conformant] is None
        )
        assert rr_series[_SUFFICIENT_DURATION - 1] is None

    @pytest.mark.asyncio
    async def test_rr_deviation_filter_does_not_affect_hr_persistence(
        self, db_session: AsyncSession
    ) -> None:
        """The RR deviation filter is RR-specific: it does not null
        HR, power, speed, or elevation records that fall inside
        their own hard bounds but deviate > 20% from their local
        median. This test exercises the filter-isolation guard at
        the integration layer (Phase-2.2-P2 Testing Requirement 3).

        Construction: a series where HR has a single 100 bpm sample
        among 150 bpm baselines (HR is in [30, 220] bpm hard bound
        but deviates by 33% from its 150 bpm median — the RR
        filter would null it if the filter were applied to HR),
        AND RR has the same 400 ms spike among 800 ms baselines
        pattern that the unit test uses. The HR sample at the
        spike position must be preserved; the RR sample at the
        spike position must be nulled.

        Concretely: index 31 (well inside the trailing-30 RR
        window for the conformant baselines) carries a
        100 bpm HR spike and a 400 ms RR spike. After cleaning:
            * ``rr_series[31]`` is ``None`` (RR filter fired)
            * ``hr_series[31]`` is non-null (HR filter did NOT
              fire — the 100 bpm is inside the [30, 220] bpm
              hard bound and the RR-specific filter does not
              apply to HR)
            * ``hr_series[30]`` and ``hr_series[32]`` are
              non-null (no bleed)
        """
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # HR: 31 conformant 150 bpm baselines, one 100 bpm
        # "spike" at index 31 (inside the HR hard bound but
        # 33% below the rolling median), then 568 conformant
        # 150 bpm. The 100 bpm value is preserved by the
        # pipeline (the RR filter does not apply to HR).
        hr_spike_index = 31
        hr_records: list[float] = (
            [150.0] * hr_spike_index
            + [100.0]
            + [150.0] * (_SUFFICIENT_DURATION - hr_spike_index - 1)
        )
        # RR: 31 conformant 800 ms baselines, one 400 ms spike
        # at index 31, then 568 conformant 800 ms. The 400 ms
        # is inside the [200, 2500] ms hard bound but is
        # nulled by the deviation filter.
        rr_spike_index = 31
        rr_records: list[float] = (
            [800.0] * rr_spike_index
            + [400.0]
            + [800.0] * (_SUFFICIENT_DURATION - rr_spike_index - 1)
        )

        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=cast(list[float | None], hr_records),
            rr_records=cast(list[float | None], rr_records),
            has_hr=True,
            has_rr_intervals=True,
        )

        service, _, raw_repo, _ = _build_service(
            db_session, parsed, object_storage
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        # HR gate satisfied → row created. Both channels carry
        # data → both are "available" (HR null fraction is
        # ~0%; RR null fraction is 1/600 = 0.17%, well below
        # 80%).
        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None
        available = row.available_channels
        assert available["hr"] is True
        assert available["rr_intervals"] is True

        # Re-read the cleaned stream and assert at the
        # persistence boundary.
        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        payload = json.loads(gzip.decompress(cleaned_bytes).decode("utf-8"))
        hr_series = [r["hr_bpm"] for r in payload["time_series"]]
        rr_series = [r["rr_ms"] for r in payload["time_series"]]

        # The RR spike at index 31 is nulled by the deviation
        # filter.
        assert rr_series[rr_spike_index] is None, (
            f"RR sample at index {rr_spike_index} (the 400 ms spike, "
            f"-50% deviation from 800 ms median) must be nulled by "
            f"the ±{RR_DEVIATION_THRESHOLD*100:.0f}% rolling-median "
            f"deviation filter"
        )
        # The HR value at index 31 is NOT nulled. The HR EMA
        # smoothing step modifies the value but never nulls
        # it — the EMA null-carry-forward only fires when the
        # input is null, and the 100 bpm is non-null. The
        # smoothed value is finite (the HR EMA is α=0.1
        # against a 150 bpm previous, so the smoothed value
        # is ~145 bpm; the precise value is not the point).
        assert hr_series[hr_spike_index] is not None, (
            f"HR sample at index {hr_spike_index} (the 100 bpm value, "
            f"inside the [30, 220] bpm hard bound) must be retained "
            f"by the pipeline — the RR-specific deviation filter does "
            f"NOT apply to HR (Phase-2.2-P2 Testing Requirement 3)"
        )
        # Neighbours of the HR spike are not nulled either —
        # the RR filter did not bleed into the HR channel.
        assert hr_series[hr_spike_index - 1] is not None
        assert hr_series[hr_spike_index + 1] is not None
        # Conforming RR samples far from the spike are preserved.
        assert rr_series[0] == 800.0
        assert rr_series[_SUFFICIENT_DURATION - 1] == 800.0
        # The RR samples immediately around the spike are
        # preserved (only the spike itself is nulled).
        assert rr_series[rr_spike_index - 1] == 800.0
        assert rr_series[rr_spike_index + 1] == 800.0

        # Sanity check on the bounds used in the construction.
        assert RR_MIN_MS <= 400.0 <= RR_MAX_MS  # RR spike inside hard bound
        assert 30 <= 100.0 <= 220  # HR spike inside HR hard bound


# ---------------------------------------------------------------------------
# Test: Gen-1 population GAP formula accuracy (integration target).
# ---------------------------------------------------------------------------

class TestCleanGapFormulaAccuracy:
    """Verify the GAP formula ``gap = raw_pace / (1 + a*grade + b*grade²)``
    produces the documented numerical result for known inputs.

    Setup: a flat-grade GPS run and an uphill GPS run. For the
    flat run, ``grade = 0`` and the formula reduces to
    ``gap = raw_pace`` — assert that the service's
    ``gap_sec_per_km`` matches ``raw_pace`` for the flat run. For
    the uphill run, compute the expected ``gap`` from the
    formula with the documented coefficients and compare to the
    service output within a small tolerance (the service applies
    Savitzky-Golay smoothing to GAP which slightly attenuates the
    value at the boundary; the *interior* of the run is
    unaffected).
    """

    @pytest.mark.asyncio
    async def test_gap_equals_raw_pace_for_flat_grade(
        self, db_session: AsyncSession
    ) -> None:
        """Flat grade → ``gap_sec_per_km`` equals ``raw_pace`` (no
        grade correction)."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # 3 m/s → 1000/3 ≈ 333.33 sec/km raw pace.
        speed_m_s = 3.0
        raw_pace_sec_per_km = 1000.0 / speed_m_s  # 333.333...

        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=[150.0] * _SUFFICIENT_DURATION,
            gps_records=_gps_running_flat(_SUFFICIENT_DURATION, speed_m_s=speed_m_s),
            has_hr=True,
            has_gps=True,
        )

        service, _, raw_repo, _ = _build_service(
            db_session, parsed, object_storage
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None

        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        payload = json.loads(gzip.decompress(cleaned_bytes).decode("utf-8"))
        # Pick a record in the middle of the run (away from the
        # Savitzky-Golay boundary effects).
        middle = payload["time_series"][
            _SUFFICIENT_DURATION // 2
        ]
        gap = middle["gap_sec_per_km"]
        assert gap is not None
        # Flat grade: gap must equal raw_pace. Tolerance 1% to
        # absorb float rounding.
        assert abs(gap - raw_pace_sec_per_km) / raw_pace_sec_per_km < 0.01, (
            f"flat-grade GAP {gap} deviates from raw_pace "
            f"{raw_pace_sec_per_km:.3f} by more than 1%"
        )

    @pytest.mark.asyncio
    async def test_gap_matches_formula_for_uphill_grade(
        self, db_session: AsyncSession
    ) -> None:
        """Uphill grade: ``gap_sec_per_km`` matches
        ``raw_pace / (1 + a*grade + b*grade²)`` with the documented
        coefficients. The exact expected value is computed from the
        engineered GPS series."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        speed_m_s = 3.0
        raw_pace_sec_per_km = 1000.0 / speed_m_s
        elevation_gain_m = 30.0
        # Total distance covered at constant speed over the run.
        total_distance_m = speed_m_s * _SUFFICIENT_DURATION
        grade_pct = (elevation_gain_m / total_distance_m) * 100.0
        expected_gap = raw_pace_sec_per_km / (
            1.0
            + GAP_COEFFICIENT_A * grade_pct
            + GAP_COEFFICIENT_B * (grade_pct ** 2)
        )

        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=_SUFFICIENT_DURATION,
            hr_records=[150.0] * _SUFFICIENT_DURATION,
            gps_records=_gps_running_uphill(
                _SUFFICIENT_DURATION,
                speed_m_s=speed_m_s,
                elevation_gain_m=elevation_gain_m,
            ),
            has_hr=True,
            has_gps=True,
        )

        service, _, raw_repo, _ = _build_service(
            db_session, parsed, object_storage
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        assert result.created is True
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None

        cleaned_bytes = await object_storage.download_cleaned_stream(
            row.fit_file_key
        )
        payload = json.loads(gzip.decompress(cleaned_bytes).decode("utf-8"))
        middle = payload["time_series"][
            _SUFFICIENT_DURATION // 2
        ]
        gap = middle["gap_sec_per_km"]
        assert gap is not None
        # The smoothed GAP is the Savitzky-Golay output — the
        # constant-grade signal is preserved exactly, but we
        # tolerate 2% to absorb the very first and last
        # boundary records that contaminate the smoothed series.
        assert abs(gap - expected_gap) / expected_gap < 0.02, (
            f"uphill GAP {gap:.3f} deviates from formula value "
            f"{expected_gap:.3f} by more than 2%"
        )


# ---------------------------------------------------------------------------
# Test: HR dropout flag does not block cleaning.
# ---------------------------------------------------------------------------

class TestCleanHrDropoutDoesNotBlock:
    """``quality_flags.hr_dropout_pct`` is informational only."""

    @pytest.mark.asyncio
    async def test_high_hr_dropout_still_produces_raw_sensor_stream(
        self, db_session: AsyncSession
    ) -> None:
        """An activity with ``hr_dropout_pct = 0.5`` (50% HR
        dropout) still gets cleaned and a ``RawSensorStream`` is
        created. The dropout flag is informational — cleaning is
        gated on post-artifact null fraction, not on the
        pre-existing dropout flag."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
            quality_flags={"hr_dropout_pct": 0.5},
        )
        await db_session.commit()

        service, _, raw_repo, _ = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        result = await service.clean(activity.id)
        await db_session.commit()

        assert result.created is True
        assert await raw_repo.get_by_activity_id(activity.id) is not None


# ---------------------------------------------------------------------------
# Test: available_channels reflects post-artifact null fraction.
# ---------------------------------------------------------------------------

class TestCleanAvailableChannelsPersisted:
    """``available_channels`` is persisted as a JSONB dict with the
    expected boolean shape — true if the channel survived artifact
    removal with ≤ 80% null fraction, false otherwise."""

    @pytest.mark.asyncio
    async def test_available_channels_shape_and_values(
        self, db_session: AsyncSession
    ) -> None:
        """``available_channels`` is a dict with keys ``hr``,
        ``rr_intervals``, ``power``, ``pace``, ``cadence``,
        ``elevation`` — all booleans. For an HR-only stream,
        ``hr=True`` and the rest are ``False`` (or ``False`` for
        cadence per the documented deferral)."""
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        service, _, raw_repo, _ = _build_service(
            db_session,
            _hr_only_parsed(_SUFFICIENT_DURATION),
            object_storage,
        )
        await service.clean(activity.id)
        await db_session.commit()

        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None
        available = row.available_channels
        assert set(available.keys()) == {
            "hr",
            "rr_intervals",
            "power",
            "pace",
            "cadence",
            "elevation",
        }
        assert available["hr"] is True
        assert available["cadence"] is False  # deferred in Phase-2.2
        # Channels with no input data → false.
        assert available["rr_intervals"] is False
        assert available["power"] is False
        assert available["pace"] is False
        assert available["elevation"] is False
