"""ThresholdDetectionService — compute threshold observations from cleaned streams.

Implements Phase-2.3-P1 of the implementation plan
``docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md``.

This service is the single owner of the three threshold detection
algorithms (HR deflection, RR inflection, power-to-HR ratio) and the
signal-selection logic that routes a session to the applicable
algorithms. It produces :class:`ThresholdObservation` data structures
that :class:`PhysiologyUpdateService` (Phase 2.3-P2) consumes to
update the per-athlete ``AthletePhysiology`` posterior state.

Public surface:

* :meth:`ThresholdDetectionService.detect` — single async entry
  point. Returns ``list[ThresholdObservation]``.

Invariants codified here, copied from the architecture corpus:

* Threshold detection only runs for ``calibration_eligible = true``
  activities. Non-eligible activities return an empty list
  silently — the worker surfaces the no-op to procrastinate.
* Threshold detection only runs for ``sport_type = RUNNING``.
  Non-running activities return an empty list silently.
* Missing ``RawSensorStream`` returns an empty list (signal
  cleaning not yet complete). Per ADR-009, downstream consumers
  handle "not yet ready" by skipping.
* The service does NOT write to ``PhysiologyMeasurement`` — that
  is ``PhysiologyUpdateService``'s responsibility (Plan P2).
* The service does NOT mutate ``AthletePhysiology``.
* Observation weights are fixed constants from
  ``evidence-mapping.md``: ``training_hr_deflection`` = 1.0,
  ``training_rr_inflection`` = 2.5, ``training_power_hr_ratio`` =
  1.5. These are the same values used by ``PhysiologyUpdateService``
  for the Bayesian update.
* ``confidence_weight`` on ``ThresholdObservation`` is
  algorithm-specific (0.0–1.0) and is distinct from the evidence
  ``weight`` (which is source-specific). The ``confidence_weight``
  reflects signal quality (e.g., R² for HR deflection, RMSSD
  signal quality for RR inflection). It is stored on
  ``PhysiologyMeasurement`` for audit but does NOT affect the
  Bayesian update — the evidence ``weight`` does.
"""

from __future__ import annotations

import gzip
import json
import math
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Dict, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import (
    MeasurementSource,
    PhysiologyParameter,
    SessionType,
    SportType,
)
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


# ---------------------------------------------------------------------------
# Frozen module constants.
# ---------------------------------------------------------------------------

#: Algorithm version strings — frozen at module scope. A future
#: algorithm change increments the version and re-detection
#: produces observations with the new ``algorithm_used`` value.
ALGORITHM_HR_DEFLECTION: str = "hr_deflection_v1"
ALGORITHM_RR_INFLECTION: str = "rr_inflection_v1"
ALGORITHM_POWER_HR_RATIO: str = "power_hr_ratio_v1"
ALGORITHM_NATURAL_TRAINING: str = "natural_training_v1"
ALGORITHM_HR_DRIFT: str = "hr_drift_v1"
ALGORITHM_HR_RECOVERY: str = "hr_recovery_v1"

#: Observation weights from ``evidence-mapping.md``. These are the
#: same values used by ``PhysiologyUpdateService`` (Plan P2) for the
#: Bayesian update. The ``ThresholdObservation.weight`` field carries
#: this value so ``PhysiologyUpdateService`` does not need to re-derive
#: it.
WEIGHT_HR_DEFLECTION: float = 1.0
WEIGHT_RR_INFLECTION: float = 2.5
WEIGHT_POWER_HR_RATIO: float = 1.5
WEIGHT_LT1_NATURAL_TRAINING: float = 0.5
WEIGHT_LT1_HR_DRIFT: float = 1.0
WEIGHT_LT1_HR_RECOVERY: float = 0.5

#: HR deflection algorithm thresholds from
#: ``docs/architecture/02-computations/threshold-detection.md``
#: Algorithm 1. ``R2_MIN_THRESHOLD`` is the minimum acceptable
#: coefficient of determination for the linear HR-intensity
#: regression; below this the algorithm returns no observations.
#: ``MIN_INTENSITY_STEPS`` is the minimum number of distinct
#: intensity bins required for the regression to be meaningful.
R2_MIN_THRESHOLD: float = 0.80
MIN_INTENSITY_STEPS: int = 3

#: RR inflection algorithm thresholds from
#: ``docs/architecture/02-computations/threshold-detection.md``
#: Algorithm 2. ``RMSSD_DROP_THRESHOLD`` is the fractional drop
#: below pre-effort baseline that defines the LT1 inflection
#: (15% per the spec). ``MIN_SECONDS_PER_INTENSITY_LEVEL`` is the
#: minimum duration at each intensity level required for the
#: algorithm to produce observations (8 minutes per the spec).
RMSSD_DROP_THRESHOLD: float = 0.15
MIN_SECONDS_PER_INTENSITY_LEVEL: int = 480

#: RMSSD rolling window size in seconds (Algorithm 2 step 2).
RMSSD_WINDOW_S: int = 60

#: Power-to-HR ratio algorithm thresholds from
#: ``docs/architecture/02-computations/threshold-detection.md``
#: Algorithm 3. ``RATIO_DECLINE_THRESHOLD`` is the minimum
#: sustained decline in the power/HR ratio (as a fraction of the
#: sub-threshold baseline) required to declare a breakpoint.
RATIO_DECLINE_THRESHOLD: float = 0.05

#: LT1 natural training analysis thresholds from
#: ``docs/architecture/02-computations/lt1-detection.md``
#: method 3. ``MIN_EASY_RUNS`` is the minimum number of recent
#: easy / recovery runs required (≥3 per the spec).
#: ``EASY_RUN_HR_TOLERANCE_BPM`` is the maximum spread (±5 bpm)
#: across mean-HR-per-run that the algorithm accepts as
#: "consistent" — a run whose mean HR deviates by more than this
#: is excluded.
#: ``NATURAL_TRAINING_LOOKBACK`` caps how many recent
#: calibration-eligible running activities the algorithm
#: inspects.
MIN_EASY_RUNS: int = 3
EASY_RUN_HR_TOLERANCE_BPM: float = 5.0
NATURAL_TRAINING_LOOKBACK: int = 20

#: LT1 HR drift algorithm thresholds from
#: ``docs/architecture/02-computations/lt1-detection.md``
#: method 4. ``HR_DRIFT_STEADY_STATE_S`` is the minimum segment
#: duration (≥20 minutes per the spec) to qualify as
#: steady-state. ``HR_DRIFT_START_S`` and ``HR_DRIFT_END_S``
#: define the first/last windows used to compute the drift
#: (first/last 5 minutes per the spec).
#: ``HR_DRIFT_ABOVE_LT1_BPM`` (5 bpm) and
#: ``HR_DRIFT_BELOW_LT1_BPM`` (2 bpm) are the thresholds
#: classifying a segment as above / below LT1.
HR_DRIFT_STEADY_STATE_S: int = 1200
HR_DRIFT_START_S: int = 300
HR_DRIFT_END_S: int = 300
HR_DRIFT_ABOVE_LT1_BPM: float = 5.0
HR_DRIFT_BELOW_LT1_BPM: float = 2.0

#: LT1 HR recovery algorithm thresholds from
#: ``docs/architecture/02-computations/lt1-detection.md``
#: method 5. ``HR_RECOVERY_WINDOW_S`` is the required recovery
#: window (≥2 minutes per the spec).
#: ``HR_RECOVERY_FAST_BPM`` (30 bpm in 2 min) and
#: ``HR_RECOVERY_SLOW_BPM`` (20 bpm in 2 min) are the
#: thresholds classifying the recovery speed.
HR_RECOVERY_WINDOW_S: int = 120
HR_RECOVERY_FAST_BPM: float = 30.0
HR_RECOVERY_SLOW_BPM: float = 20.0
#: Hard-effort classifier — the HR at cessation of effort must
#: be at least this fraction of max HR (proxied via
#: ``hr_120s_mean`` peak in the stream) to qualify as "above
#: LT2 / near max".
HR_RECOVERY_HARD_EFFORT_FRACTION: float = 0.90


# ---------------------------------------------------------------------------
# Result types.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdObservation:
    """One observation produced by threshold detection.

    The data contract between :class:`ThresholdDetectionService`
    and :class:`PhysiologyUpdateService` (Plan P2). Each observation
    carries the observed value, the source (which determines the
    evidence weight for the Bayesian update), the algorithm used,
    and an algorithm-specific confidence weight (0.0–1.0) that
    reflects signal quality.

    Fields:

    * ``parameter`` — which physiological parameter this observation
      contributes to (``LT1_HR``, ``LT2_HR``, ``CP``, etc.).
    * ``observed_value`` — the numeric value observed (HR in bpm,
      power in watts, etc.).
    * ``source`` — the ``MeasurementSource`` enum value that
      determines the evidence weight for the Bayesian update.
    * ``weight`` — the evidence weight from the evidence-mapping
      table. Fixed per source; carried on the observation so
      ``PhysiologyUpdateService`` does not need to re-derive it.
    * ``activity_id`` — the activity this observation was derived
      from. Nullable for lab/field test measurements, but
      threshold detection always sets it.
    * ``measurement_date`` — the date of the activity.
    * ``algorithm_used`` — the algorithm version string (e.g.,
      ``hr_deflection_v1``).
    * ``confidence_weight`` — algorithm-specific confidence in the
      0.0–1.0 range. Distinct from the evidence ``weight`` (which
      is source-specific). Stored on ``PhysiologyMeasurement`` for
      audit but does NOT affect the Bayesian update.
    """

    parameter: PhysiologyParameter
    observed_value: float
    source: MeasurementSource
    weight: float
    activity_id: uuid.UUID
    measurement_date: date
    algorithm_used: str
    confidence_weight: Optional[float]


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class ThresholdDetectionError(Exception):
    """Base class for threshold-detection failures."""


# ---------------------------------------------------------------------------
# Service.
# ---------------------------------------------------------------------------


class ThresholdDetectionService:
    """Compute threshold observations from cleaned sensor streams.

    The service is the single owner of the three threshold detection
    algorithms and the signal-selection logic that routes a session
    to the applicable algorithms. Construction is dependency-injected:
    the service holds an :class:`ObjectStorageClient`, a
    :class:`RawSensorStreamRepository`, an :class:`ActivityRepository`,
    an :class:`AthletePhysiologyRepository`, and a
    :class:`PhysiologyMeasurementRepository`. The :class:`AsyncSession`
    parameter is retained for API stability (the worker passes it
    positionally) and flows through to the injected repositories
    which hold it; the service does not store a direct reference.

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
        athlete_physiology_repository: AthletePhysiologyRepository,
        physiology_measurement_repository: PhysiologyMeasurementRepository,
        planned_session_repository: Optional[
            PlannedSessionRepository
        ] = None,
    ) -> None:
        # NOTE: the `session` parameter is retained because the
        # worker constructs the service with `session=session` and
        # the repositories hold the session internally. The service
        # does not store a direct reference to the session.
        self.object_storage = object_storage
        self.raw_streams = raw_stream_repository
        self.activities = activity_repository
        self.athlete_physiology = athlete_physiology_repository
        self.physiology_measurements = physiology_measurement_repository
        # Optional: only required by the LT1 natural training
        # analysis algorithm (method 3). Kept optional so existing
        # call sites that do not need natural training analysis
        # (unit tests that exercise only the per-session
        # algorithms) do not have to wire the repository.
        self.planned_sessions = planned_session_repository

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------

    async def detect(
        self, athlete_id: uuid.UUID, activity_id: uuid.UUID
    ) -> List[ThresholdObservation]:
        """Detect threshold observations for one activity.

        The single async entry point. Returns the list of
        :class:`ThresholdObservation` objects produced by the
        applicable algorithms. The service does NOT write to
        ``PhysiologyMeasurement`` — that is
        ``PhysiologyUpdateService``'s responsibility (Plan P2).

        Guards (all return an empty list silently):

        * Missing activity → ``[]``.
        * ``calibration_eligible = false`` → ``[]``.
        * ``sport_type != RUNNING`` → ``[]``.
        * Missing ``RawSensorStream`` → ``[]`` (signal cleaning
          not yet complete; per ADR-009, downstream consumers
          handle "not yet ready" by skipping).

        Signal selection (per ``threshold-detection.md``):

        * ``has_rr_intervals`` → run RR inflection (Algorithm 2).
        * ``has_hr``:
            * ``has_power`` → run HR deflection (Algorithm 1) +
              power-to-HR ratio (Algorithm 3).
            * else → run HR deflection (Algorithm 1).
        * else → ``[]`` (no update from this session).

        RR inflection takes priority over HR deflection when both
        are available (RR is the richer signal). Both may run — RR
        inflection produces higher-weight observations, HR
        deflection produces supplementary observations. The
        power-to-HR ratio always runs alongside HR-based detection
        when power is available.

        LT1 passive inference methods (``lt1-detection.md``
        methods 3–5) run as supplementary analysis after the
        per-session algorithms:

        * ``has_hr`` → run HR drift (method 4) and HR recovery
          (method 5).
        * Always → run natural training analysis (method 3,
          cross-session) as the last step. Fails silently when
          historical data is unavailable.

        Raises:
            ThresholdDetectionError: the cleaned stream could not
                be deserialised or downloaded. Propagates so the
                worker retries per procrastinate backoff.
        """
        activity = await self.activities.get_by_id(activity_id)
        if activity is None:
            return []

        # Calibration eligibility gate — non-eligible activities
        # return an empty list silently.
        if not activity.calibration_eligible:
            return []

        # Sport type gate — non-running activities return an empty
        # list silently.
        if activity.sport_type != SportType.RUNNING:
            return []

        # Signal cleaning gate — missing RawSensorStream means
        # cleaning has not yet completed. Per ADR-009, downstream
        # consumers handle "not yet ready" by skipping.
        raw_stream = await self.raw_streams.get_by_activity_id(activity_id)
        if raw_stream is None:
            return []

        # Download and deserialise the cleaned stream.
        cleaned_bytes = await self.object_storage.download_fit(
            raw_stream.fit_file_key
        )
        stream = _parse_cleaned_stream(cleaned_bytes)

        # Signal selection — route to applicable algorithms.
        observations: List[ThresholdObservation] = []
        if activity.has_rr_intervals and stream.available_channels.rr_intervals:
            observations.extend(
                _rr_inflection(stream, activity)
            )
        if activity.has_hr:
            observations.extend(_hr_deflection(stream, activity))
            if activity.has_power and stream.available_channels.power:
                observations.extend(_power_hr_ratio(stream, activity))
            # LT1 passive inference methods — per-session HR drift
            # and HR recovery. These run as supplementary analysis
            # after the per-session algorithms when HR is available.
            observations.extend(_hr_drift(stream, activity))
            observations.extend(_hr_recovery(stream, activity))

        # LT1 natural training analysis — cross-session, runs
        # last and fails silently when historical data is
        # unavailable.
        observations.extend(
            await _natural_training_analysis(athlete_id, activity, self)
        )

        return observations


# ---------------------------------------------------------------------------
# Algorithm implementations.
#
# Each algorithm is a pure function over the deserialised
# :class:`CleanedStream` and the :class:`Activity` row. They are
# synchronous because the cleaned stream is already in memory after
# deserialisation; the worker invokes them from the async
# :meth:`detect` entry point without further I/O.
# ---------------------------------------------------------------------------


def _hr_deflection(
    stream: CleanedStream, activity: Activity
) -> List[ThresholdObservation]:
    """Algorithm 1 — HR deflection.

    Implements the algorithm specified in
    ``docs/architecture/02-computations/threshold-detection.md``
    Algorithm 1:

    1. Segment the cleaned stream into intensity bins using GAP
       (``gap_sec_per_km``) or power (``power_w``). GAP is
       preferred when available; power is the fallback.
    2. For each bin: compute mean HR and mean intensity.
    3. Fit a linear HR-intensity regression across bins.
    4. LT1: first bin where slope increases above baseline (first
       departure from linearity).
    5. LT2: second, steeper departure.

    Returns ``[]`` (no observations) when:

    * Fewer than :data:`MIN_INTENSITY_STEPS` distinct intensity
      steps are present.
    * The linear regression R² is below
      :data:`R2_MIN_THRESHOLD`.

    On success, produces two :class:`ThresholdObservation` objects
    (one for ``LT1_HR`` and one for ``LT2_HR``) with source
    :attr:`MeasurementSource.TRAINING_HR_DEFLECTION` and weight
    :data:`WEIGHT_HR_DEFLECTION`. The ``confidence_weight`` is
    derived from the regression R² (higher R² → higher
    confidence, clamped to ``[0.0, 1.0]``).

    Bins with > 80% null HR values are skipped per the signal
    cleaning null-propagation invariant.
    """
    bins = _segment_into_intensity_bins(stream)
    if len(bins) < MIN_INTENSITY_STEPS:
        return []

    # Compute mean HR and mean intensity per bin, skipping bins
    # with insufficient HR coverage (>80% null).
    bin_means: List[Tuple[float, float]] = []
    for intensity_values, hr_values in bins:
        hr_non_null = [v for v in hr_values if v is not None]
        if not hr_non_null:
            continue
        null_fraction = 1.0 - (len(hr_non_null) / len(hr_values))
        if null_fraction > 0.80:
            continue
        intensity_non_null = [v for v in intensity_values if v is not None]
        if not intensity_non_null:
            continue
        bin_means.append((sum(intensity_non_null) / len(intensity_non_null),
                          sum(hr_non_null) / len(hr_non_null)))

    if len(bin_means) < MIN_INTENSITY_STEPS:
        return []

    # Linear regression: HR = slope * intensity + intercept.
    slope, intercept, r_squared = _linear_regression(bin_means)
    if r_squared < R2_MIN_THRESHOLD:
        return []

    # Sort bins by HR in ascending order (lowest HR first). This
    # ensures that bin_means[0] is the lowest HR bin (sub-threshold
    # region) and bin_means[-1] is the highest HR bin
    # (supra-threshold region). Sorting by HR is more robust than
    # sorting by intensity because HR is always in the same
    # direction (higher HR = higher intensity), whereas intensity
    # can be GAP (lower = higher intensity) or power (higher =
    # higher intensity).
    bin_means.sort(key=lambda b: b[1])

    # Detect LT1 and LT2. The algorithm looks for departures from
    # linearity — bins where HR rises faster than the linear trend
    # predicts. When the data is perfectly linear (no departures),
    # we fall back to using the intensity bins themselves: LT1 is
    # the HR at the lowest HR bin (the sub-threshold region), and
    # LT2 is the HR at a higher HR bin (the supra-threshold
    # region).
    lt1_hr: Optional[float] = None
    lt2_hr: Optional[float] = None

    # Compute residuals (observed HR − predicted HR) for each bin.
    residuals: List[Tuple[float, float, float]] = []
    for intensity_mean, hr_mean in bin_means:
        predicted = slope * intensity_mean + intercept
        residuals.append((intensity_mean, hr_mean, hr_mean - predicted))

    # Baseline residual is the mean of the first two bins'
    # residuals (the sub-threshold region — lowest HR).
    if len(residuals) >= 2:
        baseline_residual = (residuals[0][2] + residuals[1][2]) / 2.0
    else:
        baseline_residual = residuals[0][2]

    # Threshold for "departure from linearity": residual exceeds
    # baseline by more than 1.5 bpm (a small but meaningful
    # upward deflection).
    departure_threshold = 1.5

    # Find bins where the residual exceeds baseline by more than
    # the departure threshold. These are the "departure" bins.
    departure_bins: List[Tuple[float, float, float]] = []
    for intensity_mean, hr_mean, residual in residuals:
        if residual - baseline_residual > departure_threshold:
            departure_bins.append((intensity_mean, hr_mean, residual))

    if len(departure_bins) >= 1:
        # LT1: HR at the first departure bin.
        lt1_hr = departure_bins[0][1]
    else:
        # No departures from linearity — fall back to using the
        # intensity bins themselves. LT1 is the HR at the lowest
        # HR bin (the sub-threshold region).
        lt1_hr = bin_means[0][1]

    if len(departure_bins) >= 2:
        # LT2: HR at the second departure bin (steeper departure).
        lt2_hr = departure_bins[1][1]
    elif len(bin_means) >= 3:
        # No second departure — fall back to using a higher
        # HR bin. LT2 is the HR at the third-lowest HR bin (a
        # higher intensity where HR rises more steeply).
        lt2_hr = bin_means[2][1]

    confidence_weight = max(0.0, min(1.0, r_squared))
    measurement_date = activity.activity_date
    observations: List[ThresholdObservation] = [
        ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=lt1_hr,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=WEIGHT_HR_DEFLECTION,
            activity_id=activity.id,
            measurement_date=measurement_date,
            algorithm_used=ALGORITHM_HR_DEFLECTION,
            confidence_weight=confidence_weight,
        )
    ]
    if lt2_hr is not None:
        observations.append(
            ThresholdObservation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=lt2_hr,
                source=MeasurementSource.TRAINING_HR_DEFLECTION,
                weight=WEIGHT_HR_DEFLECTION,
                activity_id=activity.id,
                measurement_date=measurement_date,
                algorithm_used=ALGORITHM_HR_DEFLECTION,
                confidence_weight=confidence_weight,
            )
        )
    return observations


def _rr_inflection(
    stream: CleanedStream, activity: Activity
) -> List[ThresholdObservation]:
    """Algorithm 2 — RR inflection (HRV).

    Implements the algorithm specified in
    ``docs/architecture/02-computations/threshold-detection.md``
    Algorithm 2:

    1. Clean RR series (artifact detection; values outside ±20%
       of rolling median removed). The cleaned stream from
       Phase 2.2 already has this applied, so this is a
       verification pass — we skip null values that fall outside
       physiological bounds as a safety net.
    2. Compute RMSSD in 60-second rolling windows throughout the
       session using the ``rr_ms`` field from
       :class:`CleanedRecord`.
    3. Align RMSSD time-series with intensity time-series (GAP or
       power).
    4. LT1: first significant decrease in RMSSD as intensity
       rises (threshold: RMSSD drops > 15% below pre-effort
       baseline within the window).
    5. LT2: second inflection; typically less distinct; requires
       more data.

    Returns ``[]`` (no observations) when:

    * Fewer than :data:`MIN_SECONDS_PER_INTENSITY_LEVEL` seconds
      of data at each required intensity level.
    * No RR data is available.

    On success, produces two :class:`ThresholdObservation` objects
    (one for ``LT1_HR`` and one for ``LT2_HR``) with source
    :attr:`MeasurementSource.TRAINING_RR_INFLECTION` and weight
    :data:`WEIGHT_RR_INFLECTION`. The ``confidence_weight``
    reflects RMSSD signal quality (higher when the RMSSD
    time-series is well-defined and the inflection is clear).
    """
    rr_series = [(r.t, r.rr_ms) for r in stream.time_series
                 if r.rr_ms is not None]
    if not rr_series:
        return []

    # Compute RMSSD in 60-second rolling windows.
    rmssd_series = _compute_rmssd_rolling(rr_series, window_s=RMSSD_WINDOW_S)
    if not rmssd_series:
        return []

    # Align RMSSD with intensity (GAP or power).
    intensity_series = _extract_intensity_series(stream)
    if not intensity_series:
        return []

    # Segment into intensity bins and compute mean RMSSD per bin.
    bins = _segment_into_intensity_bins_from_series(
        intensity_series, rmssd_series
    )
    if len(bins) < 2:
        return []

    # Check minimum duration per intensity level.
    bin_durations = _compute_bin_durations(stream)
    for duration in bin_durations:
        if duration < MIN_SECONDS_PER_INTENSITY_LEVEL:
            return []

    # Compute mean RMSSD per bin.
    bin_rmssd: List[Tuple[float, float]] = []
    for (intensity_values, _), (_, rmssd_values) in zip(
        _segment_into_intensity_bins(stream), bins
    ):
        rmssd_non_null = [v for _, v in rmssd_values if v is not None]
        intensity_non_null = [v for v in intensity_values if v is not None]
        if not rmssd_non_null or not intensity_non_null:
            continue
        bin_rmssd.append(
            (sum(intensity_non_null) / len(intensity_non_null),
             sum(rmssd_non_null) / len(rmssd_non_null))
        )

    if len(bin_rmssd) < 2:
        return []

    # Sort by intensity.
    bin_rmssd.sort(key=lambda b: b[0])

    # Pre-effort baseline: mean RMSSD of the lowest-intensity bin.
    baseline_rmssd = bin_rmssd[0][1]
    if baseline_rmssd <= 0:
        return []

    # LT1: first bin where RMSSD drops > 15% below baseline.
    lt1_hr: Optional[float] = None
    lt2_hr: Optional[float] = None
    drop_threshold = baseline_rmssd * (1.0 - RMSSD_DROP_THRESHOLD)

    inflections: List[Tuple[float, float]] = []
    for intensity_mean, rmssd_mean in bin_rmssd:
        if rmssd_mean < drop_threshold:
            inflections.append((intensity_mean, rmssd_mean))

    if len(inflections) >= 1:
        # Map the inflection intensity back to HR via the HR
        # recorded at that intensity bin.
        lt1_hr = _hr_at_intensity(stream, inflections[0][0])

    if len(inflections) >= 2:
        lt2_hr = _hr_at_intensity(stream, inflections[1][0])

    if lt1_hr is None:
        return []

    # Confidence weight: based on the magnitude of the RMSSD drop
    # (larger drop → clearer inflection → higher confidence).
    if inflections:
        drop_fraction = (baseline_rmssd - inflections[0][1]) / baseline_rmssd
        confidence_weight = max(0.0, min(1.0, drop_fraction / 0.30))
    else:
        confidence_weight = 0.0

    measurement_date = activity.activity_date
    observations: List[ThresholdObservation] = [
        ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=lt1_hr,
            source=MeasurementSource.TRAINING_RR_INFLECTION,
            weight=WEIGHT_RR_INFLECTION,
            activity_id=activity.id,
            measurement_date=measurement_date,
            algorithm_used=ALGORITHM_RR_INFLECTION,
            confidence_weight=confidence_weight,
        )
    ]
    if lt2_hr is not None:
        observations.append(
            ThresholdObservation(
                parameter=PhysiologyParameter.LT2_HR,
                observed_value=lt2_hr,
                source=MeasurementSource.TRAINING_RR_INFLECTION,
                weight=WEIGHT_RR_INFLECTION,
                activity_id=activity.id,
                measurement_date=measurement_date,
                algorithm_used=ALGORITHM_RR_INFLECTION,
                confidence_weight=confidence_weight,
            )
        )
    return observations


def _power_hr_ratio(
    stream: CleanedStream, activity: Activity
) -> List[ThresholdObservation]:
    """Algorithm 3 — power-to-HR ratio.

    Implements the algorithm specified in
    ``docs/architecture/02-computations/threshold-detection.md``
    Algorithm 3:

    * At sub-threshold: power/HR ratio is stable within a session.
    * Above LT2: ratio begins sustained decline (cardiovascular
      cost rises faster than output).
    * Detect the ratio breakpoint.
    * Only produce an observation when the power series shows a
      clear ratio breakpoint.

    Returns ``[]`` (no observations) when:

    * No power data is available.
    * The ratio does not show a clear breakpoint (sustained
      decline exceeding :data:`RATIO_DECLINE_THRESHOLD`).

    On success, produces one :class:`ThresholdObservation` for
    :attr:`PhysiologyParameter.CP` with source
    :attr:`MeasurementSource.TRAINING_POWER_HR_RATIO` and weight
    :data:`WEIGHT_POWER_HR_RATIO`. The ``confidence_weight``
    reflects the magnitude of the ratio decline (larger decline
    → clearer breakpoint → higher confidence).
    """
    if not stream.available_channels.power:
        return []

    # Compute power/HR ratio per second.
    ratios: List[Tuple[int, float]] = []
    for record in stream.time_series:
        if record.power_w is not None and record.hr_bpm is not None \
                and record.hr_bpm > 0:
            ratios.append((record.t, record.power_w / record.hr_bpm))

    if len(ratios) < MIN_INTENSITY_STEPS * RMSSD_WINDOW_S:
        return []

    # Segment into intensity bins (by power) and compute mean
    # ratio per bin.
    bins = _segment_power_hr_into_bins(stream)
    if len(bins) < MIN_INTENSITY_STEPS:
        return []

    bin_ratios: List[Tuple[float, float]] = []
    for intensity_values, ratio_values in bins:
        ratio_non_null = [v for v in ratio_values if v is not None]
        intensity_non_null = [v for v in intensity_values if v is not None]
        if not ratio_non_null or not intensity_non_null:
            continue
        bin_ratios.append(
            (sum(intensity_non_null) / len(intensity_non_null),
             sum(ratio_non_null) / len(ratio_non_null))
        )

    if len(bin_ratios) < MIN_INTENSITY_STEPS:
        return []

    # Sort by intensity.
    bin_ratios.sort(key=lambda b: b[0])

    # Compute baseline ratio (mean of lowest-intensity bins).
    baseline_bins = bin_ratios[: max(2, len(bin_ratios) // 3)]
    baseline_ratio = sum(r for _, r in baseline_bins) / len(baseline_bins)
    if baseline_ratio <= 0:
        return []

    # Detect sustained decline: the ratio in the highest-intensity
    # bins must be below baseline by more than
    # RATIO_DECLINE_THRESHOLD.
    high_bins = bin_ratios[-max(2, len(bin_ratios) // 3):]
    high_ratio = sum(r for _, r in high_bins) / len(high_bins)
    decline_fraction = (baseline_ratio - high_ratio) / baseline_ratio

    if decline_fraction < RATIO_DECLINE_THRESHOLD:
        return []

    # CP estimate: power at the breakpoint (the highest-intensity
    # bin where the ratio is still within the stable region).
    cp_power: Optional[float] = None
    for intensity_mean, ratio_mean in bin_ratios:
        if ratio_mean >= baseline_ratio * (1.0 - RATIO_DECLINE_THRESHOLD):
            cp_power = intensity_mean
        else:
            break

    if cp_power is None:
        return []

    confidence_weight = max(0.0, min(1.0, decline_fraction / 0.20))
    measurement_date = activity.activity_date
    return [
        ThresholdObservation(
            parameter=PhysiologyParameter.CP,
            observed_value=cp_power,
            source=MeasurementSource.TRAINING_POWER_HR_RATIO,
            weight=WEIGHT_POWER_HR_RATIO,
            activity_id=activity.id,
            measurement_date=measurement_date,
            algorithm_used=ALGORITHM_POWER_HR_RATIO,
            confidence_weight=confidence_weight,
        )
    ]


# ---------------------------------------------------------------------------
# LT1 passive inference methods (lt1-detection.md methods 3–5).
#
# These algorithms run as supplementary analysis after the
# per-session algorithms (1–3). They produce ``LT1_HR``
# observations only. Natural training analysis is cross-session
# and queries historical activities; HR drift and HR recovery are
# per-session and operate on the current activity's cleaned
# stream.
# ---------------------------------------------------------------------------


async def _natural_training_analysis(
    athlete_id: uuid.UUID,
    activity: Activity,
    service: "ThresholdDetectionService",
) -> List[ThresholdObservation]:
    """LT1 method 3 — natural training analysis (passive inference).

    Implements the algorithm specified in
    ``docs/architecture/02-computations/lt1-detection.md`` method 3:

    1. Identify recent easy / recovery runs (session_type
       ``EASY_RUN`` or ``RECOVERY_RUN`` on the linked
       ``PlannedSession``).
    2. For each, download the cleaned stream and compute the mean
       HR using ``hr_30s_mean`` or ``hr_60s_mean`` (the rolling
       smoothed channels; fall back to ``hr_bpm`` if neither
       smoothed channel is present).
    3. If the mean HR is consistent across ≥3 runs (all values
       within ±5 bpm of the median), use the median as the LT1
       HR estimate.

    This method is cross-session. It does NOT require the current
    activity to be an easy run — it runs as supplementary analysis
    after the per-session algorithms regardless of the current
    activity's session type. The current activity is used only as
    the ``activity_id`` on the produced observation (so the
    observation is associated with the activity that triggered
    detection).

    Returns ``[]`` (no observations) when:

    * Fewer than :data:`MIN_EASY_RUNS` recent easy / recovery
      runs are available.
    * The mean HR across runs is not consistent
      (spread > :data:`EASY_RUN_HR_TOLERANCE_BPM`).
    * Historical cleaned streams are unavailable (the algorithm
      fails silently — this is the most expensive algorithm and
      the last one run).

    On success, produces one :class:`ThresholdObservation` for
    :attr:`PhysiologyParameter.LT1_HR` with source
    :attr:`MeasurementSource.TRAINING_HR_DEFLECTION` and weight
    :data:`WEIGHT_LT1_NATURAL_TRAINING` (0.5 — lower confidence
    than active tests per the spec). The ``confidence_weight``
    reflects the consistency of the easy-run HR values (tighter
    spread → higher confidence).
    """
    # Guard: the natural training analysis requires the planned
    # session repository. If the service was constructed without
    # it, skip silently.
    if service.planned_sessions is None:
        return []

    # Query recent calibration-eligible running activities.
    recent_activities = await service.activities.get_recent_activities_for_athlete(
        athlete_id=athlete_id,
        sport_type=SportType.RUNNING,
        limit=NATURAL_TRAINING_LOOKBACK,
    )
    if not recent_activities:
        return []

    # Filter to easy / recovery runs by joining through the
    # planned session. Activities without a planned session link
    # are excluded.
    easy_run_hrs: List[float] = []
    for candidate in recent_activities:
        if candidate.planned_session_id is None:
            continue
        planned = await service.planned_sessions.get_by_id(
            candidate.planned_session_id
        )
        if planned is None:
            continue
        if planned.session_type not in (
            SessionType.EASY_RUN,
            SessionType.RECOVERY_RUN,
        ):
            continue

        # Download the cleaned stream. If the stream is missing
        # (cleaning not yet complete for this activity) skip
        # silently — natural training analysis fails open.
        raw_stream = await service.raw_streams.get_by_activity_id(
            candidate.id
        )
        if raw_stream is None:
            continue
        if not candidate.has_hr:
            continue
        try:
            cleaned_bytes = await service.object_storage.download_fit(
                raw_stream.fit_file_key
            )
            stream = _parse_cleaned_stream(cleaned_bytes)
        except ThresholdDetectionError:
            # Fail silently — the algorithm is supplementary.
            continue

        mean_hr = _compute_mean_smoothed_hr(stream)
        if mean_hr is not None:
            easy_run_hrs.append(mean_hr)

    if len(easy_run_hrs) < MIN_EASY_RUNS:
        return []

    # Consistency check: all values within ±5 bpm of the median.
    sorted_hrs = sorted(easy_run_hrs)
    median_hr = sorted_hrs[len(sorted_hrs) // 2]
    if any(abs(hr - median_hr) > EASY_RUN_HR_TOLERANCE_BPM for hr in sorted_hrs):
        return []

    # Confidence weight: tighter spread → higher confidence.
    # Map [0, 5] bpm spread → [1.0, 0.0] confidence.
    spread = max(abs(hr - median_hr) for hr in sorted_hrs)
    confidence_weight = max(
        0.0, min(1.0, 1.0 - spread / EASY_RUN_HR_TOLERANCE_BPM)
    )

    return [
        ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=median_hr,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=WEIGHT_LT1_NATURAL_TRAINING,
            activity_id=activity.id,
            measurement_date=activity.activity_date,
            algorithm_used=ALGORITHM_NATURAL_TRAINING,
            confidence_weight=confidence_weight,
        )
    ]


def _hr_drift(
    stream: CleanedStream, activity: Activity
) -> List[ThresholdObservation]:
    """LT1 method 4 — HR drift (steady-state stability).

    Implements the algorithm specified in
    ``docs/architecture/02-computations/lt1-detection.md`` method 4:

    1. Identify steady-state segments (constant pace, constant
       grade) of duration ≥ :data:`HR_DRIFT_STEADY_STATE_S`
       (20 minutes per the spec).
    2. For each qualifying segment, compute mean HR over the
       first :data:`HR_DRIFT_START_S` (5 min) and the last
       :data:`HR_DRIFT_END_S` (5 min).
    3. ``hr_drift = hr_end - hr_start``.
       * Drift > :data:`HR_DRIFT_ABOVE_LT1_BPM` (5 bpm) →
         intensity is likely above LT1.
       * Drift < :data:`HR_DRIFT_BELOW_LT1_BPM` (2 bpm) →
         intensity is likely below LT1.
    4. The algorithm uses the drift as a constraint to refine
       the LT1 estimate, not a direct observation: when drift
       suggests "below LT1" the segment's mean HR is an upper
       bound on LT1; when drift suggests "above LT1" the
       segment's mean HR is a lower bound. The observation's
       ``observed_value`` is the segment's mean HR — the
       ``PhysiologyUpdateService`` (Plan P2) consumes the
       source and weight to apply the constraint semantics.

    Returns ``[]`` (no observations) when:

    * No HR data is available.
    * No steady-state segment of ≥ 20 min is found.
    * The drift is between 2 and 5 bpm (ambiguous — the
      algorithm does not produce a constraint in that band).

    On success, produces one :class:`ThresholdObservation` for
    :attr:`PhysiologyParameter.LT1_HR` with source
    :attr:`MeasurementSource.TRAINING_HR_DEFLECTION` and weight
    :data:`WEIGHT_LT1_HR_DRIFT` (1.0). The
    ``confidence_weight`` reflects how far the drift is from the
    threshold (clearer drift → higher confidence).
    """
    if not stream.available_channels.hr:
        return []

    # Identify the longest steady-state segment of ≥
    # HR_DRIFT_STEADY_STATE_S seconds with constant pace and
    # constant grade. "Constant" here is operationalised as
    # coefficient of variation < 5% over the segment for both
    # pace and grade. Pace uses gap_sec_per_km when available;
    # grade uses grade_pct.
    segment = _find_steady_state_segment(stream)
    if segment is None:
        return []

    start_t, end_t = segment
    hr_in_segment = [
        r.hr_bpm for r in stream.time_series
        if r.t >= start_t and r.t <= end_t and r.hr_bpm is not None
    ]
    if len(hr_in_segment) < HR_DRIFT_START_S + HR_DRIFT_END_S:
        return []

    hr_start = sum(
        r.hr_bpm for r in stream.time_series
        if r.t >= start_t
        and r.t < start_t + HR_DRIFT_START_S
        and r.hr_bpm is not None
    ) / HR_DRIFT_START_S
    hr_end = sum(
        r.hr_bpm for r in stream.time_series
        if r.t > end_t - HR_DRIFT_END_S
        and r.t <= end_t
        and r.hr_bpm is not None
    ) / HR_DRIFT_END_S
    drift = hr_end - hr_start

    if drift >= HR_DRIFT_ABOVE_LT1_BPM:
        # Above LT1 — segment mean HR is a lower bound.
        mean_hr = (hr_start + hr_end) / 2.0
        confidence_weight = max(
            0.0, min(1.0, (drift - HR_DRIFT_ABOVE_LT1_BPM) / 5.0)
        )
        return [
            ThresholdObservation(
                parameter=PhysiologyParameter.LT1_HR,
                observed_value=mean_hr,
                source=MeasurementSource.TRAINING_HR_DEFLECTION,
                weight=WEIGHT_LT1_HR_DRIFT,
                activity_id=activity.id,
                measurement_date=activity.activity_date,
                algorithm_used=ALGORITHM_HR_DRIFT,
                confidence_weight=confidence_weight,
            )
        ]
    if drift <= HR_DRIFT_BELOW_LT1_BPM:
        # Below LT1 — segment mean HR is an upper bound.
        mean_hr = (hr_start + hr_end) / 2.0
        confidence_weight = max(
            0.0, min(1.0, (HR_DRIFT_BELOW_LT1_BPM - drift) / 2.0)
        )
        return [
            ThresholdObservation(
                parameter=PhysiologyParameter.LT1_HR,
                observed_value=mean_hr,
                source=MeasurementSource.TRAINING_HR_DEFLECTION,
                weight=WEIGHT_LT1_HR_DRIFT,
                activity_id=activity.id,
                measurement_date=activity.activity_date,
                algorithm_used=ALGORITHM_HR_DRIFT,
                confidence_weight=confidence_weight,
            )
        ]

    # Ambiguous drift — no constraint.
    return []


def _hr_recovery(
    stream: CleanedStream, activity: Activity
) -> List[ThresholdObservation]:
    """LT1 method 5 — HR recovery (recovery speed after stopping).

    Implements the algorithm specified in
    ``docs/architecture/02-computations/lt1-detection.md`` method 5:

    1. Identify hard efforts — defined here as the peak of the
       smoothed HR series (``hr_120s_mean``) reaching at least
       :data:`HR_RECOVERY_HARD_EFFORT_FRACTION` (90%) of the
       stream's max smoothed HR. This proxies "above LT2 / near
       max HR" using the available cleaned-stream signals.
    2. After the peak, identify the recovery window — the
       :data:`HR_RECOVERY_WINDOW_S` (2 min) following the first
       sustained drop in smoothed HR after the peak.
    3. ``hr_recovery = hr_at_cessation - hr_at_2min``.
    4. Faster recovery (> :data:`HR_RECOVERY_FAST_BPM` / 30 bpm
       in 2 min) suggests lower LT1.
       Slower recovery (< :data:`HR_RECOVERY_SLOW_BPM` / 20 bpm
       in 2 min) suggests higher LT1.

    The observation's ``observed_value`` is the HR at the start
    of recovery (cessation) — the same proxy the spec uses. The
    ``PhysiologyUpdateService`` (Plan P2) consumes the source
    and weight to apply the recovery-speed semantics.

    Returns ``[]`` (no observations) when:

    * No HR data is available.
    * No hard effort is detected in the stream.
    * The recovery window is shorter than
      :data:`HR_RECOVERY_WINDOW_S`.

    On success, produces one :class:`ThresholdObservation` for
    :attr:`PhysiologyParameter.LT1_HR` with source
    :attr:`MeasurementSource.TRAINING_HR_DEFLECTION` and weight
    :data:`WEIGHT_LT1_HR_RECOVERY` (0.5 — supplementary per the
    spec). The ``confidence_weight`` reflects how far the
    recovery speed is from the fast / slow thresholds.
    """
    if not stream.available_channels.hr:
        return []

    # Build the smoothed HR series. Use hr_120s_mean when
    # available; fall back to hr_60s_mean, then hr_30s_mean,
    # then hr_bpm.
    smoothed: List[Tuple[int, Optional[float]]] = []
    for r in stream.time_series:
        v = r.hr_120s_mean
        if v is None:
            v = r.hr_60s_mean
        if v is None:
            v = r.hr_30s_mean
        if v is None:
            v = r.hr_bpm
        smoothed.append((r.t, v))

    non_null = [(t, v) for t, v in smoothed if v is not None]
    if len(non_null) < 2:
        return []

    peak_hr = max(v for _, v in non_null)
    hard_effort_threshold = peak_hr * HR_RECOVERY_HARD_EFFORT_FRACTION
    peak_t = next(t for t, v in non_null if v == peak_hr)

    # Find the cessation point: the first sample after the peak
    # where smoothed HR drops below hard_effort_threshold for at
    # least 10 seconds (recovery begins).
    cessation_t: Optional[int] = None
    drop_window: List[int] = []
    for t, v in smoothed:
        if t <= peak_t:
            continue
        if v is not None and v < hard_effort_threshold:
            drop_window.append(t)
            if len(drop_window) >= 10 and (
                drop_window[-1] - drop_window[0] >= 9
            ):
                cessation_t = drop_window[0]
                break
        else:
            drop_window = []

    if cessation_t is None:
        return []

    # The recovery window is the HR_RECOVERY_WINDOW_S seconds
    # after cessation.
    recovery_end_t = cessation_t + HR_RECOVERY_WINDOW_S
    if recovery_end_t > smoothed[-1][0]:
        return []

    hr_at_cessation = next(
        (v for t, v in smoothed if t >= cessation_t and v is not None),
        None,
    )
    hr_at_2min = next(
        (
            v for t, v in reversed(smoothed)
            if t <= recovery_end_t and v is not None
        ),
        None,
    )
    if hr_at_cessation is None or hr_at_2min is None:
        return []

    recovery_drop = hr_at_cessation - hr_at_2min

    # Only produce an observation when the recovery is clearly
    # fast OR clearly slow. Ambiguous recoveries (20–30 bpm) do
    # not contribute a constraint.
    is_fast = recovery_drop >= HR_RECOVERY_FAST_BPM
    is_slow = recovery_drop <= HR_RECOVERY_SLOW_BPM
    if not (is_fast or is_slow):
        return []

    # Confidence weight: how far the recovery drop is from the
    # nearest threshold.
    if recovery_drop >= HR_RECOVERY_FAST_BPM:
        confidence_weight = max(
            0.0, min(1.0, (recovery_drop - HR_RECOVERY_FAST_BPM) / 10.0)
        )
    else:
        confidence_weight = max(
            0.0, min(1.0, (HR_RECOVERY_SLOW_BPM - recovery_drop) / 10.0)
        )

    return [
        ThresholdObservation(
            parameter=PhysiologyParameter.LT1_HR,
            observed_value=hr_at_cessation,
            source=MeasurementSource.TRAINING_HR_DEFLECTION,
            weight=WEIGHT_LT1_HR_RECOVERY,
            activity_id=activity.id,
            measurement_date=activity.activity_date,
            algorithm_used=ALGORITHM_HR_RECOVERY,
            confidence_weight=confidence_weight,
        )
    ]


def _compute_mean_smoothed_hr(
    stream: CleanedStream,
) -> Optional[float]:
    """Return the mean smoothed HR across the cleaned stream.

    Prefers ``hr_60s_mean`` (the 60-second rolling mean per the
    signal-cleaning spec), falls back to ``hr_30s_mean``, then to
    ``hr_bpm`` when neither smoothed channel is populated. Returns
    ``None`` when no HR values are present.
    """
    values: List[float] = []
    for r in stream.time_series:
        v = r.hr_60s_mean
        if v is None:
            v = r.hr_30s_mean
        if v is None:
            v = r.hr_bpm
        if v is not None:
            values.append(v)
    if not values:
        return None
    return sum(values) / len(values)


def _find_steady_state_segment(
    stream: CleanedStream,
) -> Optional[Tuple[int, int]]:
    """Return ``(start_t, end_t)`` of the longest steady-state
    segment of ≥ ``HR_DRIFT_STEADY_STATE_S`` seconds.

    A segment is steady-state when both pace (``gap_sec_per_km``)
    and grade (``grade_pct``) have a coefficient of variation
    below 5% across the segment. The function scans the stream
    with a sliding window of ``HR_DRIFT_STEADY_STATE_S`` seconds
    and returns the window with the lowest combined CV.

    Returns ``None`` when no qualifying window exists.
    """
    if not stream.time_series:
        return None

    window_size = HR_DRIFT_STEADY_STATE_S
    if len(stream.time_series) < window_size:
        return None

    best_segment: Optional[Tuple[int, int]] = None
    best_score: float = float("inf")

    # Pre-extract pace and grade series for efficiency.
    pace_series: List[Tuple[int, Optional[float]]] = [
        (r.t, r.gap_sec_per_km) for r in stream.time_series
    ]
    grade_series: List[Tuple[int, Optional[float]]] = [
        (r.t, r.grade_pct) for r in stream.time_series
    ]

    for i in range(len(stream.time_series) - window_size + 1):
        start_t = stream.time_series[i].t
        end_t = stream.time_series[i + window_size - 1].t

        # Score = combined CV of pace and grade. Lower is better.
        pace_cv = _coefficient_of_variation(
            [v for _, v in pace_series[i:i + window_size] if v is not None]
        )
        grade_cv = _coefficient_of_variation(
            [v for _, v in grade_series[i:i + window_size] if v is not None]
        )
        # When pace or grade is missing, ignore that dimension.
        pace_score = pace_cv if pace_cv is not None else 0.0
        grade_score = grade_cv if grade_cv is not None else 0.0
        combined = pace_score + grade_score

        if (
            (pace_cv is None or pace_cv < 0.05)
            and (grade_cv is None or grade_cv < 0.05)
            and combined < best_score
        ):
            best_score = combined
            best_segment = (start_t, end_t)

    return best_segment


def _coefficient_of_variation(values: List[float]) -> Optional[float]:
    """Return the coefficient of variation (σ / μ) of ``values``,
    or ``None`` when fewer than two values are present.
    """
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    if mean == 0:
        return None
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance) / abs(mean)


# ---------------------------------------------------------------------------
# Shared helpers.
# ---------------------------------------------------------------------------


def _segment_into_intensity_bins(
    stream: CleanedStream,
) -> List[Tuple[List[Optional[float]], List[Optional[float]]]]:
    """Segment the cleaned stream into intensity bins.

    Returns a list of ``(intensity_values, hr_values)`` tuples,
    one per bin. GAP (``gap_sec_per_km``) is preferred when
    available; power (``power_w``) is the fallback. HR values
    are paired with their corresponding intensity values.

    Bins are formed by quantising intensity into discrete steps.
    """
    intensity_field: Optional[str] = None
    if stream.available_channels.pace:
        intensity_field = "gap_sec_per_km"
    elif stream.available_channels.power:
        intensity_field = "power_w"

    if intensity_field is None:
        return []

    intensity_values = [getattr(r, intensity_field) for r in stream.time_series]
    hr_values = [r.hr_bpm for r in stream.time_series]

    # Quantise intensity into bins. We use a simple approach:
    # round intensity to the nearest 5% of its range, producing
    # discrete steps.
    non_null = [v for v in intensity_values if v is not None]
    if not non_null:
        return []

    intensity_min = min(non_null)
    intensity_max = max(non_null)
    intensity_range = intensity_max - intensity_min
    if intensity_range <= 0:
        return []

    step_size = intensity_range / 10.0  # 10 bins across the range

    bins: Dict[float, Tuple[List[Optional[float]], List[Optional[float]]]] = {}
    for intensity, hr in zip(intensity_values, hr_values):
        if intensity is None:
            continue
        bin_key = round((intensity - intensity_min) / step_size) * step_size
        if bin_key not in bins:
            bins[bin_key] = ([], [])
        bins[bin_key][0].append(intensity)
        bins[bin_key][1].append(hr)

    # Sort by bin key (intensity).
    return [bins[k] for k in sorted(bins.keys())]


def _segment_into_intensity_bins_from_series(
    intensity_series: List[Tuple[int, Optional[float]]],
    value_series: List[Tuple[int, Optional[float]]],
) -> List[Tuple[List[Tuple[int, Optional[float]]], List[Tuple[int, Optional[float]]]]]:
    """Segment paired intensity and value series into bins.

    Used by the RR inflection algorithm to align RMSSD with
    intensity. Returns a list of ``(intensity_bin, value_bin)``
    tuples where each bin is a list of ``(t, value)`` pairs.
    """
    non_null_intensity = [v for _, v in intensity_series if v is not None]
    if not non_null_intensity:
        return []

    intensity_min = min(non_null_intensity)
    intensity_max = max(non_null_intensity)
    intensity_range = intensity_max - intensity_min
    if intensity_range <= 0:
        return []

    step_size = intensity_range / 10.0

    bins: dict[float, tuple[list[tuple[int, Optional[float]]], list[tuple[int, Optional[float]]]]] = {}
    for (t_i, i_val), (t_v, v_val) in zip(intensity_series, value_series):
        if i_val is None:
            continue
        bin_key = round((i_val - intensity_min) / step_size) * step_size
        if bin_key not in bins:
            bins[bin_key] = ([], [])
        bins[bin_key][0].append((t_i, i_val))
        bins[bin_key][1].append((t_v, v_val))

    return [bins[k] for k in sorted(bins.keys())]


def _segment_power_hr_into_bins(
    stream: CleanedStream,
) -> List[Tuple[List[Optional[float]], List[Optional[float]]]]:
    """Segment the stream into power-based bins with power/HR ratios.

    Returns a list of ``(power_values, ratio_values)`` tuples,
    one per bin. Used by the power-to-HR ratio algorithm.
    """
    power_values: List[Optional[float]] = []
    ratio_values: List[Optional[float]] = []
    for r in stream.time_series:
        power_values.append(r.power_w)
        if r.power_w is not None and r.hr_bpm is not None and r.hr_bpm > 0:
            ratio_values.append(r.power_w / r.hr_bpm)
        else:
            ratio_values.append(None)

    non_null_power = [v for v in power_values if v is not None]
    if not non_null_power:
        return []

    power_min = min(non_null_power)
    power_max = max(non_null_power)
    power_range = power_max - power_min
    if power_range <= 0:
        return []

    step_size = power_range / 10.0

    bins: Dict[float, Tuple[List[Optional[float]], List[Optional[float]]]] = {}
    for power, ratio in zip(power_values, ratio_values):
        if power is None:
            continue
        bin_key = round((power - power_min) / step_size) * step_size
        if bin_key not in bins:
            bins[bin_key] = ([], [])
        bins[bin_key][0].append(power)
        bins[bin_key][1].append(ratio)

    return [bins[k] for k in sorted(bins.keys())]


def _linear_regression(
    points: List[Tuple[float, float]],
) -> Tuple[float, float, float]:
    """Fit a linear regression y = slope * x + intercept.

    Returns ``(slope, intercept, r_squared)``. The R² value is
    the coefficient of determination; 1.0 indicates a perfect
    fit.
    """
    n = len(points)
    if n < 2:
        return 0.0, 0.0, 0.0

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    # R² = 1 - SS_res / SS_tot
    mean_y = sum_y / n
    ss_tot = sum((p[1] - mean_y) ** 2 for p in points)
    ss_res = sum((p[1] - (slope * p[0] + intercept)) ** 2 for p in points)

    if ss_tot == 0:
        r_squared = 1.0 if ss_res == 0 else 0.0
    else:
        r_squared = 1.0 - ss_res / ss_tot

    return slope, intercept, r_squared


def _compute_rmssd_rolling(
    rr_series: List[Tuple[int, float]],
    window_s: int,
) -> List[Tuple[int, Optional[float]]]:
    """Compute RMSSD in rolling windows over the RR series.

    Returns a list of ``(t, rmssd)`` tuples, one per window.
    RMSSD (root mean square of successive differences) is a
    standard HRV metric computed from consecutive RR intervals.
    """
    if len(rr_series) < 2:
        return []

    result: List[Tuple[int, Optional[float]]] = []
    window_start_idx = 0
    for i in range(1, len(rr_series)):
        t_current = rr_series[i][0]
        # Advance window start to maintain window_s width.
        while (rr_series[window_start_idx][0]
               < t_current - window_s):
            window_start_idx += 1
            if window_start_idx >= i:
                break

        if window_start_idx >= i:
            result.append((t_current, None))
            continue

        # Compute successive differences within the window.
        window = rr_series[window_start_idx:i + 1]
        if len(window) < 2:
            result.append((t_current, None))
            continue

        successive_diffs = [window[j + 1][1] - window[j][1]
                            for j in range(len(window) - 1)]
        rmssd = math.sqrt(
            sum(d ** 2 for d in successive_diffs) / len(successive_diffs)
        )
        result.append((t_current, rmssd))

    return result


def _extract_intensity_series(
    stream: CleanedStream,
) -> List[Tuple[int, Optional[float]]]:
    """Extract the intensity time-series from the cleaned stream.

    GAP is preferred when available; power is the fallback.
    Returns a list of ``(t, intensity)`` tuples.
    """
    if stream.available_channels.pace:
        return [(r.t, r.gap_sec_per_km) for r in stream.time_series]
    if stream.available_channels.power:
        return [(r.t, r.power_w) for r in stream.time_series]
    return []


def _compute_bin_durations(stream: CleanedStream) -> List[int]:
    """Compute the duration (in seconds) of each intensity bin.

    Used by the RR inflection algorithm to enforce the minimum
    duration per intensity level.
    """
    bins = _segment_into_intensity_bins(stream)
    return [len(intensity_values) for intensity_values, _ in bins]


def _hr_at_intensity(
    stream: CleanedStream, target_intensity: float
) -> Optional[float]:
    """Return the mean HR at a given intensity level.

    Used by the RR inflection algorithm to map an inflection
    intensity back to an HR value for the observation.
    """
    hr_values: List[float] = []
    intensity_field: Optional[str] = None
    if stream.available_channels.pace:
        intensity_field = "gap_sec_per_km"
    elif stream.available_channels.power:
        intensity_field = "power_w"

    if intensity_field is None:
        return None

    for r in stream.time_series:
        intensity = getattr(r, intensity_field)
        if intensity is not None and r.hr_bpm is not None:
            if abs(intensity - target_intensity) < 0.5:
                hr_values.append(r.hr_bpm)

    if not hr_values:
        return None
    return sum(hr_values) / len(hr_values)


# ---------------------------------------------------------------------------
# Deserialisation helper.
# ---------------------------------------------------------------------------


def _parse_cleaned_stream(raw_bytes: bytes) -> CleanedStream:
    """Deserialise gzipped JSON bytes into a :class:`CleanedStream`.

    Mirrors the serialisation in
    :meth:`CleanedStream.to_json_bytes` (gzipped JSON with the
    ``time_series``, ``sampling_rate_hz``, and ``available_channels``
    keys). The inverse of the upload path in
    :meth:`SignalCleaningService.clean`.

    Raises:
        ThresholdDetectionError: the bytes could not be
            decompressed or parsed. Propagates so the worker
            retries per procrastinate backoff.
    """
    try:
        decompressed = gzip.decompress(raw_bytes)
        payload = json.loads(decompressed.decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise ThresholdDetectionError(
            f"failed to deserialise cleaned stream: {exc}"
        ) from exc

    time_series_raw = payload.get("time_series", [])
    time_series = [
        CleanedRecord(
            t=record["t"],
            hr_bpm=record.get("hr_bpm"),
            rr_ms=record.get("rr_ms"),
            power_w=record.get("power_w"),
            gap_sec_per_km=record.get("gap_sec_per_km"),
            cadence_rpm=record.get("cadence_rpm"),
            elevation_m=record.get("elevation_m"),
            grade_pct=record.get("grade_pct"),
            variability_index=record.get("variability_index"),
            hr_30s_mean=record.get("hr_30s_mean"),
            hr_60s_mean=record.get("hr_60s_mean"),
            hr_120s_mean=record.get("hr_120s_mean"),
            power_30s_mean=record.get("power_30s_mean"),
            gap_30s_mean=record.get("gap_30s_mean"),
        )
        for record in time_series_raw
    ]

    channels_raw = payload.get("available_channels", {})
    available_channels = AvailableChannels(
        hr=bool(channels_raw.get("hr", False)),
        rr_intervals=bool(channels_raw.get("rr_intervals", False)),
        power=bool(channels_raw.get("power", False)),
        pace=bool(channels_raw.get("pace", False)),
        cadence=bool(channels_raw.get("cadence", False)),
        elevation=bool(channels_raw.get("elevation", False)),
    )

    return CleanedStream(
        time_series=time_series,
        sampling_rate_hz=float(payload.get("sampling_rate_hz", 1.0)),
        available_channels=available_channels,
    )
