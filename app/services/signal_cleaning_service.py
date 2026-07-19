"""Execute the 7-step signal-cleaning pipeline."""

from __future__ import annotations

import gzip
import json
import math
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, cast

from scipy.signal import savgol_filter
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_utils import log_event
from app.models.enums import ActivitySource, SportType
from app.models.raw_sensor_stream import RawSensorStream
from app.repositories.activity_repository import ActivityRepository
from app.repositories.raw_sensor_stream_repository import (
    RawSensorStreamRepository,
)
from app.services.fit_parser_service import (
    FitParserService,
    ParsedFitData,
)
from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageConflictError,
)


# ---------------------------------------------------------------------------
# Frozen module constants.
# ---------------------------------------------------------------------------

#: Pipeline version frozen at module scope. A future algorithm
#: change increments this string and re-cleaning produces a new
#: ``RawSensorStream`` row with the new version (per ADR-009
#: tradeoff: the cleaned-stream key would then need a version
#: suffix; this is a future decision, recorded in the ADR).
PIPELINE_VERSION: str = "v1-signal-cleaning"

#: Gen-1 population GAP coefficients verbatim from
#: ``docs/architecture/02-computations/effort-normalisation.md``.
#: Inlined here (not promoted to a service) per the plan's
#: Implementation Clarifications — no second consumer exists yet.
#: A future extraction has an unambiguous anchor in this docstring.
GAP_COEFFICIENT_A: float = 0.033
GAP_COEFFICIENT_B: float = 0.00012

#: Artifact-removal thresholds from
#: ``docs/architecture/02-computations/signal-cleaning.md`` step 1.
HR_MIN_BPM: int = 30
HR_MAX_BPM: int = 220
POWER_ROLLING_WINDOW_S: int = 30
SPEED_MAX_M_S: float = 25.0
RR_MIN_MS: float = 200.0
RR_MAX_MS: float = 2500.0
#: RR rolling-median deviation filter (follow-on to the hard bound).
#: See ``docs/architecture/02-computations/signal-cleaning.md`` Step 1
#: ("RR deviation check" section) and
#: ``docs/architecture/02-computations/threshold-detection.md``
#: Algorithm 2 consumer contract: "values outside ±20% of rolling
#: median removed". ``RR_ROLLING_WINDOW_S`` is the trailing window
#: size in seconds — at the 1 Hz resampled rate this is 30 samples,
#: matching the power-artifact rolling window. ``RR_DEVIATION_THRESHOLD``
#: is the ±20% deviation fraction: a sample is nulled if
#: ``abs(sample - rolling_median) > 0.20 * rolling_median``. These
#: constants are the future extraction anchor if the threshold is
#: ever promoted to a per-athlete value in ``ThresholdDetectionService``.
RR_ROLLING_WINDOW_S: int = 30
RR_DEVIATION_THRESHOLD: float = 0.20

#: Smoothing parameters from
#: ``docs/architecture/02-computations/signal-cleaning.md`` step 2.
HR_EMA_ALPHA: float = 0.1
SAVGOL_WINDOW: int = 7
SAVGOL_POLYORDER: int = 3

#: Available-channels null-fraction threshold from the pipeline
#: invariant: "A channel with > 80% null values after artifact
#: removal is marked unavailable in ``AvailableChannels``."
NULL_FRACTION_UNAVAILABLE_THRESHOLD: float = 0.80

#: Minimum non-null HR seconds for a stream to be persisted (5 min).
MIN_NON_NULL_HR_SECONDS: int = 300

#: Coefficient-of-variation window (variability index).
VARIABILITY_WINDOW_S: int = 30

#: Rolling-feature window sizes from
#: ``docs/architecture/02-computations/signal-cleaning.md`` step 4.
ROLLING_WINDOWS_S: Sequence[int] = (30, 60, 120)


# ---------------------------------------------------------------------------
# Result types.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AvailableChannels:
    """Per-channel availability flags persisted on ``RawSensorStream``.

    Mirrors the shape in
    ``docs/architecture/01-entities/raw-sensor-stream.md`` exactly.
    """

    hr: bool
    rr_intervals: bool
    power: bool
    pace: bool
    cadence: bool
    elevation: bool

    def to_dict(self) -> Dict[str, bool]:
        return {
            "hr": self.hr,
            "rr_intervals": self.rr_intervals,
            "power": self.power,
            "pace": self.pace,
            "cadence": self.cadence,
            "elevation": self.elevation,
        }


@dataclass(frozen=True)
class CleanedRecord:
    """One second of the cleaned time-series.

    All signal fields are ``Optional[float]``; ``None`` propagates
    through the pipeline per the null-propagation invariant.
    """

    t: int
    hr_bpm: Optional[float]
    rr_ms: Optional[float]
    power_w: Optional[float]
    gap_sec_per_km: Optional[float]
    cadence_rpm: Optional[float]
    elevation_m: Optional[float]
    grade_pct: Optional[float]
    variability_index: Optional[float]
    hr_30s_mean: Optional[float]
    hr_60s_mean: Optional[float]
    hr_120s_mean: Optional[float]
    power_30s_mean: Optional[float]
    gap_30s_mean: Optional[float]


@dataclass(frozen=True)
class CleanedStream:
    """Structured time-series output of steps 1–4.

    Mirrors the TypeScript schema in
    ``docs/architecture/02-computations/signal-cleaning.md`` exactly.
    Serialised to gzipped JSON and uploaded to object storage by
    :meth:`SignalCleaningService.clean` after the gates pass.
    """

    time_series: List[CleanedRecord]
    sampling_rate_hz: float
    available_channels: AvailableChannels

    def to_json_bytes(self) -> bytes:
        """Serialise to JSON bytes for compression."""
        return json.dumps(
            {
                "time_series": [_record_to_dict(r) for r in self.time_series],
                "sampling_rate_hz": self.sampling_rate_hz,
                "available_channels": self.available_channels.to_dict(),
            },
            separators=(",", ":"),
        ).encode("utf-8")


def _record_to_dict(record: CleanedRecord) -> Dict[str, object]:
    return {
        "t": record.t,
        "hr_bpm": record.hr_bpm,
        "rr_ms": record.rr_ms,
        "power_w": record.power_w,
        "gap_sec_per_km": record.gap_sec_per_km,
        "cadence_rpm": record.cadence_rpm,
        "elevation_m": record.elevation_m,
        "grade_pct": record.grade_pct,
        "variability_index": record.variability_index,
        "hr_30s_mean": record.hr_30s_mean,
        "hr_60s_mean": record.hr_60s_mean,
        "hr_120s_mean": record.hr_120s_mean,
        "power_30s_mean": record.power_30s_mean,
        "gap_30s_mean": record.gap_30s_mean,
    }


@dataclass(frozen=True)
class CleaningResult:
    """Outcome of a :meth:`SignalCleaningService.clean` call.

    The ``created`` flag is the success signal consumed by the
    procrastinate ``signal_clean`` worker task. ``reason`` is set
    on the no-op and short-stream paths so observability can
    distinguish "already cleaned (retry)" from "stream too short".
    """

    created: bool
    reason: Optional[str] = None
    stream: Optional[CleanedStream] = None
    raw_sensor_stream_id: Optional[uuid.UUID] = None


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class SignalCleaningError(Exception):
    """Base class for signal-cleaning failures."""


class SignalCleaningNotFoundError(SignalCleaningError):
    """The activity does not exist; the worker surfaces a 404-style
    error to procrastinate so the task is not retried forever."""


class SignalCleaningIneligibleError(SignalCleaningError):
    """The activity is not eligible for cleaning (not calibration-
    eligible, not running, or otherwise failed the gate). The worker
    surfaces this to procrastinate so a stale queue entry does not
    corrupt state."""


# ---------------------------------------------------------------------------
# Internal intermediate types.
# ---------------------------------------------------------------------------


@dataclass
class _ResampledChannel:
    """Per-second channel arrays after step 1 (resampling)."""

    duration: int
    hr: List[Optional[float]] = field(default_factory=list)
    power: List[Optional[float]] = field(default_factory=list)
    rr: List[Optional[float]] = field(default_factory=list)
    speed_m_s: List[Optional[float]] = field(default_factory=list)
    elevation_m: List[Optional[float]] = field(default_factory=list)
    grade_pct: List[Optional[float]] = field(default_factory=list)


@dataclass
class _DerivedChannel:
    """Per-second arrays extended with derived metrics after step 3.

    Carries the fields that step 3 computes (gap_sec_per_km,
    grade_pct) alongside the smoothed channels from step 2. The
    rolling-features step reads this and emits :class:`CleanedRecord`.
    """

    duration: int
    hr: List[Optional[float]]
    rr: List[Optional[float]]
    power: List[Optional[float]]
    speed_m_s: List[Optional[float]]
    elevation_m: List[Optional[float]]
    grade_pct: List[Optional[float]]
    gap_sec_per_km: List[Optional[float]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class SignalCleaningService:
    """Execute the Phase-2.2 signal-cleaning pipeline for one activity.

    The service is the single owner of step-1–4 logic. The pipeline
    order is enforced by the call sequence in :meth:`clean`; there
    is no dispatcher helper that could be re-ordered.

    Construction is dependency-injected: the service holds an
    :class:`ObjectStorageClient`, a :class:`RawSensorStreamRepository`,
    an :class:`ActivityRepository`, and a :class:`FitParserService`.
    The :class:`AsyncSession` parameter is retained for API stability
    (the worker passes it positionally) and flows through to the
    injected repositories which hold it; the service does not store
    a direct reference.

    The :class:`FitParserService` is re-parsed on each cleaning run
    (Phase-2.2 does not stash parsed records across services).

    The service is safe to construct once per procrastinate task
    invocation. The constructor performs no I/O.
    """

    def __init__(
        self,
        *,
        session: AsyncSession,
        object_storage: ObjectStorageClient,
        raw_stream_repository: RawSensorStreamRepository,
        activity_repository: ActivityRepository,
        fit_parser: FitParserService,
    ) -> None:
        # NOTE: the `session` parameter is retained because the
        # worker constructs the service with `session=session` and
        # the repositories hold the session internally. The service
        # does not store a direct reference to the session — the
        # validation report flagged `self._session` as dead.
        self.object_storage = object_storage
        self.raw_streams = raw_stream_repository
        self.activities = activity_repository
        self.fit_parser = fit_parser

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------

    async def clean(self, activity_id: uuid.UUID) -> CleaningResult:
        """Clean the activity's raw FIT into a ``RawSensorStream``.

        Steps in fixed order, enforced by call sequence:

        1. :meth:`_resample_to_1hz`
        2. :meth:`_remove_artifacts`
        3. :meth:`_smooth`
        4. :meth:`_compute_derived_metrics`
        5. :meth:`_compute_rolling_features`

        After step 5, the gates are evaluated: ``available_channels``
        is computed from per-channel null fractions and the
        5-minute non-null HR gate is enforced. If a gate fails, no
        row is written and a :class:`CleaningResult` with
        ``created=False`` is returned. If all gates pass, the
        cleaned stream is serialised, uploaded, the
        ``RawSensorStream`` row is inserted, and
        ``Activity.cleaning_pipeline_version`` is updated — all
        sharing the caller's transaction (the worker commits once).

        Guards:

        * Missing activity → :class:`SignalCleaningNotFoundError`.
        * ``source = manual_entry`` → ``CleaningResult(created=False,
          reason="manual_entry")`` no-op.
        * ``RawSensorStream`` already exists →
          ``CleaningResult(created=False, reason="already_cleaned")``
          idempotent success.
        * ``calibration_eligible = false`` or
          ``sport_type != running`` →
          :class:`SignalCleaningIneligibleError`.

        Raises:
            SignalCleaningNotFoundError: activity does not exist.
            SignalCleaningIneligibleError: stale queue entry — the
                activity is not calibration-eligible or not running.
            FitParseError: the FIT file is corrupt / unsupported.
                Propagates so the worker retries per procrastinate
                backoff.
            ObjectStorageConflictError: not raised — the conflict
                is the idempotency outcome on retry and is caught
                internally.
        """
        activity = await self.activities.get_by_id(activity_id)
        if activity is None:
            raise SignalCleaningNotFoundError(
                f"activity {activity_id} does not exist"
            )

        # Defence-in-depth: manual entries have no FIT.
        if activity.source == ActivitySource.MANUAL_ENTRY:
            log_event(
                event="signal_cleaning.skipped",
                activity_id=str(activity_id),
                outcome="skipped",
            )
            return CleaningResult(created=False, reason="manual_entry")

        # Idempotency: a row already exists → retry after a
        # partial-then-committed run. Return success without
        # re-running the pipeline.
        if await self.raw_streams.exists_for_activity(activity_id):
            log_event(
                event="signal_cleaning.skipped",
                activity_id=str(activity_id),
                outcome="already_cleaned",
            )
            return CleaningResult(
                created=False, reason="already_cleaned"
            )

        # Stale queue entries must not corrupt state.
        if (
            not activity.calibration_eligible
            or activity.sport_type != SportType.RUNNING
        ):
            raise SignalCleaningIneligibleError(
                f"activity {activity_id} is not eligible for cleaning "
                f"(calibration_eligible={activity.calibration_eligible}, "
                f"sport_type={activity.sport_type.value})"
            )

        fit_key = activity.fit_file_key
        if fit_key is None:
            # Non-manual activities always carry a fit_file_key by
            # the ingestion contract. Treat a missing key as a
            # worker-retryable state — the upload may not have
            # committed yet.
            raise SignalCleaningError(
                f"activity {activity_id} has no fit_file_key"
            )

        fit_bytes = await self.object_storage.download_fit(fit_key)
        parsed: ParsedFitData = await self.fit_parser.parse(fit_bytes)

        # Pipeline order is fixed — see the method docstring and
        # signal-cleaning.md step ordering. Each method's output is
        # the next method's input; the order is enforced by call
        # sequence, not by a dispatcher.
        resampled = self._resample_to_1hz(parsed)
        artifact_free = self._remove_artifacts(resampled)
        smoothed = self._smooth(artifact_free)
        derived = self._compute_derived_metrics(smoothed, artifact_free)
        features = self._compute_rolling_features(derived)

        # available_channels is computed from the post-artifact null
        # fractions; it feeds the threshold-detection consumer and
        # the persistence row.
        available = self._available_channels(artifact_free)

        # 5-minute non-null HR gate. Returning ``created=False`` here
        # is the explicit no-row signal: the activity stays with
        # ``cleaning_pipeline_version = null`` and segmentation will
        # skip it.
        non_null_hr_count = sum(
            1 for v in artifact_free.hr if v is not None
        )
        if non_null_hr_count < MIN_NON_NULL_HR_SECONDS:
            log_event(
                event="signal_cleaning.short_stream",
                activity_id=str(activity_id),
                outcome="skipped",
            )
            return CleaningResult(created=False, reason="short_stream")

        stream = CleanedStream(
            time_series=features,
            sampling_rate_hz=1.0,
            available_channels=available,
        )

        # Persist atomically: upload + insert + activity version
        # update share the caller's transaction. The cleaned-stream
        # key is derived deterministically from activity_id, so a
        # retry after a partial-then-committed upload hits
        # ``ObjectStorageConflictError`` — that conflict is the
        # idempotency outcome.
        key = self.object_storage.build_cleaned_stream_key(
            activity.athlete_id, activity.id
        )
        payload = gzip.compress(stream.to_json_bytes())
        try:
            await self.object_storage.upload_cleaned_stream(
                athlete_id=activity.athlete_id,
                activity_id=activity.id,
                payload_bytes=payload,
            )
        except ObjectStorageConflictError:
            # Idempotent retry — the cleaned stream is immutable and
            # the upload already succeeded on a prior attempt. The
            # subsequent insert + version update must still run to
            # close the transaction.
            log_event(
                event="signal_cleaning.upload_conflict_idempotent",
                activity_id=str(activity_id),
                outcome="success",
            )

        inserted = await self.raw_streams.insert(
            RawSensorStream(
                activity_id=activity.id,
                fit_file_key=key,
                sampling_rate_hz=1.0,
                available_channels=available.to_dict(),
                cleaning_pipeline_version=PIPELINE_VERSION,
            )
        )
        await self.activities.update_cleaning_version(
            activity_id=activity.id, version=PIPELINE_VERSION
        )

        log_event(
            event="signal_cleaning.success",
            activity_id=str(activity_id),
            outcome="success",
        )
        return CleaningResult(
            created=True,
            stream=stream,
            raw_sensor_stream_id=inserted.id,
        )

    # ------------------------------------------------------------------
    # Step 1 — Resample to 1 Hz.
    # ------------------------------------------------------------------

    def _resample_to_1hz(self, parsed: ParsedFitData) -> _ResampledChannel:
        """Materialise a uniform 1 Hz time index from 0…duration-1.

        Each channel is aligned onto the index; missing samples
        propagate as ``None`` per the null-propagation invariant.
        HR resampling only coerces timestamps; it does NOT invent
        HR values. Forward-fill is forbidden.

        Mapping rules:

        * ``hr_records`` (bpm) → ``hr`` aligned by t = 0, 1, 2…
        * ``power_records`` (W) → ``power`` aligned the same way
        * ``rr_records`` (ms) → ``rr`` aligned by source index
        * ``gps_records[i].speed`` (m/s) → ``speed_m_s`` aligned by
          source index; elevation from ``gps_records[i].altitude``;
          ``grade_pct`` is computed from the running elevation
          delta and the known per-second speed (when speed is
          available; otherwise grade stays null).
        """
        duration = max(0, int(parsed.duration_seconds))
        channel = _ResampledChannel(
            duration=duration,
            hr=[],
            power=[],
            rr=[],
            speed_m_s=[],
            elevation_m=[],
            grade_pct=[],
        )

        # Materialise the 1 Hz index. All channels start as null and
        # are filled only where the source provides a sample.
        nulls: List[Optional[float]] = [None] * duration
        channel.hr = list(nulls)
        channel.power = list(nulls)
        channel.rr = list(nulls)
        channel.speed_m_s = list(nulls)
        channel.elevation_m = list(nulls)
        channel.grade_pct = list(nulls)

        # ``hr_records`` is a per-second list of integer bpm. We
        # align by index — sample i corresponds to t = i.
        for i, value in enumerate(parsed.hr_records):
            if i >= duration:
                break
            if isinstance(value, (int, float)):
                channel.hr[i] = float(value)

        for i, value in enumerate(parsed.power_records):
            if i >= duration:
                break
            if isinstance(value, (int, float)):
                channel.power[i] = float(value)

        # ``rr_records`` is a flat list of intervals (ms) from the
        # parser; align by source index. The list is typically
        # 1/60th the rate of HR (one RR per beat), so we treat the
        # index-aligned value as best-effort; out-of-bounds samples
        # are dropped.
        for i, value in enumerate(parsed.rr_records):
            if i >= duration:
                break
            if isinstance(value, (int, float)):
                channel.rr[i] = float(value)

        # GPS records carry per-sample speed and altitude. Align by
        # source index; missing fields stay null.
        for i, gps in enumerate(parsed.gps_records):
            if i >= duration:
                break
            if isinstance(gps.speed, (int, float)):
                channel.speed_m_s[i] = float(gps.speed)
            if isinstance(gps.altitude, (int, float)):
                channel.elevation_m[i] = float(gps.altitude)

        # Compute grade_pct from per-second elevation delta over the
        # known per-second speed. Grade stays null when either
        # elevation delta or speed is unavailable; this keeps
        # downstream GAP computation well-defined.
        for t in range(duration):
            if t == 0:
                # First sample: grade undefined.
                continue
            elevation_curr = channel.elevation_m[t]
            elevation_prev = channel.elevation_m[t - 1]
            if elevation_curr is None or elevation_prev is None:
                # Missing elevation: grade undefined.
                continue
            speed = channel.speed_m_s[t]
            if speed is None or speed <= 0:
                continue
            elevation_delta = elevation_curr - elevation_prev
            # grade_pct = rise/run * 100, where run = speed * 1s
            channel.grade_pct[t] = (elevation_delta / speed) * 100.0

        return channel

    # ------------------------------------------------------------------
    # Step 1 (artifact removal) — separate from resampling so the
    # resampled arrays are preserved for the available_channels null
    # fraction evaluation that runs AFTER artifact removal.
    # ------------------------------------------------------------------

    def _remove_artifacts(
        self, resampled: _ResampledChannel
    ) -> _ResampledChannel:
        """Apply artifact-removal thresholds from signal-cleaning.md.

        Two-stage RR artifact removal:

        * HR null outside 30–220 bpm
        * Power null above 3× rolling-30s median
        * Speed null above 25 m/s (~90 km/h; GPS spike)
        * RR: hard bound 200–2500 ms, then ±20% rolling-median
          deviation filter (window=30 s, threshold=0.20); samples
          surviving the hard bound but deviating > ±20% from their
          trailing rolling median are nulled. This two-stage removal
          produces the cleaned RR series consumed by
          ``ThresholdDetectionService`` HRV-inflection step 1.

        References:

        * ``docs/architecture/02-computations/signal-cleaning.md``
          Step 1 (the updated two-stage RR artifact removal
          section)
        * ``docs/architecture/02-computations/threshold-detection.md``
          Algorithm 2 step 1: "values outside ±20% of rolling
          median removed" (the downstream consumer contract that
          the deviation filter serves)
        """
        artifact_free = _ResampledChannel(
            duration=resampled.duration,
            hr=list(resampled.hr),
            power=list(resampled.power),
            rr=list(resampled.rr),
            speed_m_s=list(resampled.speed_m_s),
            elevation_m=list(resampled.elevation_m),
            grade_pct=list(resampled.grade_pct),
        )

        n = resampled.duration
        for t in range(n):
            hr = artifact_free.hr[t]
            if hr is not None and (hr < HR_MIN_BPM or hr > HR_MAX_BPM):
                artifact_free.hr[t] = None

            speed = artifact_free.speed_m_s[t]
            if speed is not None and speed > SPEED_MAX_M_S:
                artifact_free.speed_m_s[t] = None

            rr = artifact_free.rr[t]
            if rr is not None and (rr < RR_MIN_MS or rr > RR_MAX_MS):
                artifact_free.rr[t] = None

        # Power artifact: null above 3× the rolling-30s median of
        # the non-null power samples. Compute the median on the
        # pre-artifact power series (so the artifact removal does
        # not poison the threshold itself); null the post-artifact
        # copy where the threshold fires.
        for t in range(n):
            power = resampled.power[t]
            if power is None:
                artifact_free.power[t] = None
                continue
            window_start = max(0, t - POWER_ROLLING_WINDOW_S + 1)
            window_values = [
                v
                for v in resampled.power[window_start : t + 1]
                if v is not None
            ]
            if not window_values:
                # No context to judge — keep the sample.
                continue
            median = _median(window_values)
            if power > 3 * median:
                artifact_free.power[t] = None

        # RR deviation artifact (follow-on to the hard bound). Null
        # samples that deviate more than ±20% from the trailing
        # rolling median. The window excludes the candidate sample
        # itself — otherwise a single extreme sample would pull the
        # median toward itself and the check would become a no-op
        # for exactly the samples it is meant to catch. This is the
        # critical difference from the power-artifact pass above
        # (power uses a 3× threshold where including the candidate
        # is safe; the RR 20% threshold does not tolerate that).
        for t in range(n):
            rr = artifact_free.rr[t]
            if rr is None:
                # Null-propagation: already-nulled samples stay null.
                continue
            window_start = max(0, t - RR_ROLLING_WINDOW_S)
            # Trailing samples BEFORE index t (half-open slice).
            # The candidate at t is excluded from the window.
            window_values = [
                v
                for v in artifact_free.rr[window_start:t]
                if v is not None
            ]
            if len(window_values) < 2:
                # Not enough context — keep the sample, consistent
                # with the power artifact's
                # ``if not window_values: continue`` guard.
                continue
            median = _median(window_values)
            if abs(rr - median) > RR_DEVIATION_THRESHOLD * median:
                artifact_free.rr[t] = None

        return artifact_free

    # ------------------------------------------------------------------
    # Step 2 — Smoothing / filtering.
    # ------------------------------------------------------------------

    def _smooth(self, resampled: _ResampledChannel) -> _ResampledChannel:
        """HR EMA α=0.1 (null carry-forward); power Savitzky-Golay.

        * HR: exponential moving average with α=0.1. Null inputs
          carry forward the last smoothed value (or stay null at
          the start of the series).
        * Power: Savitzky-Golay (window=7, poly=3). Implemented
          inline via ``scipy.signal.savgol_filter``; nulls are
          interpolated with the mean for the filter call, then
          re-nulled at the positions they were null. ``mode='nearest'``
          is used to extend the boundary samples so the smoothed
          output length matches the input length.
        * Pace is not present at this stage — pace is derived in
          step 3 from speed/grade. The Savitzky-Golay smoothing
          for pace is therefore applied in step 3 over
          ``raw_pace_sec_per_km`` (which lives on the derived
          record); see :meth:`_compute_derived_metrics`.
        """
        n = resampled.duration
        smoothed = _ResampledChannel(
            duration=n,
            hr=list(resampled.hr),
            power=list(resampled.power),
            rr=list(resampled.rr),
            speed_m_s=list(resampled.speed_m_s),
            elevation_m=list(resampled.elevation_m),
            grade_pct=list(resampled.grade_pct),
        )

        # HR EMA α=0.1 with null carry-forward of last smoothed value.
        last_smoothed: Optional[float] = None
        for t in range(n):
            v = resampled.hr[t]
            if v is None:
                # Null carry-forward: stay null at the start of the
                # series, otherwise repeat the last smoothed value.
                smoothed.hr[t] = last_smoothed
                continue
            if last_smoothed is None:
                # First non-null sample: no prior smoothed value,
                # so the EMA reduces to the sample itself.
                current = v
            else:
                # EMA: new = α * value + (1 - α) * prev
                current = HR_EMA_ALPHA * v + (1 - HR_EMA_ALPHA) * last_smoothed
            smoothed.hr[t] = current
            last_smoothed = current

        # Power Savitzky-Golay smoothing. Nulls are filled with the
        # mean of the present samples so the filter can run; the
        # original null positions are restored afterwards so the
        # null-propagation invariant is preserved. Requires
        # ``len(series) >= SAVGOL_WINDOW`` and at least one present
        # sample; otherwise the smoothing is skipped and the
        # smoothed.power channel mirrors the artifact_free power
        # channel.
        if n >= SAVGOL_WINDOW and any(
            v is not None for v in resampled.power
        ):
            present = [v for v in resampled.power if v is not None]
            mean_value = sum(present) / len(present)
            filled = [
                v if v is not None else mean_value for v in resampled.power
            ]
            filtered = cast(
                List[float],
                savgol_filter(
                    filled, SAVGOL_WINDOW, SAVGOL_POLYORDER, mode="nearest"
                ),
            )
            for t in range(n):
                if resampled.power[t] is None:
                    smoothed.power[t] = None
                else:
                    smoothed.power[t] = float(filtered[t])
        # else: power channel already mirrors artifact_free.power.

        return smoothed

    # ------------------------------------------------------------------
    # Step 3 — Derived metrics.
    # ------------------------------------------------------------------

    def _compute_derived_metrics(
        self,
        smoothed: _ResampledChannel,
        artifact_free: _ResampledChannel,
    ) -> _DerivedChannel:
        """Compute GAP (grade-adjusted pace) per record.

        GAP formula (Gen-1 population) from
        ``docs/architecture/02-computations/effort-normalisation.md``:

            correction_factor = 1 + a * grade_pct + b * grade_pct²
            gap_sec_per_km = raw_pace_sec_per_km / correction_factor

        where ``raw_pace_sec_per_km = 1000 / speed_m_s`` for
        ``speed_m_s > 0`` (null speed → null pace → null GAP).

        Grade comes from the smoothed channel when present,
        else falls back to the artifact_free grade, else to
        ``0.0`` (flat assumption when no GPS). Per the
        architecture corpus, "Raw pace is never used anywhere in
        the system" — the GAP field is the only pace ever
        persisted, never ``raw_pace``.

        The Savitzky-Golay smoothing for pace is applied here over
        ``raw_pace_sec_per_km`` (the inverse-speed raw pace),
        using the same window/polyorder as power; null raw paces
        are interpolated with the mean, smoothed, then re-nulled.
        """
        n = smoothed.duration
        derived = _DerivedChannel(
            duration=n,
            hr=list(smoothed.hr),
            rr=list(smoothed.rr),
            power=list(smoothed.power),
            speed_m_s=list(smoothed.speed_m_s),
            elevation_m=list(smoothed.elevation_m),
            grade_pct=list(smoothed.grade_pct),
            gap_sec_per_km=[None] * n,
        )

        # Compute raw pace and GAP for every record. Null where
        # speed is null or non-positive; grade falls back to 0
        # when no GPS-grade is available.
        raw_pace: List[Optional[float]] = [None] * n
        for t in range(n):
            speed = smoothed.speed_m_s[t]
            if speed is not None and speed > 0:
                raw_pace[t] = 1000.0 / speed
            else:
                raw_pace[t] = None

            grade = smoothed.grade_pct[t]
            if grade is None:
                grade = artifact_free.grade_pct[t] if t < len(artifact_free.grade_pct) else None
            if grade is None:
                grade = 0.0

            pace = raw_pace[t]
            if pace is not None:
                correction = 1.0 + GAP_COEFFICIENT_A * grade + GAP_COEFFICIENT_B * (grade ** 2)
                if correction == 0.0:
                    # Pathological grade (e.g. very large negative);
                    # fall back to raw pace.
                    derived.gap_sec_per_km[t] = pace
                else:
                    derived.gap_sec_per_km[t] = pace / correction
            else:
                derived.gap_sec_per_km[t] = None

        # Savitzky-Golay smoothing of GAP. Same null-fill / re-null
        # pattern as the power smoothing above. Requires the
        # standard conditions (window <= n, at least one present
        # sample); otherwise the gap channel is left as computed.
        if n >= SAVGOL_WINDOW and any(v is not None for v in derived.gap_sec_per_km):
            present = [v for v in derived.gap_sec_per_km if v is not None]
            mean_value = sum(present) / len(present)
            filled = [
                v if v is not None else mean_value for v in derived.gap_sec_per_km
            ]
            filtered = cast(
                List[float],
                savgol_filter(
                    filled, SAVGOL_WINDOW, SAVGOL_POLYORDER, mode="nearest"
                ),
            )
            for t in range(n):
                if derived.gap_sec_per_km[t] is None:
                    continue
                derived.gap_sec_per_km[t] = float(filtered[t])

        return derived

    # ------------------------------------------------------------------
    # Step 4 — Rolling features.
    # ------------------------------------------------------------------

    def _compute_rolling_features(
        self, derived: _DerivedChannel
    ) -> List[CleanedRecord]:
        """Compute 30/60/120-second rolling means and variability index.

        All rolling windows use the non-null values within the
        window and compute the mean of available samples. The
        variability index is the coefficient of variation
        (``std / mean``) of pace over the
        ``VARIABILITY_WINDOW_S`` window. The rolling mean fields
        for HR, power, and GAP are populated; rolling means for
        longer windows (60 s, 120 s) are emitted only for HR per
        the schema in
        ``docs/architecture/02-computations/signal-cleaning.md``.

        The result is the list of :class:`CleanedRecord` instances
        that the service persists.
        """
        n = derived.duration
        if n == 0:
            return []

        result: List[CleanedRecord] = []

        for t in range(n):
            # Per-window value extraction. ``max(0, t - W + 1)`` is
            # the start of the trailing window of length W ending at
            # (and including) t.
            def _window(attr: str, window: int) -> List[float]:
                start = max(0, t - window + 1)
                values: List[float] = []
                for k in range(start, t + 1):
                    v = getattr(derived, attr)[k]
                    if v is not None:
                        values.append(v)
                return values

            hr_window_30 = _window("hr", 30)
            hr_window_60 = _window("hr", 60)
            hr_window_120 = _window("hr", 120)
            power_window_30 = _window("power", 30)
            gap_window_30 = _window("gap_sec_per_km", 30)
            variability_window = _window("gap_sec_per_km", VARIABILITY_WINDOW_S)

            hr_30s_mean = (
                sum(hr_window_30) / len(hr_window_30) if hr_window_30 else None
            )
            hr_60s_mean = (
                sum(hr_window_60) / len(hr_window_60) if hr_window_60 else None
            )
            hr_120s_mean = (
                sum(hr_window_120) / len(hr_window_120) if hr_window_120 else None
            )
            power_30s_mean = (
                sum(power_window_30) / len(power_window_30) if power_window_30 else None
            )
            gap_30s_mean = (
                sum(gap_window_30) / len(gap_window_30) if gap_window_30 else None
            )

            # Variability index: coefficient of variation of pace
            # over the 30s window. Requires at least two samples to
            # compute a std; otherwise stays null.
            if len(variability_window) >= 2:
                mean = sum(variability_window) / len(variability_window)
                variance = sum((v - mean) ** 2 for v in variability_window) / len(
                    variability_window
                )
                std = math.sqrt(variance)
                variability_index = std / mean if mean > 0 else None
            else:
                variability_index = None

            # Cadence is deferred in Phase-2.2 (ParsedFitData does
            # not expose it; FIT parsing expansion is out of scope
            # per the plan's Notes). Always null in the cleaned
            # record.
            record = CleanedRecord(
                t=t,
                hr_bpm=derived.hr[t],
                rr_ms=derived.rr[t],
                power_w=derived.power[t],
                gap_sec_per_km=derived.gap_sec_per_km[t],
                cadence_rpm=None,
                elevation_m=derived.elevation_m[t],
                grade_pct=derived.grade_pct[t],
                variability_index=variability_index,
                hr_30s_mean=hr_30s_mean,
                hr_60s_mean=hr_60s_mean,
                hr_120s_mean=hr_120s_mean,
                power_30s_mean=power_30s_mean,
                gap_30s_mean=gap_30s_mean,
            )
            result.append(record)

        return result

    def _available_channels(self, resampled: _ResampledChannel) -> AvailableChannels:
        """Compute available channels from null fractions after artifact removal.

        The post-artifact null fraction is evaluated per channel.
        A channel is "available" (``True``) when its null fraction
        is at or below :data:`NULL_FRACTION_UNAVAILABLE_THRESHOLD`
        (i.e., at least 20% of the channel survived artifact
        removal). The 80% null rule protects the invariant
        "available_channels reflects what survived artifact removal".

        Special cases:

        * ``cadence`` is always ``False`` in Phase-2.2 because the
          parser does not expose cadence; the per-channel null
          rule would otherwise read as ``True`` for a never-written
          field.
        * ``pace`` and ``elevation`` are evaluated from the GPS
          presence in the input — these are ``True`` only when
          at least one GPS sample was supplied (i.e., the channel
          had a non-null source at any index). The per-record
          null-fraction rule would otherwise report ``True`` for
          an all-null pace channel derived from a speed-only
          input.
        """
        n = resampled.duration
        if n == 0:
            return AvailableChannels(
                hr=False,
                rr_intervals=False,
                power=False,
                pace=False,
                cadence=False,
                elevation=False,
            )

        def _available(series: Sequence[Optional[float]]) -> bool:
            non_null = sum(1 for v in series if v is not None)
            return non_null / n > NULL_FRACTION_UNAVAILABLE_THRESHOLD

        def _any_present(series: Sequence[Optional[float]]) -> bool:
            return any(v is not None for v in series)

        hr_available = _available(resampled.hr)
        rr_available = _available(resampled.rr)
        power_available = _available(resampled.power)
        pace_available = _any_present(resampled.speed_m_s)
        elevation_available = _any_present(resampled.elevation_m)

        return AvailableChannels(
            hr=hr_available,
            rr_intervals=rr_available,
            power=power_available,
            pace=pace_available,
            # Cadence is deferred in Phase-2.2 — always false.
            cadence=False,
            elevation=elevation_available,
        )


def _median(values: Sequence[float]) -> float:
    """Return the median of a non-empty numeric sequence.

    Local helper to avoid an additional dependency on ``statistics``
    for a single call site.
    """
    sorted_values = sorted(values)
    length = len(sorted_values)
    mid = length // 2
    if length % 2 == 0:
        return 0.5 * (sorted_values[mid - 1] + sorted_values[mid])
    return float(sorted_values[mid])