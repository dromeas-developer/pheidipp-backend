"""Unit tests for FitParserService.

Tests the async parse() entry point and error handling.
The sync _parse_sync implementation is tested via patching to
return controlled ParsedFitData without requiring real FIT bytes.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.services.fit_parser_service import (
    FitParseEmptyError,
    FitParseError,
    FitParserService,
    ParsedFitData,
    _BytesReader,
    _coerce_duration_seconds,
    _ensure_utc,
)
from app.services.fit_parser_service import _BytesReader as BytesReader


class TestFitParserServiceParse:
    """async parse() method — calls _parse_sync in executor and handles errors."""

    def _mock_parsed_fit(
        self,
        hr_records=None,
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
            hr_records=hr_records if hr_records is not None else [120] * duration_seconds,
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
        import asyncio

        service = FitParserService()
        mock_result = self._mock_parsed_fit(hr_records=[120])

        # Must be a sync callable — run_in_executor calls it synchronously,
        # passing the coroutine object instead of its result if it's async.
        def _fake_parse_sync(bytes):
            return mock_result

        with patch.object(
            service, "_parse_sync", side_effect=_fake_parse_sync
        ) as mock_sync:
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

    def test_ensure_utc_naive_datetime(self) -> None:
        """Naive datetime gets UTC attached."""
        import datetime
        naive = datetime.datetime(2026, 6, 15, 8, 0, 0)
        result = _ensure_utc(naive)
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_ensure_utc_aware_datetime(self) -> None:
        """Aware datetime is converted to UTC."""
        import datetime
        eastern = datetime.timezone(datetime.timedelta(hours=-4))
        aware = datetime.datetime(2026, 6, 15, 8, 0, 0, tzinfo=eastern)
        result = _ensure_utc(aware)
        assert result.tzinfo == timezone.utc

    def test_coerce_duration_seconds_small_value(self) -> None:
        """Values <= 10000 are treated as seconds."""
        assert _coerce_duration_seconds(3600) == 3600
        assert _coerce_duration_seconds(0) == 0

    def test_coerce_duration_seconds_large_value_treated_as_ms(self) -> None:
        """Values > 10000 are treated as milliseconds and divided by 1000."""
        assert _coerce_duration_seconds(3600000) == 3600
        assert _coerce_duration_seconds(60000) == 60


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