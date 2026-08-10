"""Integration tests for Activity model and ingestion DB-level behaviour.

Covers activity dedup constraints (partial unique index) and the
load-score column state at creation. Twin-recalibrate append-only
behaviour lives in tests/integration/test_twin_recalibration_service.py.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from tests.utils.factories import make_athlete


def _build_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    external_id: str | None = None,
    source: ActivitySource = ActivitySource.MANUAL_UPLOAD,
) -> Activity:
    activity = Activity(
        athlete_id=athlete_id,
        source=source,
        external_id=external_id,
        activity_date=date(2026, 1, 1),
        start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
        duration_seconds=3600,
        sport_type=SportType.RUNNING,
        sport_type_detection_version="v1",
        has_hr=True,
        has_rr_intervals=False,
        has_power=False,
        has_gps=True,
        quality_flags={},
        fit_file_key="athlete/2026-01-01/uuid.fit",
        ingestion_pipeline_version="v1-simple-fit",
    )
    db_session.add(activity)
    return activity


class TestActivityDeduplication:
    async def test_duplicate_external_id_raises_integrity_error(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        _build_activity(
            db_session, athlete_id=athlete.id, external_id="garmin-123"
        )
        await db_session.commit()

        _build_activity(
            db_session, athlete_id=athlete.id, external_id="garmin-123"
        )
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_same_external_id_different_source_allowed(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        _build_activity(
            db_session,
            athlete_id=athlete.id,
            external_id="ext-1",
            source=ActivitySource.INTERVALS_ICU,
        )
        _build_activity(
            db_session,
            athlete_id=athlete.id,
            external_id="ext-1",
            source=ActivitySource.MANUAL_UPLOAD,
        )
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(
            select(Activity).where(Activity.athlete_id == athlete.id)
        )
        rows = list(result.scalars())
        assert len(rows) == 2

    async def test_manual_entry_with_null_external_id_exempt_from_dedup(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        _build_activity(
            db_session,
            athlete_id=athlete.id,
            external_id=None,
            source=ActivitySource.MANUAL_ENTRY,
        )
        _build_activity(
            db_session,
            athlete_id=athlete.id,
            external_id=None,
            source=ActivitySource.MANUAL_ENTRY,
        )
        await db_session.commit()

        from sqlalchemy import select

        result = await db_session.execute(
            select(Activity).where(Activity.athlete_id == athlete.id)
        )
        rows = list(result.scalars())
        assert len(rows) == 2


class TestActivityLoadScoresNullAtCreation:
    async def test_load_scores_default_to_null(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        activity = _build_activity(
            db_session, athlete_id=athlete.id, external_id="upload-1"
        )
        await db_session.commit()
        await db_session.refresh(activity)

        assert activity.aerobic_load is None
        assert activity.neuromuscular_load is None
        assert activity.structural_load is None

    async def test_fit_file_key_set_at_creation(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)
        activity = _build_activity(
            db_session, athlete_id=athlete.id, external_id="upload-2"
        )
        await db_session.commit()
        await db_session.refresh(activity)

        assert activity.fit_file_key is not None
        assert "athlete" in activity.fit_file_key

    async def test_no_avg_columns_on_model(self) -> None:
        columns = {
            col.key
            for col in Activity.__table__.columns  # type: ignore[attr-defined]
        }
        assert "avg_hr" not in columns
        assert "avg_pace" not in columns
        assert "avg_power" not in columns
        assert "avg_cadence" not in columns
