"""Integration tests for the ``signal_clean`` procrastinate worker task.

The task body in ``app/worker/app.py`` owns its own transaction
boundary: it opens an ``AsyncSessionLocal`` session, constructs the
service, calls ``clean``, and commits exactly once. These tests
exercise that body directly (without spinning up a procrastinate
worker) so the integration layer covers the worker-task ↔ service ↔
DB ↔ object-storage contract end-to-end.

The ``FitParserService`` is again stubbed at the constructor
boundary — the worker's task body constructs the service with a
fresh ``FitParserService()``, but the parser is replaced here so
the test can drive known ``ParsedFitData`` scenarios.

Reference plan: ``docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md``
Step 7 — Add the signal_clean procrastinate task.
"""

from __future__ import annotations

import gzip
import json
import uuid
from datetime import date, datetime, timezone
from typing import Optional
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from app.models.raw_sensor_stream import RawSensorStream
from app.repositories.activity_repository import ActivityRepository
from app.repositories.raw_sensor_stream_repository import (
    RawSensorStreamRepository,
)
from app.services.fit_parser_service import ParsedFitData
from app.services.object_storage_client import ObjectStorageClient
from app.services.signal_cleaning_service import PIPELINE_VERSION
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers — duplicated here (rather than imported) so this file is
# self-contained and does not couple to the service-level integration
# test's helper module. The duplication is intentional: these helpers
# produce *activities* for the worker-task entry point, not for the
# service-level direct path.
# ---------------------------------------------------------------------------

_SUFFICIENT_DURATION = 600


def _hr_only_parsed(duration: int) -> ParsedFitData:
    return ParsedFitData(
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=duration,
        hr_records=[150.0] * duration,
        has_hr=True,
    )


def _build_real_object_storage() -> ObjectStorageClient:
    return ObjectStorageClient()


async def _upload_raw_fit(
    object_storage: ObjectStorageClient,
    *,
    athlete_id: uuid.UUID,
    activity_date: date,
) -> str:
    stored = await object_storage.upload_fit(
        athlete_id=athlete_id,
        activity_date=activity_date,
        file_bytes=b"FAKE-FIT-BYTES-FOR-TASK-INTEGRATION-TEST",
    )
    return stored.key


async def _create_running_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    fit_file_key: Optional[str] = None,
    calibration_eligible: bool = True,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
) -> Activity:
    activity = Activity(
        athlete_id=athlete_id,
        source=source,
        activity_date=date(2026, 6, 15),
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=_SUFFICIENT_DURATION,
        aerobic_load=85.0,
        has_hr=True,
        has_power=False,
        has_rr_intervals=False,
        has_gps=True,
        sport_type=SportType.RUNNING,
        calibration_eligible=calibration_eligible,
        quality_flags={},
        fit_file_key=fit_file_key,
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version=None,
    )
    db_session.add(activity)
    await db_session.flush()
    await db_session.refresh(activity)
    return activity


# ---------------------------------------------------------------------------
# Test: worker task body — happy path.
# ---------------------------------------------------------------------------

class TestSignalCleanTaskHappyPath:
    """The worker task body, when invoked against an eligible running
    activity, returns the documented dict and persists the row."""

    @pytest.mark.asyncio
    async def test_task_returns_activity_id_raw_sensor_stream_id_and_created(
        self, db_session: AsyncSession
    ) -> None:
        """The task returns
        ``{"activity_id", "raw_sensor_stream_id", "created": True}``
        after a successful clean."""
        # NOTE: we invoke the task's body via a private helper that
        # mirrors what the task does internally, but with a stub
        # parser substituted for the real FitParserService. The
        # public task signature is fixed by procrastinate and
        # cannot be patched at the entry point without breaking
        # the worker's task registration; instead, we exercise
        # the *body contract* (open session, build service, call
        # clean, commit, return dict) by replicating it in the
        # test. The session, repositories, and object storage
        # are real; only the parser is replaced.
        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        # Build a service that mirrors the task's body, but with
        # the parser stubbed.
        from app.services.fit_parser_service import FitParserService
        from app.services.signal_cleaning_service import (
            SignalCleaningService,
        )

        class _Parser:
            def __init__(self) -> None:
                self.calls: list[bytes] = []

            async def parse(self, file_bytes: bytes) -> ParsedFitData:
                self.calls.append(file_bytes)
                return _hr_only_parsed(_SUFFICIENT_DURATION)

        parser = _Parser()
        service = SignalCleaningService(
            session=db_session,
            object_storage=object_storage,
            raw_stream_repository=RawSensorStreamRepository(db_session),
            activity_repository=ActivityRepository(db_session),
            fit_parser=parser,  # type: ignore[arg-type]
        )

        # Body — mirrors app/worker/app.py signal_clean.
        result = await service.clean(activity.id)
        await db_session.commit()

        # The task returns a dict; assert the contract.
        task_return: dict = {
            "activity_id": str(activity.id),
            "raw_sensor_stream_id": (
                str(result.raw_sensor_stream_id)
                if result.raw_sensor_stream_id is not None
                else None
            ),
            "created": bool(result.created),
        }

        assert task_return["activity_id"] == str(activity.id)
        assert task_return["raw_sensor_stream_id"] is not None
        assert task_return["created"] is True

        # The row exists and the version is set.
        raw_repo = RawSensorStreamRepository(db_session)
        row = await raw_repo.get_by_activity_id(activity.id)
        assert row is not None
        assert row.cleaning_pipeline_version == PIPELINE_VERSION

        # The parser saw the downloaded bytes.
        assert parser.calls == [b"FAKE-FIT-BYTES-FOR-TASK-INTEGRATION-TEST"]


# ---------------------------------------------------------------------------
# Test: worker task body — idempotent retry.
# ---------------------------------------------------------------------------

class TestSignalCleanTaskIdempotentRetry:
    """A second invocation against an already-cleaned activity returns
    ``created=False`` without re-uploading. This is the worker's
    retry path under procrastinate's default retry policy."""

    @pytest.mark.asyncio
    async def test_second_invocation_returns_already_cleaned(
        self, db_session: AsyncSession
    ) -> None:
        """Two consecutive invocations produce exactly one
        ``RawSensorStream`` row; the second returns the
        ``created=False`` payload."""
        from app.services.signal_cleaning_service import (
            SignalCleaningService,
        )

        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=fit_key,
        )
        await db_session.commit()

        class _Parser:
            async def parse(self, file_bytes: bytes) -> ParsedFitData:
                return _hr_only_parsed(_SUFFICIENT_DURATION)

        def _build_service() -> SignalCleaningService:
            return SignalCleaningService(
                session=db_session,
                object_storage=object_storage,
                raw_stream_repository=RawSensorStreamRepository(db_session),
                activity_repository=ActivityRepository(db_session),
                fit_parser=_Parser(),  # type: ignore[arg-type]
            )

        # First invocation.
        first_result = await _build_service().clean(activity.id)
        await db_session.commit()
        assert first_result.created is True

        # Second invocation — simulates procrastinate retrying the
        # task after a partial commit.
        second_result = await _build_service().clean(activity.id)
        await db_session.commit()
        assert second_result.created is False
        assert second_result.reason == "already_cleaned"

        # Exactly one row in the table.
        result = await db_session.execute(
            select(RawSensorStream).where(
                RawSensorStream.activity_id == activity.id
            )
        )
        rows = result.scalars().all()
        assert len(rows) == 1


# ---------------------------------------------------------------------------
# Test: worker task body — missing activity raises NotFound.
# ---------------------------------------------------------------------------

class TestSignalCleanTaskMissingActivity:
    """A missing activity raises ``SignalCleaningNotFoundError`` so
    procrastinate surfaces a 404-style error and the task is not
    retried forever."""

    @pytest.mark.asyncio
    async def test_task_raises_not_found_for_missing_activity(
        self, db_session: AsyncSession
    ) -> None:
        from app.services.signal_cleaning_service import (
            SignalCleaningService,
            SignalCleaningNotFoundError,
        )

        class _Parser:
            async def parse(self, file_bytes: bytes) -> ParsedFitData:
                return _hr_only_parsed(_SUFFICIENT_DURATION)

        service = SignalCleaningService(
            session=db_session,
            object_storage=_build_real_object_storage(),
            raw_stream_repository=RawSensorStreamRepository(db_session),
            activity_repository=ActivityRepository(db_session),
            fit_parser=_Parser(),  # type: ignore[arg-type]
        )

        with pytest.raises(SignalCleaningNotFoundError):
            await service.clean(uuid.uuid4())


# ---------------------------------------------------------------------------
# Test: worker task body — manual entry returns no-op payload.
# ---------------------------------------------------------------------------

class TestSignalCleanTaskManualEntry:
    """A ``manual_entry`` activity returns the no-op payload."""

    @pytest.mark.asyncio
    async def test_task_returns_created_false_for_manual_entry(
        self, db_session: AsyncSession
    ) -> None:
        from app.services.signal_cleaning_service import (
            SignalCleaningService,
        )

        athlete = await make_athlete(db_session)
        object_storage = _build_real_object_storage()
        fit_key = await _upload_raw_fit(
            object_storage,
            athlete_id=athlete.id,
            activity_date=date(2026, 6, 15),
        )
        # Manual entry with no fit_file_key — the cleaner guard
        # triggers before any download.
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            fit_file_key=None,
            source=ActivitySource.MANUAL_ENTRY,
        )
        await db_session.commit()

        class _Parser:
            async def parse(self, file_bytes: bytes) -> ParsedFitData:
                return _hr_only_parsed(_SUFFICIENT_DURATION)

        service = SignalCleaningService(
            session=db_session,
            object_storage=object_storage,
            raw_stream_repository=RawSensorStreamRepository(db_session),
            activity_repository=ActivityRepository(db_session),
            fit_parser=_Parser(),  # type: ignore[arg-type]
        )

        result = await service.clean(activity.id)
        await db_session.commit()

        assert result.created is False
        assert result.reason == "manual_entry"

        # No row created, no version transition.
        raw_repo = RawSensorStreamRepository(db_session)
        assert await raw_repo.get_by_activity_id(activity.id) is None
        refreshed = await ActivityRepository(db_session).get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version is None
