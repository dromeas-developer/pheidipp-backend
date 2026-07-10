"""Unit tests for ActivityRepository.update_cleaning_version.

Reference: docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
          Step 6 — Add update_cleaning_version to ActivityRepository
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.activity import Activity
from app.models.enums import ActivitySource, SportType
from app.repositories.activity_repository import ActivityRepository


def _mock_activity(
    *,
    activity_id: uuid.UUID | None = None,
    cleaning_pipeline_version: str | None = None,
) -> MagicMock:
    mock = MagicMock(spec=Activity)
    mock.id = activity_id or uuid.uuid4()
    mock.cleaning_pipeline_version = cleaning_pipeline_version
    return mock


class TestUpdateCleaningVersion:
    """update_cleaning_version sets cleaning_pipeline_version on the loaded row."""

    @pytest.mark.asyncio
    async def test_update_cleaning_version_sets_version(self) -> None:
        """The method sets cleaning_pipeline_version to the given version
        and flushes the change."""
        activity_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_activity = _mock_activity(
            activity_id=activity_id, cleaning_pipeline_version=None
        )

        mock_repo = ActivityRepository(mock_session)
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)

        result = await mock_repo.update_cleaning_version(
            activity_id=activity_id,
            version="v1-signal-cleaning",
        )

        assert mock_activity.cleaning_pipeline_version == "v1-signal-cleaning"
        mock_session.flush.assert_called_once()
        mock_session.refresh.assert_called_once_with(mock_activity)
        assert result == mock_activity

    @pytest.mark.asyncio
    async def test_update_cleaning_version_raises_when_activity_missing(
        self,
    ) -> None:
        """LookupError is raised when the activity does not exist."""
        activity_id = uuid.uuid4()
        mock_session = AsyncMock()

        mock_repo = ActivityRepository(mock_session)
        mock_repo.get_by_id = AsyncMock(return_value=None)

        with pytest.raises(LookupError):
            await mock_repo.update_cleaning_version(
                activity_id=activity_id,
                version="v1-signal-cleaning",
            )

    @pytest.mark.asyncio
    async def test_update_cleaning_version_does_not_delete_or_update_other_fields(
        self,
    ) -> None:
        """Only cleaning_pipeline_version is modified; aerobic_load,
        calibration_eligible, and other fields are unchanged."""
        activity_id = uuid.uuid4()
        mock_session = AsyncMock()
        mock_activity = _mock_activity(
            activity_id=activity_id,
            cleaning_pipeline_version=None,
        )
        mock_activity.aerobic_load = 85.0
        mock_activity.calibration_eligible = True

        mock_repo = ActivityRepository(mock_session)
        mock_repo.get_by_id = AsyncMock(return_value=mock_activity)

        await mock_repo.update_cleaning_version(
            activity_id=activity_id,
            version="v1-signal-cleaning",
        )

        assert mock_activity.aerobic_load == 85.0
        assert mock_activity.calibration_eligible is True
        assert mock_activity.cleaning_pipeline_version == "v1-signal-cleaning"