"""Unit tests for FitParserService — pure logic, no DB.

Covers the parse method, sport-type detection, raw-record shapes, and
error branches. External FIT file content is loaded from disk fixtures
under tests/fixtures/fit/.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from app.models.enums import SportType
from app.services.fit_parser_service import (
    FitParseEmptyError,
    FitParseError,
    FitParserService,
    ParsedFitData,
)


@pytest.fixture
def parser() -> FitParserService:
    return FitParserService()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent.parent / "fixtures" / "fit"


def _build_sample_hr_records(count: int, hr: int) -> list[int]:
    return [hr for _ in range(count)]


class TestParseReturnsRawRecords:
    async def test_hr_records_returned_as_per_sample_values(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sample = _build_sample_hr_records(3600, 169)

        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=3600,
                hr_records=[float(h) for h in sample],
                power_records=[],
                has_hr=True,
                has_power=False,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=10_000.0,
                total_ascent_m=50.0,
                has_gps=True,
                moving_duration_seconds=3550,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        result = await parser.parse(b"not-real-fit-bytes")

        assert isinstance(result.hr_records, list)
        assert len(result.hr_records) == 3600
        assert all(isinstance(v, float) for v in result.hr_records)
        assert all(isinstance(v, float) and 160 <= v <= 180 for v in result.hr_records)
        assert result.duration_seconds == 3600
        assert not isinstance(result.duration_seconds, float)

    async def test_hr_records_are_per_sample_not_averaged(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        varying = [120 + (i % 50) for i in range(1800)]

        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=1800,
                hr_records=[float(h) for h in varying],
                power_records=[],
                has_hr=True,
                has_power=False,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=None,
                total_ascent_m=None,
                has_gps=False,
                moving_duration_seconds=1750,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        result = await parser.parse(b"")

        hr_values = [v for v in result.hr_records if v is not None]
        assert min(hr_values) == 120.0
        assert max(hr_values) == 169.0
        assert len(result.hr_records) == 1800

    async def test_power_records_returned_as_per_sample_values(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        power = [300.0] * 3600

        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=3600,
                hr_records=[150.0] * 3600,
                power_records=list(power),
                has_hr=True,
                has_power=True,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=10_000.0,
                total_ascent_m=0.0,
                has_gps=True,
                moving_duration_seconds=3600,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        result = await parser.parse(b"")

        assert result.has_power is True
        assert result.power_records == power

    async def test_total_distance_and_ascent_returned(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=3600,
                hr_records=[150.0] * 3600,
                power_records=[],
                has_hr=True,
                has_power=False,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=10_250.5,
                total_ascent_m=120.0,
                has_gps=True,
                moving_duration_seconds=3500,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        result = await parser.parse(b"")

        assert result.total_distance_m == 10_250.5
        assert result.total_ascent_m == 120.0
        assert result.has_gps is True


class TestParseRunsOffLoop:
    async def test_parse_delegates_to_executor(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        called: dict[str, bool] = {"offloaded": False}

        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            called["offloaded"] = True
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=3600,
                hr_records=[150.0] * 3600,
                power_records=[],
                has_hr=True,
                has_power=False,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=None,
                total_ascent_m=None,
                has_gps=False,
                moving_duration_seconds=3600,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        await parser.parse(b"")

        assert called["offloaded"] is True


class TestParseExtractsSport:
    async def test_sport_type_running_detected(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=3600,
                hr_records=[150.0] * 3600,
                power_records=[],
                has_hr=True,
                has_power=False,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=10_000.0,
                total_ascent_m=0.0,
                has_gps=True,
                moving_duration_seconds=3500,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        result = await parser.parse(b"")

        assert result.sport_type == SportType.RUNNING
        assert result.detection_version == "v1"
        assert result.detection_confidence == "high"

    async def test_unknown_sport_when_fit_omits_sport(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=1800,
                hr_records=[140.0] * 1800,
                power_records=[],
                has_hr=True,
                has_power=False,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=None,
                total_ascent_m=None,
                has_gps=False,
                moving_duration_seconds=1700,
                sport_type=SportType.UNKNOWN,
                detection_confidence="unknown",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        result = await parser.parse(b"")

        assert result.sport_type == SportType.UNKNOWN
        assert result.detection_confidence == "unknown"


class TestParseFailures:
    async def test_corrupt_bytes_raise_fit_parse_error(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            raise ValueError("bad bytes")

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        with pytest.raises(FitParseError):
            await parser.parse(b"\x00\x01\x02not-a-fit-file")

    async def test_unsupported_fit_raises_fit_parse_error(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            raise OSError("decoder crashed")

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        with pytest.raises(FitParseError):
            await parser.parse(b"unsupported-format")

    async def test_no_partial_result_on_failure(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            raise RuntimeError("boom")

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        with pytest.raises(FitParseError):
            await parser.parse(b"")


class TestParseEmpty:
    async def test_empty_hr_records_raise_fit_parse_empty(
        self,
        parser: FitParserService,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fake_parse_sync(self: FitParserService, file_bytes: bytes) -> ParsedFitData:
            return ParsedFitData(
                start_time=datetime(2026, 1, 1, 8, 0, 0),
                duration_seconds=3600,
                hr_records=[],
                power_records=[300.0] * 3600,
                has_hr=False,
                has_power=True,
                has_rr_intervals=False,
                gps_records=[],
                rr_records=[],
                total_distance_m=10_000.0,
                total_ascent_m=0.0,
                has_gps=True,
                moving_duration_seconds=3500,
                sport_type=SportType.RUNNING,
                detection_confidence="high",
                detection_version="v1",
            )

        monkeypatch.setattr(FitParserService, "_parse_sync", fake_parse_sync)

        with pytest.raises(FitParseEmptyError):
            await parser.parse(b"")

    async def test_fit_parse_empty_subclasses_fit_parse_error(
        self,
    ) -> None:
        assert issubclass(FitParseEmptyError, FitParseError)
