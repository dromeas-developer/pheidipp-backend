"""Unit tests for CoachMessageService."""

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.coach_message_service import CoachMessageService
from app.schemas.coach_message import CoachMessageResponse, CoachMessageListResponse
from app.models.coach_message import CoachMessage
from app.models.enums import MessageType
from tests.factories import make_coach_message


@pytest.fixture
def service():
    """Fixture returning CoachMessageService."""
    return CoachMessageService()


@pytest.fixture
def mock_uow():
    """Fixture returning a mock UoW with mocked coach_messages repository."""
    uow = MagicMock()
    uow.coach_messages = MagicMock()
    uow.coach_messages.get_latest_by_athlete = AsyncMock()
    uow.coach_messages.get_first_message_by_athlete = AsyncMock()
    uow.coach_messages.has_first_message = AsyncMock()
    uow.coach_messages.list_by_athlete = AsyncMock()
    return uow


class TestCoachMessageServiceGetLatest:
    """Tests for CoachMessageService.get_latest."""

    @pytest.mark.asyncio
    async def test_get_latest_returns_response_when_repository_returns_model(
        self, service, mock_uow
    ):
        """Verify get_latest returns CoachMessageResponse when repository returns a model."""
        athlete_id = uuid.uuid4()
        orm_message = make_coach_message(athlete_id=athlete_id)

        mock_uow.coach_messages.get_latest_by_athlete.return_value = orm_message

        result = await service.get_latest(athlete_id, mock_uow)

        assert result is not None
        assert isinstance(result, CoachMessageResponse)
        assert result.athlete_id == athlete_id
        mock_uow.coach_messages.get_latest_by_athlete.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_repository_returns_none(
        self, service, mock_uow
    ):
        """Verify get_latest returns None when repository returns None."""
        athlete_id = uuid.uuid4()
        mock_uow.coach_messages.get_latest_by_athlete.return_value = None

        result = await service.get_latest(athlete_id, mock_uow)

        assert result is None


class TestCoachMessageServiceGetFirstMessage:
    """Tests for CoachMessageService.get_first_message."""

    @pytest.mark.asyncio
    async def test_get_first_message_returns_response_when_repository_returns_model(
        self, service, mock_uow
    ):
        """Verify get_first_message returns CoachMessageResponse when repository returns a model."""
        athlete_id = uuid.uuid4()
        orm_message = make_coach_message(athlete_id=athlete_id)

        mock_uow.coach_messages.get_first_message_by_athlete.return_value = orm_message

        result = await service.get_first_message(athlete_id, mock_uow)

        assert result is not None
        assert isinstance(result, CoachMessageResponse)
        assert result.athlete_id == athlete_id
        mock_uow.coach_messages.get_first_message_by_athlete.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_get_first_message_returns_none_when_repository_returns_none(
        self, service, mock_uow
    ):
        """Verify get_first_message returns None when repository returns None."""
        athlete_id = uuid.uuid4()
        mock_uow.coach_messages.get_first_message_by_athlete.return_value = None

        result = await service.get_first_message(athlete_id, mock_uow)

        assert result is None


class TestCoachMessageServiceHasFirstMessage:
    """Tests for CoachMessageService.has_first_message."""

    @pytest.mark.asyncio
    async def test_has_first_message_returns_boolean_from_repository(
        self, service, mock_uow
    ):
        """Verify has_first_message returns the boolean from repository."""
        athlete_id = uuid.uuid4()
        mock_uow.coach_messages.has_first_message.return_value = True

        result = await service.has_first_message(athlete_id, mock_uow)

        assert result is True
        mock_uow.coach_messages.has_first_message.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_has_first_message_returns_false_when_no_first_message(
        self, service, mock_uow
    ):
        """Verify has_first_message returns False when no first message exists."""
        athlete_id = uuid.uuid4()
        mock_uow.coach_messages.has_first_message.return_value = False

        result = await service.has_first_message(athlete_id, mock_uow)

        assert result is False


class TestCoachMessageServiceListByAthlete:
    """Tests for CoachMessageService.list_by_athlete."""

    @pytest.mark.asyncio
    async def test_list_by_athlete_returns_list_response(
        self, service, mock_uow
    ):
        """Verify list_by_athlete returns CoachMessageListResponse with items and total."""
        athlete_id = uuid.uuid4()
        orm_messages = [
            make_coach_message(athlete_id=athlete_id),
            make_coach_message(athlete_id=athlete_id),
        ]

        mock_uow.coach_messages.list_by_athlete.return_value = (orm_messages, 2)

        result = await service.list_by_athlete(athlete_id, mock_uow)

        assert isinstance(result, CoachMessageListResponse)
        assert len(result.items) == 2
        assert result.total == 2

    @pytest.mark.asyncio
    async def test_list_by_athlete_passes_limit_and_offset(
        self, service, mock_uow
    ):
        """Verify list_by_athlete passes limit and offset to repository."""
        athlete_id = uuid.uuid4()
        mock_uow.coach_messages.list_by_athlete.return_value = ([], 0)

        await service.list_by_athlete(athlete_id, mock_uow, limit=10, offset=5)

        mock_uow.coach_messages.list_by_athlete.assert_called_once_with(
            athlete_id, 10, 5
        )

    @pytest.mark.asyncio
    async def test_list_by_athlete_default_limit_offset(
        self, service, mock_uow
    ):
        """Verify list_by_athlete uses default limit and offset when not specified."""
        athlete_id = uuid.uuid4()
        mock_uow.coach_messages.list_by_athlete.return_value = ([], 0)

        await service.list_by_athlete(athlete_id, mock_uow)

        mock_uow.coach_messages.list_by_athlete.assert_called_once_with(
            athlete_id, 50, 0
        )