"""Integration tests for ``ActivityRepository.update_cleaning_version``.

At the integration layer the focus is the **real DB write** —
``update_cleaning_version`` mutates the ``activities`` row in the
real test database, and a fresh repository query after commit
returns the new version. The unit tests have already verified the
mock-level behaviour (method calls, flush/refresh ordering); this
file adds the persistence contract.

Reference plan: ``docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md``
Step 6 — Add ``update_cleaning_version`` to ``ActivityRepository``.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from app.repositories.activity_repository import ActivityRepository
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _create_running_activity(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    cleaning_pipeline_version: str | None = None,
) -> Activity:
    """Insert a real ``Activity`` row with the bare minimum columns."""
    activity = Activity(
        athlete_id=athlete_id,
        source=ActivitySource.MANUAL_UPLOAD,
        activity_date=date(2026, 6, 15),
        start_time=datetime(2026, 6, 15, 8, 0, tzinfo=timezone.utc),
        duration_seconds=3600,
        aerobic_load=85.0,
        has_hr=True,
        has_gps=True,
        sport_type=SportType.RUNNING,
        calibration_eligible=True,
        quality_flags={},
        fit_file_key="fit-files/athlete/2026-06-15/abc.fit",
        ingestion_pipeline_version="v1-simple-fit",
        cleaning_pipeline_version=cleaning_pipeline_version,
    )
    db_session.add(activity)
    await db_session.flush()
    await db_session.refresh(activity)
    return activity


# ---------------------------------------------------------------------------
# Test: null → non-null transition lands in the DB.
# ---------------------------------------------------------------------------

class TestUpdateCleaningVersionPersists:
    """``update_cleaning_version`` writes the version to the row in the
    real test database, and the new value is queryable through a
    fresh ``ActivityRepository.get_by_id`` call after commit."""

    @pytest.mark.asyncio
    async def test_null_to_non_null_transition_persists(
        self, db_session: AsyncSession
    ) -> None:
        """An activity with ``cleaning_pipeline_version = None`` is
        updated to ``"v1-signal-cleaning"``. After commit, a fresh
        query via ``ActivityRepository.get_by_id`` returns the new
        version."""
        athlete = await make_athlete(db_session)
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            cleaning_pipeline_version=None,
        )
        await db_session.commit()

        # Sanity: the row was inserted with a null version.
        pre_check = await ActivityRepository(db_session).get_by_id(activity.id)
        assert pre_check is not None
        assert pre_check.cleaning_pipeline_version is None

        # Apply the transition.
        result = await ActivityRepository(
            db_session
        ).update_cleaning_version(
            activity_id=activity.id,
            version="v1-signal-cleaning",
        )
        assert result.cleaning_pipeline_version == "v1-signal-cleaning"
        await db_session.commit()

        # Fresh query — the in-memory object is stale after the
        # flush. Use a new repository instance to make this
        # explicit.
        repo = ActivityRepository(db_session)
        refreshed = await repo.get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version == "v1-signal-cleaning"

    @pytest.mark.asyncio
    async def test_other_columns_unchanged_after_version_update(
        self, db_session: AsyncSession
    ) -> None:
        """Only ``cleaning_pipeline_version`` is modified; aerobic load,
        fit_file_key, sport_type, and calibration_eligible are
        unchanged."""
        athlete = await make_athlete(db_session)
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            cleaning_pipeline_version=None,
        )
        await db_session.commit()

        await ActivityRepository(
            db_session
        ).update_cleaning_version(
            activity_id=activity.id,
            version="v1-signal-cleaning",
        )
        await db_session.commit()

        refreshed = await ActivityRepository(db_session).get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version == "v1-signal-cleaning"
        # Other columns preserved.
        assert refreshed.aerobic_load == 85.0
        assert refreshed.fit_file_key == "fit-files/athlete/2026-06-15/abc.fit"
        assert refreshed.sport_type == SportType.RUNNING
        assert refreshed.calibration_eligible is True
        assert refreshed.ingestion_pipeline_version == "v1-simple-fit"


# ---------------------------------------------------------------------------
# Test: missing activity raises LookupError at the DB layer.
# ---------------------------------------------------------------------------

class TestUpdateCleaningVersionMissingActivity:
    """``update_cleaning_version`` raises ``LookupError`` when the
    activity does not exist in the DB (not a mock-level check — a
    real ``None`` return from a real ``SELECT``)."""

    @pytest.mark.asyncio
    async def test_missing_activity_raises_lookup_error(
        self, db_session: AsyncSession
    ) -> None:
        """A non-existent activity id raises ``LookupError``."""
        non_existent_id = uuid.uuid4()
        repo = ActivityRepository(db_session)
        with pytest.raises(LookupError):
            await repo.update_cleaning_version(
                activity_id=non_existent_id,
                version="v1-signal-cleaning",
            )


# ---------------------------------------------------------------------------
# Test: setting a non-null version preserves the previously set version.
# ---------------------------------------------------------------------------

class TestUpdateCleaningVersionIdempotent:
    """A second ``update_cleaning_version`` call overwrites the
    version (the architecture forbids a ``non-null → null``
    down-transition but does not forbid overwriting one version
    with another — this guards against accidental schema
    regressions)."""

    @pytest.mark.asyncio
    async def test_second_update_overwrites_previous_version(
        self, db_session: AsyncSession
    ) -> None:
        """Calling ``update_cleaning_version`` twice in sequence
        results in the second version being present in the DB."""
        athlete = await make_athlete(db_session)
        activity = await _create_running_activity(
            db_session,
            athlete_id=athlete.id,
            cleaning_pipeline_version="v1-signal-cleaning",
        )
        await db_session.commit()

        repo = ActivityRepository(db_session)
        await repo.update_cleaning_version(
            activity_id=activity.id,
            version="v2-signal-cleaning",
        )
        await db_session.commit()

        refreshed = await repo.get_by_id(activity.id)
        assert refreshed is not None
        assert refreshed.cleaning_pipeline_version == "v2-signal-cleaning"
