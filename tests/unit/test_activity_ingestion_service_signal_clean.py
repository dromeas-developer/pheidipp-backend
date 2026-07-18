"""Unit tests for the signal_clean enqueue hook in ActivityIngestionService.

Phase-2.2 adds the `_defer_signal_clean` call inside
`_run_ingestion_pipeline` after `twin_recalibration.recalibrate`
returns. These tests verify the gate conditions and failure-handling
behaviour.

Reference: docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
          docs/adr/009-signal-cleaning-as-decoupled-async-task.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import ActivitySource, HrSource, PowerSource, SportType
from app.services.activity_ingestion_service import ActivityIngestionService
from app.services.fit_parser_service import ParsedFitData
from app.services.load_computation_service import LoadScores


def _minimal_parsed_fit(
    sport_type: SportType = SportType.RUNNING,
) -> ParsedFitData:
    """Return a minimal ParsedFitData with the given sport_type.

    `start_time` MUST be a real datetime: production code at
    `app/services/activity_ingestion_service.py` calls
    `parsed.start_time.date()` unconditionally when stamping the
    activity row. A `None` start_time triggers
    `AttributeError: 'NoneType' object has no attribute 'date'`
    before any assertion in the test runs. See tests/README.md
    "Test fixtures must populate every field the production code
    reads unconditionally" (2026-07-09).
    """
    return ParsedFitData(
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=3600,
        hr_records=[150] * 3600,
        has_hr=True,
        sport_type=sport_type,
    )


def _mock_recalibration_result() -> MagicMock:
    mock_recal = MagicMock()
    mock_recal.twin_state = MagicMock()
    mock_recal.updated_form = 50.0
    return mock_recal


class TestSignalCleanEnqueueHook:
    """Verify signal_clean defer conditions inside _run_ingestion_pipeline."""

    @pytest.mark.asyncio
    async def test_signal_clean_deferred_when_eligible_running_non_manual(
        self,
    ) -> None:
        """signal_clean is deferred when the activity is calibration-eligible,
        sport_type is RUNNING, and source is not MANUAL_ENTRY."""
        activity_id = uuid.uuid4()
        athlete_id = uuid.uuid4()

        # Set up a mock dispatcher that records calls.
        defer_calls: list[dict[str, Any]] = []

        def mock_defer(**kwargs: Any) -> None:
            defer_calls.append(kwargs)

        # Build a mock activity.
        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        mock_activity.calibration_eligible = True
        mock_activity.sport_type = SportType.RUNNING
        mock_activity.source = ActivitySource.MANUAL_UPLOAD
        mock_activity.aerobic_load = None
        mock_activity.fit_file_key = "fit-files/athlete/2026-06-15/uuid.fit"
        mock_activity.quality_flags = {}

        # Mock athlete profile for max HR estimation.
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        # Mock athlete preferences for data tier inference.
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)

        # Mock athlete physiology for CP estimate.
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)

        service = ActivityIngestionService(
            session=AsyncMock(),
            task_dispatcher=mock_defer,
        )
        service.athlete_profiles = mock_profile_repo
        service.athlete_preferences = mock_prefs_repo
        service.athlete_physiology = mock_physio_repo

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(
            return_value=_minimal_parsed_fit(SportType.RUNNING)
        )

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(
            return_value=LoadScores(
                aerobic_load=100.0,
                neuromuscular_load=None,
                structural_load=None,
            )
        )

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(
            return_value=_mock_recalibration_result()
        )

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(
            return_value=True
        )

        service.events = AsyncMock()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fake fit",
        )

        # The defer was called with the activity_id.
        assert len(defer_calls) == 1
        assert defer_calls[0]["activity_id"] == str(activity_id)

    @pytest.mark.asyncio
    async def test_signal_clean_not_deferred_when_sport_type_not_running(
        self,
    ) -> None:
        """signal_clean is NOT deferred when sport_type != RUNNING,
        even if calibration_eligible were hypothetically true."""
        activity_id = uuid.uuid4()
        athlete_id = uuid.uuid4()

        defer_calls: list[dict[str, Any]] = []

        def mock_defer(**kwargs: Any) -> None:
            defer_calls.append(kwargs)

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        mock_activity.calibration_eligible = True
        mock_activity.sport_type = SportType.CYCLING  # Not running
        mock_activity.source = ActivitySource.MANUAL_UPLOAD
        mock_activity.aerobic_load = None
        mock_activity.fit_file_key = "fit-files/athlete/2026-06-15/uuid.fit"
        mock_activity.quality_flags = {}

        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)

        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)

        service = ActivityIngestionService(
            session=AsyncMock(),
            task_dispatcher=mock_defer,
        )
        service.athlete_profiles = mock_profile_repo
        service.athlete_preferences = mock_prefs_repo
        service.athlete_physiology = mock_physio_repo

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(
            return_value=_minimal_parsed_fit(SportType.CYCLING)
        )

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(
            return_value=LoadScores(
                aerobic_load=100.0,
                neuromuscular_load=None,
                structural_load=None,
            )
        )

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(
            return_value=_mock_recalibration_result()
        )

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(
            return_value=True
        )

        service.events = AsyncMock()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fake fit",
        )

        # No defer for cycling activities.
        assert len(defer_calls) == 0

    @pytest.mark.asyncio
    async def test_signal_clean_not_deferred_when_not_eligible(self) -> None:
        """signal_clean is NOT deferred when calibration_eligible is False."""
        activity_id = uuid.uuid4()
        athlete_id = uuid.uuid4()

        defer_calls: list[dict[str, Any]] = []

        def mock_defer(**kwargs: Any) -> None:
            defer_calls.append(kwargs)

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        mock_activity.calibration_eligible = False  # Not eligible
        mock_activity.sport_type = SportType.RUNNING
        mock_activity.source = ActivitySource.MANUAL_UPLOAD
        mock_activity.aerobic_load = None
        mock_activity.fit_file_key = "fit-files/athlete/2026-06-15/uuid.fit"
        mock_activity.quality_flags = {}

        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)

        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)

        service = ActivityIngestionService(
            session=AsyncMock(),
            task_dispatcher=mock_defer,
        )
        service.athlete_profiles = mock_profile_repo
        service.athlete_preferences = mock_prefs_repo
        service.athlete_physiology = mock_physio_repo

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(
            return_value=_minimal_parsed_fit(SportType.RUNNING)
        )

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(
            return_value=LoadScores(
                aerobic_load=100.0,
                neuromuscular_load=None,
                structural_load=None,
            )
        )

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(
            return_value=_mock_recalibration_result()
        )

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(
            return_value=False
        )

        service.events = AsyncMock()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fake fit",
        )

        # No defer when not eligible.
        assert len(defer_calls) == 0

    @pytest.mark.asyncio
    async def test_signal_clean_not_deferred_when_manual_entry(self) -> None:
        """signal_clean is NOT deferred when source = MANUAL_ENTRY
        (manual entries have no FIT file per the invariant)."""
        activity_id = uuid.uuid4()
        athlete_id = uuid.uuid4()

        defer_calls: list[dict[str, Any]] = []

        def mock_defer(**kwargs: Any) -> None:
            defer_calls.append(kwargs)

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        mock_activity.calibration_eligible = True
        mock_activity.sport_type = SportType.RUNNING
        mock_activity.source = ActivitySource.MANUAL_ENTRY  # Manual — no FIT
        mock_activity.aerobic_load = None
        mock_activity.fit_file_key = None  # Manual entries have no FIT key
        mock_activity.quality_flags = {}

        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)

        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)

        service = ActivityIngestionService(
            session=AsyncMock(),
            task_dispatcher=mock_defer,
        )
        service.athlete_profiles = mock_profile_repo
        service.athlete_preferences = mock_prefs_repo
        service.athlete_physiology = mock_physio_repo

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(
            return_value=_minimal_parsed_fit(SportType.RUNNING)
        )

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(
            return_value=LoadScores(
                aerobic_load=100.0,
                neuromuscular_load=None,
                structural_load=None,
            )
        )

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(
            return_value=_mock_recalibration_result()
        )

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(
            return_value=True
        )

        service.events = AsyncMock()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fake fit",
        )

        # No defer for manual entries.
        assert len(defer_calls) == 0

    @pytest.mark.asyncio
    async def test_signal_clean_defer_failure_is_swallowed(self) -> None:
        """When _defer_signal_clean raises (queue backend outage), the
        exception is swallowed so the ingestion commit path still succeeds.
        Per the plan: 'If the defer call itself raises, swallow it and log
        activity.signal_clean.enqueue.failure — the ingestion commit MUST
        still succeed.'"""
        activity_id = uuid.uuid4()
        athlete_id = uuid.uuid4()

        def mock_defer(**kwargs: Any) -> None:
            raise RuntimeError("queue backend unavailable")

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.athlete_id = athlete_id
        mock_activity.calibration_eligible = True
        mock_activity.sport_type = SportType.RUNNING
        mock_activity.source = ActivitySource.MANUAL_UPLOAD
        mock_activity.aerobic_load = None
        mock_activity.fit_file_key = "fit-files/athlete/2026-06-15/uuid.fit"
        mock_activity.quality_flags = {}

        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)

        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)

        service = ActivityIngestionService(
            session=AsyncMock(),
            task_dispatcher=mock_defer,
        )
        service.athlete_profiles = mock_profile_repo
        service.athlete_preferences = mock_prefs_repo
        service.athlete_physiology = mock_physio_repo

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(
            return_value=_minimal_parsed_fit(SportType.RUNNING)
        )

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(
            return_value=LoadScores(
                aerobic_load=100.0,
                neuromuscular_load=None,
                structural_load=None,
            )
        )

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(
            return_value=_mock_recalibration_result()
        )

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(
            return_value=True
        )

        service.events = AsyncMock()

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        # The pipeline MUST NOT raise even though the defer failed.
        # The pipeline completes successfully; only the signal_clean
        # enqueue was missed (recoverable via backfill per Principle #14).
        await service.run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fake fit",
        )

        # Pipeline completed without raising.
        mock_repo.update_load_scores.assert_called_once()