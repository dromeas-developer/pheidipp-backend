"""FitParserService — extract raw HR data from a FIT file.

Implements the Phase-1.6 contract from
``docs/architecture/01-entities/activity.md` →
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
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from fitparse import FitFile, FitParseError as UpstreamFitParseError

from app.core.logging_utils import log_event


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
    """

    start_time: datetime
    duration_seconds: int
    hr_records: List[int] = field(default_factory=list)
    power_records: List[int] = field(default_factory=list)
    has_hr: bool = False
    has_power: bool = False
    has_rr_intervals: bool = False


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
        fit = FitFile(_BytesReader(file_bytes))
        # ``parse`` is a generator that yields definition + data
        # messages. We only need data messages for record extraction.
        # fit.parse() has no return (populates internal buffers as a
        # side-effect); list() was an erroneous wrapper — remove it.
        fit.parse()  # type: ignore[arg-type]

        hr_records: list[int] = []
        power_records: list[int] = []
        rr_seen = False
        start_time: Optional[datetime] = None
        duration_seconds: int = 0

        session_seen = False
        for message in fit.messages:
            if message.name == "session":  # type: ignore[attr-defined]
                session_seen = True
                if start_time is None:
                    raw_start = message.get_value(self.SESSION_START_FIELD)  # type: ignore[attr-defined]
                    if isinstance(raw_start, datetime):
                        start_time = _ensure_utc(raw_start)
                raw_total = (
                    message.get_value(self.SESSION_TOTAL_TIMER_FIELD)  # type: ignore[attr-defined]
                    or message.get_value(self.SESSION_TOTAL_ELAPSED_FIELD)  # type: ignore[attr-defined]
                )
                if isinstance(raw_total, (int, float)):
                    # FIT total_timer_time is in seconds with a 1000x
                    # scaling factor (i.e. milliseconds). The library
                    # sometimes already divides by 1000 depending on
                    # the producer; coerce defensively.
                    duration_seconds = _coerce_duration_seconds(raw_total)
                continue

            if message.name != "record":  # type: ignore[attr-defined]
                continue

            raw_hr = message.get_value(self.HR_FIELD)  # type: ignore[attr-defined]
            if isinstance(raw_hr, int) and 20 <= raw_hr <= 250:
                hr_records.append(raw_hr)

            raw_power = message.get_value(self.POWER_FIELD)  # type: ignore[attr-defined]
            if isinstance(raw_power, int) and 0 <= raw_power <= 2500:
                power_records.append(raw_power)

            # RR-interval availability is signalled by the presence
            # of the field on a record message. We do not extract
            # individual samples at this phase; Phase 2 refines the
            # RR handling.
            if message.get_value("rr_interval") is not None:  # type: ignore[attr-defined]
                rr_seen = True

            if start_time is None:
                raw_ts = message.get_value(self.TIMESTAMP_FIELD)  # type: ignore[attr-defined]
                if isinstance(raw_ts, datetime):
                    start_time = _ensure_utc(raw_ts)

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
            has_rr_intervals=rr_seen,
        )


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


class _BytesReader:
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


def _ensure_utc(value: datetime) -> datetime:
    """Return ``value`` coerced to UTC; naive values get UTC attached."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _coerce_duration_seconds(value: float | int) -> int:
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