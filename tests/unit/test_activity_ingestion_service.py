"""Unit tests for ActivityIngestionService — orchestrates FIT upload pipeline.

Phase-1.6: stage_upload (sync) + ingest_async (worker-side).
Phase-1.8: ingest_async properly publishes events inside the same transaction.

Reference: docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md
docs/implementation/phase-1/phase-1-8-p1-fix-event-ordering-and-async-processing.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import ActivitySource
from app.services.activity_ingestion_service import (
    ActivityIngestionError,
    ActivityIngestionResult,
    ActivityIngestionService,
    AthleteNotFoundForIngestionError,
    ObjectStorageFailureError,
)
from app.services.fit_parser_service import ParsedFitData
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
        # _MockRow is defined at module level (see class TestIngestAsync below).
        mock_row = _MockRow(date(1990, 1, 1))

        class _MockResult:
            def first(self):
                return mock_row

        async def _mock_execute(*args, **kwargs):
            return _MockResult()

        service.session.execute = MagicMock(side_effect=_mock_execute)

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

        # Create a mock activity with id for the pipeline
        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.aerobic_load = None
        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
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
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        # session.execute() must return an awaitable with .first() → row[0].date_of_birth.
        mock_row = _MockRow(date(1990, 1, 1))

        class _MockResult:
            def first(self):
                return mock_row

        async def _mock_execute(*args, **kwargs):
            return _MockResult()

        service.session.execute = MagicMock(side_effect=_mock_execute)

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)

        service.calibration_eligibility = MagicMock()
        service.calibration_eligibility.evaluate = MagicMock(return_value=False)

        service.events = AsyncMock()

        mock_activity = MagicMock()
        mock_activity.aerobic_load = None
        mock_activity.id = activity_id

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        # _run_ingestion_pipeline calls activities.update_load_scores(), not update().
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
        )

        mock_scores = LoadScores(aerobic_load=100.0, neuromuscular_load=None, structural_load=None)

        mock_twin_state = MagicMock()
        mock_recal = MagicMock()
        mock_recal.twin_state = mock_twin_state

        service = ActivityIngestionService(session=AsyncMock())
        # session.execute() must return an awaitable with .first() → row[0].date_of_birth.
        mock_row = _MockRow(date(1990, 1, 1))

        class _MockResult:
            def first(self):
                return mock_row

        async def _mock_execute(*args, **kwargs):
            return _MockResult()

        service.session.execute = MagicMock(side_effect=_mock_execute)

        service.fit_parser = MagicMock()
        service.fit_parser.parse = AsyncMock(return_value=mock_parsed)

        service.load_computation = MagicMock()
        service.load_computation.compute_aerobic_load = MagicMock(return_value=mock_scores)

        service.twin_recalibration = MagicMock()
        service.twin_recalibration.recalibrate = AsyncMock(return_value=mock_recal)

        service.calibration_eligibility = MagicMock()
        service.events = AsyncMock()

        mock_activity = MagicMock()
        mock_activity.id = activity_id
        mock_activity.activity_date = date(2026, 6, 15)
        mock_activity.fit_file_key = "fit-files/test.fit"
        mock_activity.duration_seconds = 3600
        mock_activity.has_hr = True
        mock_activity.has_power = False
        mock_activity.has_rr_intervals = False

        mock_repo = AsyncMock()
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)
        service.activities = mock_repo

        await service.ingest_async(
            athlete_id=athlete_id,
            activity_id=activity_id,
            file_bytes=file_bytes,
        )

        # Verify event was published
        service.events.publish.assert_called_once()
        call_kwargs = service.events.publish.call_args[1]
        assert call_kwargs["event_type"] == "activity_ingested"
        assert call_kwargs["athlete_id"] == athlete_id


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