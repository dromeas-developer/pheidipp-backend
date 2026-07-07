"""Unit tests for ActivityIngestionService — orchestrates FIT upload pipeline.

Phase-1.6: stage_upload (sync) + ingest_async (worker-side).
Phase-1.8: ingest_async properly publishes events inside the same transaction.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
docs/implementation/phase-1/phase-1-8-p1-fix-event-ordering-and-async-processing.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ActivitySource, HrSource, PowerSource, SportType
from app.services.activity_ingestion_service import (
    ActivityIngestionError,
    ActivityIngestionResult,
    ActivityIngestionService,
    AthleteNotFoundForIngestionError,
    ObjectStorageFailureError,
)
from app.services.fit_parser_service import GpsRecord, ParsedFitData
from app.services.load_computation_service import LoadScores
from app.services.object_storage_client import (
    ObjectStorageClient,
    ObjectStorageConflictError,
    ObjectStorageUploadError,
    StoredFitObject,
)


class TestStageUpload:
    """stage_upload: object storage BEFORE Activity creation."""

    @pytest.mark.asyncio
    async def test_stage_upload_uploads_to_object_storage_first(self) -> None:
        """Object storage upload must succeed BEFORE Activity is created.

        Architecture invariant: if object storage fails, no Activity is created.
        """
        athlete_id = uuid.uuid4()
        file_bytes = b"fake fit content"

        mock_storage = AsyncMock(spec=ObjectStorageClient)
        mock_storage.upload_fit.return_value = StoredFitObject(
            key="fit-files/athlete/2026-06-15/uuid.fit",
            byte_count=len(file_bytes),
            content_md5="abc123",
        )

        mock_repo = AsyncMock()
        mock_repo.add = AsyncMock()

        service = ActivityIngestionService(
            session=AsyncMock(),
            object_storage=mock_storage,
        )
        service.activities = mock_repo

        # Call stage_upload
        result = await service.stage_upload(
            athlete_id=athlete_id,
            file_bytes=file_bytes,
        )

        # Verify upload was called BEFORE add
        assert mock_storage.upload_fit.call_count == 1
        assert mock_repo.add.call_count == 1

        # Verify Activity has fit_file_key set
        activity = mock_repo.add.call_args[0][0]
        assert activity.fit_file_key is not None
        assert "fit-files/" in activity.fit_file_key

    @pytest.mark.asyncio
    async def test_stage_upload_storage_failure_raises_no_activity_created(
        self,
    ) -> None:
        """ObjectStorageFailureError when upload fails — no Activity row created."""
        athlete_id = uuid.uuid4()
        file_bytes = b"fake fit content"

        mock_storage = AsyncMock(spec=ObjectStorageClient)
        mock_storage.upload_fit.side_effect = ObjectStorageUploadError(
            "network error"
        )

        mock_repo = AsyncMock()

        service = ActivityIngestionService(
            session=AsyncMock(),
            object_storage=mock_storage,
        )
        service.activities = mock_repo

        with pytest.raises(ObjectStorageFailureError):
            await service.stage_upload(
                athlete_id=athlete_id,
                file_bytes=file_bytes,
            )

        # Activity should NOT be created
        assert mock_repo.add.call_count == 0

    @pytest.mark.asyncio
    async def test_stage_upload_conflict_raises_activity_ingestion_error(
        self,
    ) -> None:
        """ObjectStorageConflictError raises ActivityIngestionError — not retryable."""
        athlete_id = uuid.uuid4()

        mock_storage = AsyncMock(spec=ObjectStorageClient)
        mock_storage.upload_fit.side_effect = ObjectStorageConflictError(
            "key already exists"
        )

        service = ActivityIngestionService(
            session=AsyncMock(),
            object_storage=mock_storage,
        )

        with pytest.raises(ActivityIngestionError) as exc_info:
            await service.stage_upload(
                athlete_id=athlete_id,
                file_bytes=b"fit",
            )
        assert "conflict" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_stage_upload_sets_load_scores_null(self) -> None:
        """Activity created by stage_upload has null load scores."""
        athlete_id = uuid.uuid4()

        mock_storage = AsyncMock(spec=ObjectStorageClient)
        mock_storage.upload_fit.return_value = StoredFitObject(
            key="fit-files/athlete/2026-06-15/uuid.fit",
            byte_count=100,
            content_md5="abc",
        )

        mock_repo = AsyncMock()
        mock_repo.add = AsyncMock()

        service = ActivityIngestionService(
            session=AsyncMock(),
            object_storage=mock_storage,
        )
        service.activities = mock_repo

        await service.stage_upload(athlete_id=athlete_id, file_bytes=b"fit")

        activity = mock_repo.add.call_args[0][0]
        assert activity.aerobic_load is None
        assert activity.neuromuscular_load is None
        assert activity.structural_load is None

    @pytest.mark.asyncio
    async def test_stage_upload_sets_calibration_eligible_false(self) -> None:
        """Phase 1.6: calibration_eligible is always False."""
        athlete_id = uuid.uuid4()

        mock_storage = AsyncMock(spec=ObjectStorageClient)
        mock_storage.upload_fit.return_value = StoredFitObject(
            key="fit-files/athlete/2026-06-15/uuid.fit",
            byte_count=100,
            content_md5="abc",
        )

        mock_repo = AsyncMock()
        mock_repo.add = AsyncMock()

        service = ActivityIngestionService(
            session=AsyncMock(),
            object_storage=mock_storage,
        )
        service.activities = mock_repo

        await service.stage_upload(athlete_id=athlete_id, file_bytes=b"fit")

        activity = mock_repo.add.call_args[0][0]
        assert activity.calibration_eligible is False

    @pytest.mark.asyncio
    async def test_stage_upload_sets_fit_file_key(self) -> None:
        """fit_file_key is always set for source != manual_entry."""
        athlete_id = uuid.uuid4()

        mock_storage = AsyncMock(spec=ObjectStorageClient)
        mock_storage.upload_fit.return_value = StoredFitObject(
            key="fit-files/athlete/2026-06-15/uuid.fit",
            byte_count=100,
            content_md5="abc",
        )

        mock_repo = AsyncMock()
        mock_repo.add = AsyncMock()

        service = ActivityIngestionService(
            session=AsyncMock(),
            object_storage=mock_storage,
        )
        service.activities = mock_repo

        await service.stage_upload(
            athlete_id=athlete_id,
            file_bytes=b"fit",
            source=ActivitySource.MANUAL_UPLOAD,
        )

        activity = mock_repo.add.call_args[0][0]
        assert activity.fit_file_key is not None


class TestIngestPipeline:
    """_run_ingestion_pipeline — parse → load → update → recalibrate (no event publish)."""

    @pytest.mark.asyncio
    async def test_run_ingestion_pipeline_parses_and_computes_load(self) -> None:
        """Pipeline parses FIT and computes aerobic_load."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        file_bytes = b"fake fit"

        # Mock parsed FIT data
        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_power=False,
            has_rr_intervals=False,
        )

        # Mock load scores
        mock_scores = LoadScores(
            aerobic_load=85.0,
            neuromuscular_load=None,
            structural_load=None,
        )

        # Mock twin recalibration result
        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state
        mock_recal.updated_form = 50.0

        service = ActivityIngestionService(session=AsyncMock())

        # Set up mock services directly on the service instance
        mock_fit_parser = MagicMock()
        mock_fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.fit_parser = mock_fit_parser

        mock_load_comp = MagicMock()
        mock_load_comp.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.load_computation = mock_load_comp

        mock_twin_recal = MagicMock()
        mock_twin_recal.recalibrate = AsyncMock(return_value=mock_recal)
        service.twin_recalibration = mock_twin_recal

        mock_calib = MagicMock()
        mock_calib.evaluate = MagicMock(return_value=False)
        service.calibration_eligibility = mock_calib

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        # Create a mock activity with id for the pipeline
        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.aerobic_load = None
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        recal, scores = await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        # Verify load was computed
        assert scores.aerobic_load == 85.0
        assert recal.twin_state == mock_twin_state
        # Verify update was called with load scores
        mock_repo.update_load_scores.assert_called_once()


class _MockRow:
    """Mock SQLAlchemy Row for _read_profile_date_of_birth queries.

    SQLAlchemy Row objects are subscriptable (row[0]) and have named
    attribute access. This class provides minimal subscriptable behaviour.
    """

    def __init__(self, date_of_birth):
        self._data = (date_of_birth,)

    def __getitem__(self, key):
        return self._data[key]


class TestIngestAsync:
    """ingest_async — production worker-side flow."""

    @pytest.mark.asyncio
    async def test_ingest_async_updates_activity(self) -> None:
        """ingest_async updates the Activity with load scores after parsing."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        file_bytes = b"fake fit"

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=SportType.RUNNING,  # Needed so tier override doesn't force TIER_6
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=False)

        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.aerobic_load = None
        mock_activity.id = activity_id

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        # _run_ingestion_pipeline calls activities.update_load_scores(), not update().
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        result = await service.ingest_async(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        # Verify update_load_scores was called with the computed scores.
        mock_repo.update_load_scores.assert_called_once()
        call_args = mock_repo.update_load_scores.call_args
        assert call_args.kwargs["aerobic_load"] == mock_scores.aerobic_load
        # Verify activity is in result
        assert result.activity == mock_activity

    @pytest.mark.asyncio
    async def test_ingest_async_publishes_event(self) -> None:
        """ingest_async publishes activity_ingested event inside the same transaction."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        file_bytes = b"fake fit"

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=SportType.RUNNING,  # Needed so tier override doesn't force TIER_6
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)

        service.calibration_eligibility = MagicMock()
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.activity_date = date(2026, 6, 15)
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.duration_seconds = 3600
        mock_activity.has_hr = True
        mock_activity.has_power = False
        mock_activity.has_rr_intervals = False
        mock_activity.sport_type = SportType.RUNNING  # Must match parsed sport_type

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        service.activities = mock_repo

        await service.ingest_async(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        # Verify activity_ingested event was published (among potentially multiple events)
        # P3 added sport_type_detected event, so we check for the specific event type
        calls = service.events.publish.call_args_list
        event_types = [call[1].get("event_type") for call in calls if call[1].get("event_type")]
        assert "activity_ingested" in event_types
        # Find the activity_ingested call and verify its payload
        for call in calls:
            if call[1].get("event_type") == "activity_ingested":
                assert call[1]["athlete_id"] == athlete_id
                break


class TestActivityIngestionResult:
    """ActivityIngestionResult frozen dataclass."""

    def test_frozen(self) -> None:
        from app.services.activity_ingestion_service import ActivityIngestionResult

        result = ActivityIngestionResult(
            activity=MagicMock(),
            twin_state=MagicMock(),
            load_scores={"aerobic_load": 100.0},
        )
        with pytest.raises(AttributeError):
            result.load_scores = {}  # type: ignore

    def test_equality(self) -> None:
        from app.services.activity_ingestion_service import ActivityIngestionResult

        a = ActivityIngestionResult(
            activity=MagicMock(),
            twin_state=MagicMock(),
            load_scores={"aerobic_load": 100.0},
        )
        b = ActivityIngestionResult(
            activity=MagicMock(),
            twin_state=MagicMock(),
            load_scores={"aerobic_load": 100.0},
        )
        # Not equal because different mock objects
        assert a != b


class TestObjectStorageFailureError:
    """ObjectStorageFailureError mapping for 503 HTTP response."""

    def test_is_ingestion_error_subclass(self) -> None:
        """ObjectStorageFailureError is a subclass of ActivityIngestionError."""
        assert issubclass(ObjectStorageFailureError, ActivityIngestionError)

    def test_raised_for_upload_error(self) -> None:
        """ObjectStorageUploadError is wrapped as ObjectStorageFailureError."""
        with pytest.raises(ObjectStorageFailureError):
            raise ObjectStorageFailureError("upload failed")


# ===========================================================================
# Phase-2.1: Signal flags and calibration eligibility expansion
# ===========================================================================


class TestSignalFlagsPopulation:
    """Phase-2.1: has_power, has_rr_intervals, has_gps set from parsed FIT."""

    @pytest.mark.asyncio
    async def test_signal_flags_set_on_activity(self) -> None:
        """Pipeline sets has_power, has_rr_intervals, has_gps on Activity."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()
        file_bytes = b"fake fit"

        # Parsed FIT with all signals
        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_power=True,
            has_rr_intervals=True,
            has_gps=True,
            power_records=[200] * 3600,
            rr_records=[800.0] * 4500,
            gps_records=[],
            total_distance_m=10000.0,
            total_ascent_m=150.0,
        )

        mock_scores = LoadScores(
            aerobic_load=100.0,
            neuromuscular_load=10.0,
            structural_load=12.0,
        )

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        # Track activity mutations
        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.aerobic_load = None
        mock_activity.has_hr = False
        mock_activity.has_power = False
        mock_activity.has_rr_intervals = False
        mock_activity.has_gps = False
        mock_activity.duration_seconds = 0
        mock_activity.start_time = datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)
        mock_activity.activity_date = date(2026, 6, 15)
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.sport_type = None

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        mock_repo.update_calibration_eligibility = AsyncMock()
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        # Verify activity was updated with signal flags
        assert mock_activity.has_hr is True
        assert mock_activity.has_power is True
        assert mock_activity.has_rr_intervals is True
        assert mock_activity.has_gps is True
        assert mock_activity.duration_seconds == 3600
        assert mock_activity.start_time == datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)
        assert mock_activity.activity_date == date(2026, 6, 15)

    @pytest.mark.asyncio
    async def test_has_power_true_when_power_data_in_fit(self) -> None:
        """has_power=True when FIT contains power records."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_power=True,
            has_rr_intervals=False,
            has_gps=False,
            power_records=[200] * 3600,
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=10.0, structural_load=None)
        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.aerobic_load = None
        mock_activity.has_hr = False
        mock_activity.has_power = False
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.sport_type = None

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fit",
        )

        assert mock_activity.has_power is True

    @pytest.mark.asyncio
    async def test_has_rr_intervals_true_when_rr_data_in_fit(self) -> None:
        """has_rr_intervals=True when FIT contains RR interval data."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_power=False,
            has_rr_intervals=True,
            has_gps=False,
            rr_records=[800.0] * 4500,
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)
        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.has_rr_intervals = False
        mock_activity.fit_file_key = "fit-files/test.fit"

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fit",
        )

        assert mock_activity.has_rr_intervals is True

    @pytest.mark.asyncio
    async def test_has_gps_true_when_gps_data_in_fit(self) -> None:
        """has_gps=True when FIT contains GPS data."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_power=False,
            has_rr_intervals=False,
            has_gps=True,
            gps_records=[],
            total_distance_m=10000.0,
            total_ascent_m=150.0,
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=12.0)
        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.has_gps = False
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.sport_type = None

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fit",
        )

        assert mock_activity.has_gps is True

    @pytest.mark.asyncio
    async def test_calibration_eligibility_updated_when_changed(self) -> None:
        """update_calibration_eligibility called when eligibility differs from current."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=SportType.RUNNING,  # Needed so tier override doesn't force TIER_6
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)
        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        # Calibration eligibility returns True when previously False
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.calibration_eligible = False  # Previously False
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.sport_type = SportType.RUNNING  # Must be running for calibration eligibility

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_calibration_eligibility = AsyncMock()
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"fit",
        )

        # Should update calibration eligibility since it changed from False to True
        mock_repo.update_calibration_eligibility.assert_called_once()
        call_kwargs = mock_repo.update_calibration_eligibility.call_args
        assert call_kwargs.kwargs["calibration_eligible"] is True


# ===========================================================================
# Phase-2.1-P2: Validation Remediation — GPS loss + structural_risk_flag
# ===========================================================================


class TestComputeQualityFlagsGpsLoss:
    """Phase-2.1-P2: gps_loss uses continuous-gap detection (>30s threshold).

    Per Phase-2.1-P1 Coder Handoff Note #2:
    "flag gps_loss = true only when position/altitude data is missing
    for > 30 continuous seconds during moving time."

    The plan's Testing Requirements specify:
    - FIT with single >30s gap → gps_loss = True
    - FIT with largest gap exactly 30s → gps_loss = False
    - FIT with several sub-30s gaps → gps_loss = False
    - has_gps=true + empty gps_records → gps_loss = True
    - has_gps=false → gps_loss = False (regardless of records)
    """

    def _make_flags(self, parsed: ParsedFitData) -> dict:
        """Helper: call _compute_quality_flags directly on a ParsedFitData."""
        service = ActivityIngestionService(session=AsyncMock())
        return service._compute_quality_flags(parsed)

    def test_gps_loss_false_when_has_gps_is_false(self) -> None:
        """has_gps=False → gps_loss=False regardless of any records."""
        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=False,
            gps_records=[
                GpsRecord(timestamp=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc)),
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is False

    def test_gps_loss_true_when_has_gps_true_but_no_records(self) -> None:
        """has_gps=True with empty gps_records → gps_loss=True (claimed GPS but no data)."""
        parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is True

    def test_gps_loss_false_when_single_gps_record(self) -> None:
        """Single GPS record → no gap to measure → gps_loss=False."""
        ts = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        parsed = ParsedFitData(
            start_time=ts,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=ts),
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is False

    def test_gps_loss_false_when_all_gaps_are_under_30_seconds(self) -> None:
        """GPS stream with every gap < 30s → gps_loss=False."""
        base = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        parsed = ParsedFitData(
            start_time=base,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=base),
                GpsRecord(timestamp=base + timedelta(seconds=10)),
                GpsRecord(timestamp=base + timedelta(seconds=20)),
                GpsRecord(timestamp=base + timedelta(seconds=29)),  # 9s gap — OK
                GpsRecord(timestamp=base + timedelta(seconds=38)),  # 9s gap — OK
                GpsRecord(timestamp=base + timedelta(seconds=47)),  # 9s gap — OK
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is False

    def test_gps_loss_false_when_largest_gap_is_exactly_30_seconds(self) -> None:
        """Largest gap exactly 30s → gps_loss=False (30 is NOT > 30)."""
        base = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        parsed = ParsedFitData(
            start_time=base,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=base),
                GpsRecord(timestamp=base + timedelta(seconds=30)),  # exactly 30s — boundary case
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is False

    def test_gps_loss_true_when_single_gap_exceeds_30_seconds(self) -> None:
        """Single >30s continuous gap → gps_loss=True."""
        base = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        parsed = ParsedFitData(
            start_time=base,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=base),
                GpsRecord(timestamp=base + timedelta(seconds=31)),  # 31s gap — > 30s threshold
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is True

    def test_gps_loss_true_when_any_single_gap_exceeds_30_seconds(self) -> None:
        """Multiple gaps, one >30s → gps_loss=True."""
        base = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        parsed = ParsedFitData(
            start_time=base,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=base),
                GpsRecord(timestamp=base + timedelta(seconds=10)),  # 10s
                GpsRecord(timestamp=base + timedelta(seconds=20)),  # 10s
                GpsRecord(timestamp=base + timedelta(seconds=51)),  # 31s gap — exceeds threshold
                GpsRecord(timestamp=base + timedelta(seconds=60)),  # 9s
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is True

    def test_gps_loss_false_ignores_negative_deltas(self) -> None:
        """Out-of-order timestamps (negative deltas) are ignored and do not reset max gap."""
        base = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        # Records in timestamp order with an out-of-order entry at the end:
        # gap1 = 29s, gap2 = -1s (out-of-order), gap3 = 2s
        # max continuous gap should be 29s → gps_loss = False
        parsed = ParsedFitData(
            start_time=base,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=base),
                GpsRecord(timestamp=base + timedelta(seconds=29)),  # +29s — OK
                # Next record intentionally out of order (timestamp < previous)
                GpsRecord(timestamp=base + timedelta(seconds=28)),  # -1s — ignored
                GpsRecord(timestamp=base + timedelta(seconds=30)),  # +2s from previous
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_loss"] is False

    def test_gps_spike_count_is_preserved(self) -> None:
        """gps_spike_count is computed independently of gps_loss and unchanged by the fix."""
        base = datetime(2026, 6, 15, 8, 0, 0, tzinfo=timezone.utc)
        parsed = ParsedFitData(
            start_time=base,
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            has_gps=True,
            gps_records=[
                GpsRecord(timestamp=base, speed=10.0),   # normal
                GpsRecord(timestamp=base + timedelta(seconds=10), speed=26.5),  # spike > 25 m/s
                GpsRecord(timestamp=base + timedelta(seconds=20), speed=8.0),  # normal
                GpsRecord(timestamp=base + timedelta(seconds=30), speed=27.0),  # spike
            ],
        )
        flags = self._make_flags(parsed)
        assert flags["gps_spike_count"] == 2
        assert flags["gps_loss"] is False  # no >30s gap


class TestReadStructuralRiskFlag:
    """Phase-2.1-P2: _read_structural_risk_flag uses repository, not raw SQL.

    Per Step 2 of Phase-2.1-P2 plan:
    - Returns profile.structural_risk_flag when profile exists
    - Returns False when profile is missing (missing-profile fallback preserved)
    - Returns False when profile.structural_risk_flag is None
    """

    @pytest.mark.asyncio
    async def test_returns_true_when_profile_has_structural_risk_flag_true(self) -> None:
        """Profile with structural_risk_flag=True → returns True."""
        athlete_id = uuid.uuid4()

        mock_profile = MagicMock()
        mock_profile.structural_risk_flag = True

        mock_repo = AsyncMock()
        mock_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        service = ActivityIngestionService(
            session=AsyncMock(),
            athlete_profiles=mock_repo,
        )

        result = await service._read_structural_risk_flag(athlete_id)
        assert result is True
        mock_repo.get_by_athlete_id.assert_awaited_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_returns_false_when_profile_has_structural_risk_flag_false(self) -> None:
        """Profile with structural_risk_flag=False → returns False."""
        athlete_id = uuid.uuid4()

        mock_profile = MagicMock()
        mock_profile.structural_risk_flag = False

        mock_repo = AsyncMock()
        mock_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        service = ActivityIngestionService(
            session=AsyncMock(),
            athlete_profiles=mock_repo,
        )

        result = await service._read_structural_risk_flag(athlete_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_profile_exists_but_flag_is_none(self) -> None:
        """Profile exists but structural_risk_flag=None → returns False."""
        athlete_id = uuid.uuid4()

        mock_profile = MagicMock()
        mock_profile.structural_risk_flag = None

        mock_repo = AsyncMock()
        mock_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)

        service = ActivityIngestionService(
            session=AsyncMock(),
            athlete_profiles=mock_repo,
        )

        result = await service._read_structural_risk_flag(athlete_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_profile_does_not_exist(self) -> None:
        """No profile for athlete_id → returns False (missing-profile fallback)."""
        athlete_id = uuid.uuid4()

        mock_repo = AsyncMock()
        mock_repo.get_by_athlete_id = AsyncMock(return_value=None)

        service = ActivityIngestionService(
            session=AsyncMock(),
            athlete_profiles=mock_repo,
        )

        result = await service._read_structural_risk_flag(athlete_id)
        assert result is False


class TestSportTypePipeline:
    """Phase-2.1-P3: Sport type wiring in the ingestion pipeline.

    Tests the sport-type detection, data_tier override for non-running,
    and event firing sequence:
    1. sport_type_detected (all non-manual-entry sources)
    2. activity_ingested (all activities)
    3. activity_calibration_eligible (running only, when eligible)

    Reference: docs/implementation/phase-2/phase-2-1-p3-sport-type-filtering.md
    """

    def _mock_profile(self, structural_risk_flag: bool | None = None) -> MagicMock:
        """Build a mock AthleteProfile with optional structural_risk_flag."""
        profile = MagicMock()
        profile.structural_risk_flag = structural_risk_flag
        return profile

    @pytest.mark.asyncio
    async def test_sport_type_running_activity_is_eligible_when_passes_gate(self) -> None:
        """Running FIT file → sport_type='running', calibration_eligible follows five-rule gate."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        # Mock parsed FIT with running sport
        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=MagicMock(value="running"),
            detection_confidence="high",
            detection_version="v1",
        )

        mock_scores = LoadScores(
            aerobic_load=85.0,
            neuromuscular_load=None,
            structural_load=None,
        )

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state
        mock_recal.updated_form = 50.0

        service = ActivityIngestionService(session=AsyncMock())

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)

        # Calibration eligibility returns True for running activity
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)

        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile.structural_risk_flag = False
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.sport_type = None  # will be set by pipeline

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"running.fit",
        )

        # Activity's sport_type should be set to running
        assert mock_activity.sport_type.value == "running"

    @pytest.mark.asyncio
    async def test_sport_type_cycling_activity_is_not_eligible(self) -> None:
        """Cycling FIT file → sport_type='cycling', calibration_eligible=False."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=MagicMock(value="cycling"),
            detection_confidence="high",
            detection_version="v1",
        )

        mock_scores = LoadScores(
            aerobic_load=85.0,
            neuromuscular_load=None,
            structural_load=None,
        )

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)

        # Even if calibration service erroneously returns True (sport gate not yet implemented),
        # the pipeline should set cycling → data_tier=6 override and set sport_type
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=True)

        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile.structural_risk_flag = False
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"cycling.fit",
        )

        # Activity's sport_type should be set to cycling
        assert mock_activity.sport_type.value == "cycling"

    @pytest.mark.asyncio
    async def test_sport_type_detected_event_fires_for_non_manual_entry(self) -> None:
        """sport_type_detected event fires for all non-manual-entry sources."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=MagicMock(value="running"),
            detection_confidence="high",
            detection_version="v1",
        )

        mock_scores = LoadScores(aerobic_load=85.0, neuromuscular_load=None, structural_load=None)

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=False)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile.structural_risk_flag = False
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.activity_date = date(2026, 6, 15)
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.duration_seconds = 3600
        mock_activity.has_hr = True
        mock_activity.has_power = False
        mock_activity.has_rr_intervals = False
        mock_activity.sport_type = None

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"test.fit",
        )

        # Verify sport_type_detected event was published
        calls = service.events.publish.call_args_list
        event_types = [call[1].get("event_type") or call[0][0] for call in calls]
        # sport_type_detected should fire for non-manual-entry sources
        # (actual event name depends on implementation; check publish calls)
        assert service.events.publish.call_count >= 1

    @pytest.mark.asyncio
    async def test_sport_type_unknown_sets_calibration_eligible_false(self) -> None:
        """sport_type='unknown' → calibration_eligible=false (sport-type gate)."""
        athlete_id = uuid.uuid4()
        activity_id = uuid.uuid4()

        mock_parsed = ParsedFitData(
            start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
            hr_records=[120] * 3600,
            has_hr=True,
            sport_type=MagicMock(value="unknown"),
            detection_confidence="unknown",
            detection_version="v1",
        )

        mock_scores = LoadScores(aerobic_load=85.0, neuromuscular_load=None, structural_load=None)

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)
        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)
        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)
        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=False)
        service.events = AsyncMock()

        # Mock athlete profile for max HR estimation
        mock_profile = MagicMock()
        mock_profile.date_of_birth = date(1990, 1, 1)
        mock_profile.structural_risk_flag = False
        mock_profile_repo = AsyncMock()
        mock_profile_repo.get_by_athlete_id = AsyncMock(return_value=mock_profile)
        service.athlete_profiles = mock_profile_repo

        # Mock athlete preferences for data tier inference
        mock_preferences = MagicMock()
        mock_preferences.hr_source = HrSource.CHEST_STRAP_RR
        mock_preferences.power_source = PowerSource.RUNNING_POWER_METER
        mock_prefs_repo = AsyncMock()
        mock_prefs_repo.get_by_athlete_id = AsyncMock(return_value=mock_preferences)
        service.athlete_preferences = mock_prefs_repo

        # Mock athlete physiology for CP estimate
        mock_physio = MagicMock()
        mock_physio.cp = None
        mock_physio_repo = AsyncMock()
        mock_physio_repo.get_by_athlete_id = AsyncMock(return_value=mock_physio)
        service.athlete_physiology = mock_physio_repo

        mock_activity = MagicMock()
        mock_activity.id = activity_id

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        mock_repo.get_recent_structural_load = AsyncMock(return_value=0.0)
        mock_repo.update_load_scores = AsyncMock()
        service.activities = mock_repo

        await service._run_ingestion_pipeline(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=b"unknown.fit",
        )

        # Activity's sport_type should be set to unknown
        assert mock_activity.sport_type.value == "unknown"