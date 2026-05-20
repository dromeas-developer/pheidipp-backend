"""Unit tests for CoachMessageRepository."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.coach_message import CoachMessage
from app.models.enums import MessageType
from app.repositories.coach_message_repository import CoachMessageRepository
from tests.factories import make_athlete, make_athlete_profile


@pytest.fixture
def coach_message_repo(test_db_session):
    """Fixture returning CoachMessageRepository."""
    return CoachMessageRepository(test_db_session)


@pytest.fixture
async def athlete(test_db_session):
    """Fixture creating an Athlete in the test DB."""
    from app.models.athlete import Athlete
    from app.models.enums import AthleteStatus

    athlete = make_athlete(status=AthleteStatus.ACTIVE)
    test_db_session.add(athlete)
    await test_db_session.flush()
    return athlete


@pytest.fixture
async def athlete_with_profile(test_db_session, athlete):
    """Fixture creating an Athlete with a profile in the test DB."""
    profile = make_athlete_profile(athlete_id=athlete.id)
    test_db_session.add(profile)
    await test_db_session.flush()
    return athlete


class TestCoachMessageRepositoryCreate:
    """Tests for CoachMessageRepository.create."""

    @pytest.mark.asyncio
    async def test_create_persists_coach_message(self, test_db_session, coach_message_repo, athlete):
        """Verify create persists a CoachMessage and returns it with an ID."""
        message = await coach_message_repo.create(
            athlete_id=athlete.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test coach message content.",
            generation_metadata={"outcome": "success"},
        )

        assert message.id is not None
        assert message.athlete_id == athlete.id
        assert message.message_type == MessageType.FIRST_MESSAGE

        # Verify it's actually persisted
        from sqlalchemy import select
        result = await test_db_session.execute(
            select(CoachMessage).where(CoachMessage.id == message.id)
        )
        persisted = result.scalar_one()
        assert persisted.id == message.id


class TestCoachMessageRepositoryGetLatest:
    """Tests for CoachMessageRepository.get_latest_by_athlete."""

    @pytest.mark.asyncio
    async def test_get_latest_returns_most_recent_message(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify get_latest_by_athlete returns the most recent message for an athlete."""
        # Create multiple messages with different timestamps
        older_message = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Older message",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        newer_message = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.DAILY_BRIEFING,
            content="Newer message",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 2),
        )
        test_db_session.add(older_message)
        test_db_session.add(newer_message)
        await test_db_session.flush()

        latest = await coach_message_repo.get_latest_by_athlete(athlete.id)
        assert latest is not None
        assert latest.id == newer_message.id
        assert latest.content == "Newer message"

    @pytest.mark.asyncio
    async def test_get_latest_returns_none_when_no_messages(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify get_latest_by_athlete returns None when no messages exist."""
        result = await coach_message_repo.get_latest_by_athlete(athlete.id)
        assert result is None


class TestCoachMessageRepositoryGetFirstMessage:
    """Tests for CoachMessageRepository.get_first_message_by_athlete."""

    @pytest.mark.asyncio
    async def test_get_first_message_returns_filtered_message(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify get_first_message_by_athlete returns a message filtered by message_type=FIRST_MESSAGE."""
        first_msg = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="First message",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        daily_msg = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.DAILY_BRIEFING,
            content="Daily briefing",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 2),
        )
        test_db_session.add(first_msg)
        test_db_session.add(daily_msg)
        await test_db_session.flush()

        result = await coach_message_repo.get_first_message_by_athlete(athlete.id)
        assert result is not None
        assert result.message_type == MessageType.FIRST_MESSAGE
        assert result.content == "First message"

    @pytest.mark.asyncio
    async def test_get_first_message_does_not_return_non_first_message_types(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify get_first_message_by_athlete does not return non-first-message types."""
        daily_msg = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.DAILY_BRIEFING,
            content="Daily briefing",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        test_db_session.add(daily_msg)
        await test_db_session.flush()

        result = await coach_message_repo.get_first_message_by_athlete(athlete.id)
        assert result is None


class TestCoachMessageRepositoryHasFirstMessage:
    """Tests for CoachMessageRepository.has_first_message."""

    @pytest.mark.asyncio
    async def test_has_first_message_returns_true_when_exists(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify has_first_message returns True when a first message exists."""
        message = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="First message",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        test_db_session.add(message)
        await test_db_session.flush()

        result = await coach_message_repo.has_first_message(athlete.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_has_first_message_returns_false_when_none_exists(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify has_first_message returns False when no first message exists."""
        result = await coach_message_repo.has_first_message(athlete.id)
        assert result is False

    @pytest.mark.asyncio
    async def test_has_first_message_returns_false_when_only_non_first_messages(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify has_first_message returns False when only non-first-message types exist."""
        message = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.DAILY_BRIEFING,
            content="Daily briefing",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        test_db_session.add(message)
        await test_db_session.flush()

        result = await coach_message_repo.has_first_message(athlete.id)
        assert result is False


class TestCoachMessageRepositoryListByAthlete:
    """Tests for CoachMessageRepository.list_by_athlete."""

    @pytest.mark.asyncio
    async def test_list_by_athlete_returns_tuple(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify list_by_athlete returns a tuple of (list, total_count)."""
        message = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test message",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        test_db_session.add(message)
        await test_db_session.flush()

        messages, total = await coach_message_repo.list_by_athlete(athlete.id)
        assert isinstance(messages, list)
        assert isinstance(total, int)
        assert len(messages) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_list_by_athlete_respects_limit(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify list_by_athlete respects limit parameter."""
        for i in range(5):
            message = CoachMessage(
                athlete_id=athlete.id,
                message_type=MessageType.FIRST_MESSAGE,
                content=f"Message {i}",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, i + 1),
            )
            test_db_session.add(message)
        await test_db_session.flush()

        messages, total = await coach_message_repo.list_by_athlete(athlete.id, limit=2)
        assert len(messages) == 2
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_by_athlete_respects_offset(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify list_by_athlete respects offset parameter."""
        for i in range(5):
            message = CoachMessage(
                athlete_id=athlete.id,
                message_type=MessageType.FIRST_MESSAGE,
                content=f"Message {i}",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, i + 1),
            )
            test_db_session.add(message)
        await test_db_session.flush()

        messages, total = await coach_message_repo.list_by_athlete(athlete.id, offset=2)
        assert len(messages) == 3
        assert total == 5

    @pytest.mark.asyncio
    async def test_list_by_athlete_orders_by_created_at_desc(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify list_by_athlete orders by created_at descending."""
        for i in range(3):
            message = CoachMessage(
                athlete_id=athlete.id,
                message_type=MessageType.FIRST_MESSAGE,
                content=f"Message {i}",
                generation_metadata={"outcome": "success"},
                created_at=datetime(2024, 1, i + 1, tzinfo=timezone.utc),
            )
            test_db_session.add(message)
        await test_db_session.flush()

        messages, total = await coach_message_repo.list_by_athlete(athlete.id)
        # Most recent first (highest date)
        assert messages[0].created_at > messages[1].created_at
        assert messages[1].created_at > messages[2].created_at

    @pytest.mark.asyncio
    async def test_list_by_athlete_returns_empty_when_no_messages(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify list_by_athlete returns empty list and zero total when no messages exist."""
        messages, total = await coach_message_repo.list_by_athlete(athlete.id)
        assert messages == []
        assert total == 0


class TestCoachMessageRepositoryCascade:
    """Tests for cascade delete behavior."""

    @pytest.mark.asyncio
    async def test_cascade_deleting_athlete_removes_coach_messages(
        self, test_db_session, coach_message_repo, athlete
    ):
        """Verify deleting an athlete removes their coach messages."""
        message = CoachMessage(
            athlete_id=athlete.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test message",
            generation_metadata={"outcome": "success"},
            created_at=datetime(2024, 1, 1),
        )
        test_db_session.add(message)
        await test_db_session.flush()

        # Verify message exists
        messages, total = await coach_message_repo.list_by_athlete(athlete.id)
        assert total == 1

        # Delete athlete
        await test_db_session.delete(athlete)
        await test_db_session.flush()

        # Verify messages are gone
        messages, total = await coach_message_repo.list_by_athlete(athlete.id)
        assert total == 0