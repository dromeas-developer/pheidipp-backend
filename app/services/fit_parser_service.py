"""FitParserService — extract raw HR data from a FIT file.

Implements the Phase-1.6 contract from
``docs/architecture/01-entities/activity.md`` →
``LoadComputationService`` invariant ``must receive raw records from
``FitParserService``, not summary stats``.

Scope at this phase:

* HR data only (bpm per second). Power, GPS, RR intervals and lap
  data are parsed when present and exposed on the result so future
  phases can extend the contract, but the load formula in this phase
  consumes HR only.
* Heuristic load computation — the parser does NOT compute averages
  (``avg_hr``, ``avg_pace``) per the architecture invariant; those
  values are deliberately absent from the ``Activity`` row.
* Common FIT file structures from Garmin, Coros, Wahoo, Polar etc.
  Unreadable / corrupt / unsupported files raise
  :class:`FitParseError` and the API layer surfaces that as 422.

Parser library:

* ``fitparse`` (1.2+) is the de-facto Python FIT SDK. It supports
  the common subset robustly across device vendors and reads the
  raw record stream synchronously; the sync parse runs inside a
  thread-pool executor so the async event loop is never blocked.

Output:

* :class:`ParsedFitData` carries the raw HR sample array, the
  session start time, total duration, the moving duration, and
  signal-availability flags. Power samples are exposed but
  ``has_power`` / ``has_rr_intervals`` flag tracks whether the
  Phase-1.6 load formula can consume them.

Phase-2 expansion:

* GPS records (distance, elevation, speed/pace) and RR interval
  time-series for full signal processing.
* Lap data and session-level totals.
* Artifact detection (GPS spikes > 25 m/s speed).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, cast

from fitparse import FitFile, FitParseError as UpstreamFitParseError  # type: ignore[reportMissingTypeStubs]

from app.core.logging_utils import log_event
from app.models.enums import SportType


# ---------------------------------------------------------------------------
# Errors.
# ---------------------------------------------------------------------------


class FitParseError(Exception):
    """The FIT file is unreadable, corrupt, or unsupported.

    The API layer maps this to HTTP 422 with a plain-language detail
    message; the ingestion pipeline MUST NOT create an ``Activity``
    record when parsing fails (architecture invariant).
    """


class FitParseEmptyError(FitParseError):
    """The FIT file parsed successfully but produced no HR records.

    Treated separately so the caller can distinguish "this is not a
    runnable session" from "the file is corrupt". Both cases return
    422 to the API consumer.
    """


# ---------------------------------------------------------------------------
# Helper dataclass for GPS records.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GpsRecord:
    """Single GPS point from a FIT file's record message.

    All fields are in SI units (meters, meters/second) or radians.
    """

    timestamp: datetime
    position_lat: Optional[float] = None
    position_long: Optional[float] = None
    distance: Optional[float] = None
    altitude: Optional[float] = None
    speed: Optional[float] = None


# ---------------------------------------------------------------------------
# Output dataclass.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ParsedFitData:
    """One parsed FIT file's worth of raw signals.

    The contract intentionally preserves raw records (HR per second)
    rather than summary statistics so :class:`LoadComputationService`
    can apply the HR-reserve integration formula against the
    original signal — the architecture invariant on raw-records-only
    consumption.

    Phase-2 expansion:

    * GPS records (distance, elevation, speed/pace) for structural
      load computation and GPS artifact detection.
    * RR interval time-series for HRV analysis.
    * Session-level totals (total distance, total ascent).
    * Flags for data availability and quality issues.
    * Sport type detection result from FIT sport message.
    """

    start_time: datetime
    duration_seconds: int
    hr_records: list[Optional[float]] = field(default_factory=lambda: [])
    power_records: list[Optional[float]] = field(default_factory=lambda: [])
    has_hr: bool = False
    has_power: bool = False
    has_rr_intervals: bool = False
    # Phase-2 additions:
    gps_records: list[GpsRecord] = field(default_factory=lambda: [])
    rr_records: list[Optional[float]] = field(default_factory=lambda: [])
    total_distance_m: Optional[float] = None
    total_ascent_m: Optional[float] = None
    has_gps: bool = False
    moving_duration_seconds: int = 0
    # Sport type detection (Phase-2.1-P3):
    sport_type: SportType = SportType.UNKNOWN
    detection_confidence: str = "unknown"
    detection_version: str = "v1"


# ---------------------------------------------------------------------------
# Parser.
# ---------------------------------------------------------------------------


class FitParserService:
    """Parse FIT files into :class:`ParsedFitData`.

    Stateless — every ``parse`` call returns a fresh dataclass. The
    service is safe to instantiate per-request.
    """

    HR_FIELD = "heart_rate"
    POWER_FIELD = "power"
    TIMESTAMP_FIELD = "timestamp"
    SESSION_START_FIELD = "start_time"
    SESSION_TOTAL_TIMER_FIELD = "total_timer_time"
    SESSION_TOTAL_ELAPSED_FIELD = "total_elapsed_time"
    SESSION_TOTAL_DISTANCE_FIELD = "total_distance"
    SESSION_TOTAL_ELEV_GAIN_FIELD = "total_ascent"

    # GPS artifact detection threshold: speed > 25 m/s (~90 km/h) is
    # physically impossible for running and indicates a GPS glitch.
    GPS_SPEED_SPIKE_THRESHOLD_M_S = 25.0

    async def parse(self, file_bytes: bytes) -> ParsedFitData:
        """Parse FIT bytes into raw-record :class:`ParsedFitData`.

        The blocking parser call runs inside a thread-pool executor
        so the async event loop is never blocked on CPU work.

        Raises:
            FitParseError: the file is unreadable / corrupt / from
                an unsupported producer.
            FitParseEmptyError: parsing succeeded but no HR records
                were found (the session is not runnable at this phase).
        """
        loop = asyncio.get_running_loop()
        try:
            parsed = await loop.run_in_executor(None, self._parse_sync, file_bytes)
        except UpstreamFitParseError as exc:
            log_event(event="fit_parse.failed", outcome="failed")
            raise FitParseError(f"FIT file is corrupt or unsupported: {exc}") from exc
        except (ValueError, OSError) as exc:
            log_event(event="fit_parse.failed", outcome="failed")
            raise FitParseError(f"FIT file could not be parsed: {exc}") from exc

        if not parsed.hr_records:
            log_event(event="fit_parse.empty", outcome="failed")
            raise FitParseEmptyError(
                "FIT file parsed successfully but contained no HR records"
            )

        log_event(
            event="fit_parse.success",
            outcome="success",
        )
        return parsed

    # ------------------------------------------------------------------
    # Sync implementation — runs in the executor.
    # ------------------------------------------------------------------

    def _parse_sync(self, file_bytes: bytes) -> ParsedFitData:
        fit = FitFile(BytesReader(file_bytes))
        # ``parse`` is a generator that yields definition + data
        # messages. We only need data messages for record extraction.
        # fit.parse() has no return (populates internal buffers as a
        # side-effect); list() was an erroneous wrapper — remove it.
        fit.parse()  # type: ignore[arg-type]

        hr_records: list[Optional[float]] = []
        power_records: list[Optional[float]] = []
        rr_records: list[Optional[float]] = []
        gps_records: list[GpsRecord] = []
        start_time: Optional[datetime] = None
        duration_seconds: int = 0
        total_distance_m: Optional[float] = None
        total_ascent_m: Optional[float] = None
        has_gps: bool = False

        # Sport type detection variables (Phase-2.1-P3)
        sport_int: Optional[int] = None
        sub_sport_int: Optional[int] = None
        sport_type = SportType.UNKNOWN
        detection_confidence = "unknown"

        for message in fit.messages:  # type: ignore[reportUnknownVariableType]
            if message.name == "session":  # type: ignore[attr-defined]
                if start_time is None:
                    raw_start = message.get_value(self.SESSION_START_FIELD)  # type: ignore[attr-defined]
                    if isinstance(raw_start, datetime):
                        start_time = ensure_utc(raw_start)
                raw_val: Any = cast(Any, (
                    message.get_value(self.SESSION_TOTAL_TIMER_FIELD)  # type: ignore[attr-defined]
                    or message.get_value(self.SESSION_TOTAL_ELAPSED_FIELD)  # type: ignore[attr-defined]
                ))
                if isinstance(raw_val, (int, float)):
                    duration_seconds = coerce_duration_seconds(raw_val)
                # Session-level totals
                raw_dist = message.get_value(self.SESSION_TOTAL_DISTANCE_FIELD)  # type: ignore[attr-defined]
                if isinstance(raw_dist, (int, float)):
                    # FIT distance is typically in mm (1000x scale)
                    total_distance_m = float(raw_dist) / 1000.0
                raw_elev = message.get_value(self.SESSION_TOTAL_ELEV_GAIN_FIELD)  # type: ignore[attr-defined]
                if isinstance(raw_elev, (int, float)):
                    # FIT elevation is typically in m (sometimes 10x for older files)
                    total_ascent_m = float(raw_elev)

                # Extract sport type from FIT sport message (Phase-2.1-P3)
                sport_int_raw = message.get_value("sport")  # type: ignore[attr-defined]
                sub_sport_int_raw = message.get_value("sub_sport")  # type: ignore[attr-defined]
                sport_int = sport_int_raw if isinstance(sport_int_raw, int) else None
                sub_sport_int = sub_sport_int_raw if isinstance(sub_sport_int_raw, int) else None
                sport_type, detection_confidence = _map_fit_sport_to_enum(sport_int, sub_sport_int)
                continue

            if message.name != "record":  # type: ignore[attr-defined]
                continue

            raw_hr = message.get_value(self.HR_FIELD)  # type: ignore[attr-defined]
            if isinstance(raw_hr, int) and 20 <= raw_hr <= 250:
                hr_records.append(raw_hr)

            raw_power = message.get_value(self.POWER_FIELD)  # type: ignore[attr-defined]
            if isinstance(raw_power, int) and 0 <= raw_power <= 2500:
                power_records.append(raw_power)

            # RR-interval values (milliseconds)
            raw_rr = message.get_value("rr_interval")  # type: ignore[attr-defined]
            if isinstance(raw_rr, (int, float)):
                # rr_interval can be a single float (gap to next beat)
                # or a list of intervals (in milliseconds)
                if isinstance(raw_rr, list):
                    rr_records.extend(raw_rr)
                else:
                    rr_records.append(float(raw_rr))

            # GPS records: position_lat, position_long, distance, altitude, speed
            raw_lat: Optional[float] = cast(Optional[float], message.get_value("position_lat"))  # type: ignore[attr-defined]
            raw_long: Optional[float] = cast(Optional[float], message.get_value("position_long"))  # type: ignore[attr-defined]
            raw_dist: Optional[float] = cast(Optional[float], message.get_value("distance"))  # type: ignore[attr-defined]
            raw_alt: Optional[float] = cast(Optional[float], message.get_value("altitude"))  # type: ignore[attr-defined]
            raw_speed: Optional[float] = cast(Optional[float], message.get_value("speed"))  # type: ignore[attr-defined]

            if raw_lat is not None or raw_long is not None:
                # We have GPS data on this record
                has_gps = True
                if isinstance(raw_lat, int):
                    raw_lat = raw_lat / 11930465.0  # Convert to degrees
                if isinstance(raw_long, int):
                    raw_long = raw_long / 11930465.0
                if isinstance(raw_dist, (int, float)):
                    raw_dist = float(raw_dist) / 1000.0  # mm to m
                if isinstance(raw_alt, (int, float)):
                    raw_alt = float(raw_alt) / 10.0  # dm to m
                if isinstance(raw_speed, (int, float)):
                    raw_speed = float(raw_speed)  # m/s

                gps_records.append(GpsRecord(
                    timestamp=message.timestamp if hasattr(message, 'timestamp') else start_time or datetime.now(timezone.utc),  # type: ignore[attr-defined]
                    position_lat=raw_lat,
                    position_long=raw_long,
                    distance=raw_dist,
                    altitude=raw_alt,
                    speed=raw_speed,
                ))

            if start_time is None:
                raw_ts = message.get_value(self.TIMESTAMP_FIELD)  # type: ignore[attr-defined]
                if isinstance(raw_ts, datetime):
                    start_time = ensure_utc(raw_ts)

        # Fall back to record-derived duration when the session
        # message did not carry a total_timer_time. The duration
        # becomes ``len(hr_records)`` (1 sample per second) — accurate
        # enough for Tier-3 / Tier-4 ingestion which is what Phase
        # 1.6 consumes.
        if duration_seconds <= 0 and hr_records:
            duration_seconds = len(hr_records)

        if start_time is None:
            raise FitParseError(
                "FIT file did not include a session.start_time or record "
                "timestamp; cannot derive start_time"
            )

        return ParsedFitData(
            start_time=start_time,
            duration_seconds=max(0, int(duration_seconds)),
            hr_records=hr_records,
            power_records=power_records,
            has_hr=bool(hr_records),
            has_power=bool(power_records),
            has_rr_intervals=bool(rr_records),
            gps_records=gps_records,
            rr_records=rr_records,
            total_distance_m=total_distance_m,
            total_ascent_m=total_ascent_m,
            has_gps=has_gps,
            moving_duration_seconds=duration_seconds,
            sport_type=sport_type,
            detection_confidence=detection_confidence,
            detection_version="v1",
        )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


class BytesReader:
    """Lightweight ``file-like`` wrapper that ``fitparse`` accepts.

    ``fitparse.FitFile`` accepts anything that exposes ``read`` /
    ``seek`` / ``tell``. Wrapping ``bytes`` in :class:`io.BytesIO`
    would also work, but a tiny wrapper keeps the parser
    implementation dependency-light.
    """

    __slots__ = ("_buffer", "_pos")

    def __init__(self, data: bytes) -> None:
        self._buffer = data
        self._pos = 0

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            chunk = self._buffer[self._pos :]
            self._pos = len(self._buffer)
            return chunk
        chunk = self._buffer[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk

    def seek(self, offset: int, whence: int = 0) -> int:
        if whence == 0:
            self._pos = offset
        elif whence == 1:
            self._pos += offset
        elif whence == 2:
            self._pos = len(self._buffer) + offset
        return self._pos

    def tell(self) -> int:
        return self._pos

    def close(self) -> None:  # pragma: no cover - trivial
        return None


def ensure_utc(value: datetime) -> datetime:
    """Return ``value`` coerced to UTC; naive values get UTC attached."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def coerce_duration_seconds(value: float | int) -> int:
    """Normalise FIT duration values to whole seconds.

    Some FIT producers emit the field already divided by 1000
    (seconds), others emit milliseconds. We round-trip via the
    magnitude heuristic: anything > 10000 is treated as
    milliseconds and divided by 1000.
    """
    numeric = float(value)
    if numeric > 10_000:
        return int(round(numeric / 1000))
    return int(round(numeric))


def _map_fit_sport_to_enum(sport: Optional[int], sub_sport: Optional[int]) -> tuple[SportType, str]:
    """Map FIT sport and sub_sport integers to SportType and confidence.

    Uses the Garmin/Ant+ sport mapping table from
    docs/architecture/02-computations/sport-type-detection.md.

    Args:
        sport: Raw FIT sport field integer (None if absent)
        sub_sport: Raw FIT sub_sport field integer (None if absent)

    Returns:
        Tuple of (SportType, detection_confidence) where confidence is:
        - "high": FIT sport field was present and mappable
        - "low": FIT sport field was present but unrecognized (defaulted to 'other')
        - "unknown": FIT sport field is absent, generic (0), or "all" (254)

    Mapping table:
        sport=1 (running) → SportType.RUNNING (sub_sport irrelevant)
        sport=2 (cycling) → SportType.CYCLING
        sport=3 (transition) → SportType.OTHER
        sport=4 (fitness_equipment) → SportType.STRENGTH
        sport=5 (swimming) → SportType.SWIMMING
        sport=14 (walking) → SportType.OTHER
        sport=0 (generic), 254 (all), or None → SportType.UNKNOWN
        unrecognized sport int → SportType.OTHER with "low" confidence
    """
    if sport is None or sport == 0 or sport == 254:
        return SportType.UNKNOWN, "unknown"

    if sport == 1:
        # Running — sub_sport is irrelevant for calibration eligibility
        return SportType.RUNNING, "high"
    if sport == 2:
        return SportType.CYCLING, "high"
    if sport == 3:
        # Transition
        return SportType.OTHER, "high"
    if sport == 4:
        # Fitness equipment
        return SportType.STRENGTH, "high"
    if sport == 5:
        return SportType.SWIMMING, "high"
    if sport == 14:
        # Walking
        return SportType.OTHER, "high"

    # Unrecognized sport integer — default to 'other' with low confidence
    return SportType.OTHER, "low"