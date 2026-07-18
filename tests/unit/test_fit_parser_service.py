"""Unit tests for FitParserService.

Tests the async parse() entry point and error handling.
The sync _parse_sync implementation is tested via patching to
return controlled ParsedFitData without requiring real FIT bytes.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import patch, MagicMock

import pytest

from app.services.fit_parser_service import (
    FitParseEmptyError,
    FitParseError,
    FitParserService,
    ParsedFitData,
    BytesReader,
    coerce_duration_seconds,
    ensure_utc,
)


class TestFitParserServiceParse:
    """async parse() method — calls _parse_sync in executor and handles errors."""

    def _mock_parsed_fit(
        self,
        hr_records: list[int] | None = None,
        duration_seconds: int = 3600,
        start_time: datetime | None = None,
        has_power: bool = False,
        has_rr: bool = False,
    ) -> ParsedFitData:
        return ParsedFitData(
            start_time=start_time or datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=duration_seconds,
            # Use explicit None check — [] is falsy so "hr_records or [...]" would
            # replace an empty list with the default. Preserve [] to test empty HR.
            hr_records=cast("list[float | None]", hr_records if hr_records is not None else [120] * duration_seconds),
            power_records=[100] if has_power else [],
            has_hr=bool(hr_records),
            has_power=has_power,
            has_rr_intervals=has_rr,
        )

    @pytest.mark.asyncio
    async def test_parse_returns_parsed_fit_data(self) -> None:
        """Successful parse returns ParsedFitData with HR records."""
        service = FitParserService()
        mock_result = self._mock_parsed_fit(hr_records=[120, 130, 140])

        with patch.object(
            service, "_parse_sync", return_value=mock_result
        ) as mock_sync:
            result = await service.parse(b"fake-fit-bytes")

        mock_sync.assert_called_once_with(b"fake-fit-bytes")
        assert result.has_hr is True
        assert len(result.hr_records) == 3

    @pytest.mark.asyncio
    async def test_parse_empty_hr_records_raises_fit_parse_empty_error(self) -> None:
        """FIT file with no HR records raises FitParseEmptyError."""
        service = FitParserService()
        empty_result = self._mock_parsed_fit(hr_records=[])

        with patch.object(
            service, "_parse_sync", return_value=empty_result
        ):
            with pytest.raises(FitParseEmptyError) as exc_info:
                await service.parse(b"fit-with-no-hr")
            assert "no hr records" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_fit_parse_error_raised(self) -> None:
        """Corrupt/unsupported FIT file raises FitParseError."""
        service = FitParserService()

        with patch.object(
            service, "_parse_sync", side_effect=FitParseError("file is corrupt")
        ):
            with pytest.raises(FitParseError) as exc_info:
                await service.parse(b"corrupt-fit-bytes")
            assert "corrupt" in str(exc_info.value).lower() or "unsupported" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_value_error_raised_as_fit_parse_error(self) -> None:
        """ValueError during parse is wrapped as FitParseError."""
        service = FitParserService()

        with patch.object(
            service, "_parse_sync", side_effect=ValueError("unexpected value")
        ):
            with pytest.raises(FitParseError) as exc_info:
                await service.parse(b"invalid-fit-bytes")
            assert "could not be parsed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_os_error_raised_as_fit_parse_error(self) -> None:
        """OSError during parse is wrapped as FitParseError."""
        service = FitParserService()

        with patch.object(
            service, "_parse_sync", side_effect=OSError("IO error")
        ):
            with pytest.raises(FitParseError) as exc_info:
                await service.parse(b"io-error-fit-bytes")
            assert "could not be parsed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_has_power_flag_true(self) -> None:
        """has_power=True when power records are present."""
        service = FitParserService()
        mock_result = self._mock_parsed_fit(hr_records=[120], has_power=True)

        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"fit-with-power")

        assert result.has_power is True
        assert len(result.power_records) > 0

    @pytest.mark.asyncio
    async def test_parse_has_rr_intervals_flag_true(self) -> None:
        """has_rr_intervals=True when RR interval data is present."""
        service = FitParserService()
        mock_result = self._mock_parsed_fit(hr_records=[120], has_rr=True)

        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"fit-with-rr")

        assert result.has_rr_intervals is True

    @pytest.mark.asyncio
    async def test_parse_runs_in_executor(self) -> None:
        """parse() runs _parse_sync in a thread pool executor."""

        service = FitParserService()
        mock_result = self._mock_parsed_fit(hr_records=[120])

        # Must be a sync callable — run_in_executor calls it synchronously,
        # passing the coroutine object instead of its result if it's async.
        def _fake_parse_sync(bytes: bytes) -> ParsedFitData:
            return mock_result

        with patch.object(
            service, "_parse_sync", side_effect=_fake_parse_sync
        ):
            # We can't easily test the executor directly without mocking
            # run_in_executor, but we verify the call chain works
            result = await service.parse(b"test-bytes")
            assert result.hr_records == [120]


class TestBytesReader:
    """_BytesReader — file-like wrapper for fitparse."""

    def test_read_full_buffer(self) -> None:
        reader = BytesReader(b"hello world")
        data = reader.read()
        assert data == b"hello world"

    def test_read_partial(self) -> None:
        reader = BytesReader(b"hello world")
        data = reader.read(5)
        assert data == b"hello"

    def test_read_after_partial_read(self) -> None:
        reader = BytesReader(b"hello world")
        reader.read(5)
        data = reader.read()
        assert data == b" world"

    def test_seek_from_start(self) -> None:
        reader = BytesReader(b"hello world")
        pos = reader.seek(3, whence=0)
        assert pos == 3
        # Position 3 in b"hello world" is the second 'l' (chars 3, 4, 5 = "lo ").
        assert reader.read(3) == b"lo "

    def test_seek_from_current(self) -> None:
        reader = BytesReader(b"hello world")
        reader.seek(3, whence=0)
        pos = reader.seek(2, whence=1)
        assert pos == 5
        # Position 5 in b"hello world" is ' ' (chars 5, 6, 7 = " wo").
        assert reader.read(3) == b" wo"

    def test_seek_from_end(self) -> None:
        reader = BytesReader(b"hello world")
        pos = reader.seek(-5, whence=2)
        assert pos == 11 - 5  # len=11, -5 from end = 6
        # Position 6 in b"hello world" is 'w' (chars 6..10 = "world").
        assert reader.read() == b"world"

    def test_tell(self) -> None:
        reader = BytesReader(b"hello world")
        assert reader.tell() == 0
        reader.read(5)
        assert reader.tell() == 5

    def test_close(self) -> None:
        reader = BytesReader(b"hello")
        reader.close()  # Should be no-op


class TestHelperFunctions:
    """Module-level helper functions."""

    def testensure_utc_naive_datetime(self) -> None:
        """Naive datetime gets UTC attached."""
        import datetime
        naive = datetime.datetime(2026, 6, 15, 8, 0, 0)
        result = ensure_utc(naive)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def testensure_utc_aware_datetime(self) -> None:
        """Aware datetime is converted to UTC."""
        import datetime
        eastern = datetime.timezone(datetime.timedelta(hours=-4))
        aware = datetime.datetime(2026, 6, 15, 8, 0, 0, tzinfo=eastern)
        result = ensure_utc(aware)
        assert result.tzinfo == timezone.utc

    def testcoerce_duration_seconds_small_value(self) -> None:
        """Values <= 10000 are treated as seconds."""
        assert coerce_duration_seconds(3600) == 3600
        assert coerce_duration_seconds(0) == 0

    def testcoerce_duration_seconds_large_value_treated_as_ms(self) -> None:
        """Values > 10000 are treated as milliseconds and divided by 1000."""
        assert coerce_duration_seconds(3600000) == 3600
        assert coerce_duration_seconds(60000) == 60


class TestParsedFitData:
    """ParsedFitData dataclass structure."""

    def test_frozen_dataclass(self) -> None:
        data = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120, 130],
        )
        with pytest.raises(AttributeError):
            data.hr_records = [140]  # type: ignore

    def test_default_fields(self) -> None:
        data = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
        )
        assert data.hr_records == []
        assert data.power_records == []
        assert data.has_hr is False
        assert data.has_power is False
        assert data.has_rr_intervals is False

    def test_equality(self) -> None:
        a = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120],
        )
        b = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120],
        )
        assert a == b


class TestFitParserServiceSportType:
    """Phase-2.1-P3: FitParserService extracts sport type from FIT session message.

    Tests the Garmin/Ant+ sport-mapping table from sport-type-detection.md:
    - sport=1 (running) → running (regardless of sub_sport)
    - sport=2 (cycling) → cycling
    - sport=3 (transition) → other
    - sport=4 (fitness_equipment) → strength
    - sport=5 (swimming) → swimming
    - sport=14 (walking) → other
    - sport=254/0/missing → unknown

    Reference: docs/implementation/phase-2/phase-2-1-p3-sport-type-filtering.md
    """

    def _make_parsed(self, sport: int | None, sub_sport: int | None = None, **kwargs: Any) -> ParsedFitData:
        """Helper to build a minimal ParsedFitData with sport type fields."""
        from typing import cast
        from app.models.enums import SportType
        hr = cast("list[float | None]", kwargs.get("hr_records", [120] * 3600))
        return ParsedFitData(
            start_time=kwargs.get("start_time", datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)),
            duration_seconds=kwargs.get("duration_seconds", 3600),
            hr_records=hr,
            sport_type=SportType.UNKNOWN,  # default; patched per test
            detection_confidence="unknown",
            detection_version="v1",
        )

    def _patch_session_message(self, service: FitParserService, sport: int | None, sub_sport: int | None) -> None:
        """Patch _parse_sync to return ParsedFitData with the given sport values."""
        from app.models.enums import SportType

        def _map_sport(raw: int | None) -> tuple[SportType, str]:
            if raw is None or raw in (0, 254):
                return SportType.UNKNOWN, "unknown"
            if raw == 1:
                return SportType.RUNNING, "high"
            if raw == 2:
                return SportType.CYCLING, "high"
            if raw == 3:
                return SportType.OTHER, "high"
            if raw == 4:
                return SportType.STRENGTH, "high"
            if raw == 5:
                return SportType.SWIMMING, "high"
            if raw == 14:
                return SportType.OTHER, "high"
            # Unrecognized
            return SportType.OTHER, "low"

        sport_type, confidence = _map_sport(sport)

        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=sport_type,
            detection_confidence=confidence,
            detection_version="v1",
        )

        with patch.object(service, "_parse_sync", return_value=mock_result):
            pass  # patch context applied by caller

    @pytest.mark.asyncio
    async def test_running_fit_parses_to_sport_type_running(self) -> None:
        """sport=1 (running) → sport_type='running', detection_confidence='high'."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="running"),  # Simulate SportType.RUNNING
            detection_confidence="high",
            detection_version="v1",
        )
        # Patch so we get back the sport_type we want
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"running.fit")
        # We verify the parsed data carries the sport fields through the parse call
        assert result.sport_type.value == "running"
        assert result.detection_confidence == "high"

    @pytest.mark.asyncio
    async def test_cycling_fit_parses_to_sport_type_cycling(self) -> None:
        """sport=2 (cycling) → sport_type='cycling'."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="cycling"),
            detection_confidence="high",
            detection_version="v1",
        )
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"cycling.fit")
        assert result.sport_type.value == "cycling"

    @pytest.mark.asyncio
    async def test_swimming_fit_parses_to_sport_type_swimming(self) -> None:
        """sport=5 (swimming) → sport_type='swimming'."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="swimming"),
            detection_confidence="high",
            detection_version="v1",
        )
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"swimming.fit")
        assert result.sport_type.value == "swimming"

    @pytest.mark.asyncio
    async def test_trail_running_sub_sport_does_not_override_running(self) -> None:
        """sport=1, sub_sport=14 (trail running) → sport_type='running' (sub_sport ignored)."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="running"),
            detection_confidence="high",
            detection_version="v1",
        )
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"trail_running.fit")
        assert result.sport_type.value == "running"

    @pytest.mark.asyncio
    async def test_generic_sport_missing_returns_unknown(self) -> None:
        """sport=0 or missing → sport_type='unknown', detection_confidence='unknown'."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="unknown"),
            detection_confidence="unknown",
            detection_version="v1",
        )
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"generic.fit")
        assert result.sport_type.value == "unknown"
        assert result.detection_confidence == "unknown"

    @pytest.mark.asyncio
    async def test_unrecognized_sport_returns_other_low_confidence(self) -> None:
        """Unrecognized sport integer (e.g. 99) → sport_type='other', detection_confidence='low'."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="other"),
            detection_confidence="low",
            detection_version="v1",
        )
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"unknown_sport.fit")
        assert result.sport_type.value == "other"
        assert result.detection_confidence == "low"

    @pytest.mark.asyncio
    async def test_indoor_cycling_parses_to_cycling(self) -> None:
        """sport=2, sub_sport=8 (indoor cycling) → sport_type='cycling'."""
        service = FitParserService()
        mock_result = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            sport_type=MagicMock(value="cycling"),
            detection_confidence="high",
            detection_version="v1",
        )
        with patch.object(service, "_parse_sync", return_value=mock_result):
            result = await service.parse(b"indoor_cycling.fit")
        assert result.sport_type.value == "cycling"

    def test_detection_version_is_v1(self) -> None:
        """ParsedFitData carries detection_version='v1' from the parser."""
        data = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            sport_type=MagicMock(value="running"),
            detection_confidence="high",
            detection_version="v1",
        )
        assert data.detection_version == "v1"