"""Integration tests for coach messages REST endpoints."""

import uuid
from datetime import datetime

import pytest

from app.models.coach_message import CoachMessage
from app.models.enums import MessageType, AthleteStatus
from tests.factories import make_athlete, make_coach_message


async def create_athlete_and_onboard(client, db_session):
    """Helper: creates athlete, profile, activates, completes onboarding, returns athlete_id."""
    from tests.factories import make_athlete_profile

    # Create athlete
    athlete = make_athlete(status=AthleteStatus.ACTIVE)
    db_session.add(athlete)
    await db_session.flush()

    # Create profile
    profile = make_athlete_profile(athlete_id=athlete.id)
    db_session.add(profile)
    await db_session.flush()
    await db_session.commit()

    return athlete.id


async def seed_coach_message(db_session, athlete_id):
    """Helper: inserts a CoachMessage directly into the DB for testing retrieval."""
    message = make_coach_message(athlete_id=athlete_id)
    db_session.add(message)
    await db_session.flush()
    await db_session.commit()
    return message


class TestCoachMessagesAPI:
    """Tests for coach message REST endpoints."""

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_200(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages returns 200 with CoachMessageListResponse format."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_empty_when_no_messages(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages returns empty items and total=0 when no messages exist."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_latest_coach_message_returns_200(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/latest returns 200 with message data when messages exist."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/latest")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "athlete_id" in data
        assert "content" in data
        assert "message_type" in data

    @pytest.mark.asyncio
    async def test_get_latest_coach_message_returns_404_when_no_messages(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/latest returns 404 when no messages exist."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/latest")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_first_coach_message_returns_200(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/first returns 200 with first message data when it exists."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/first")

        assert response.status_code == 200
        data = response.json()
        assert data["message_type"] == "first_message"

    @pytest.mark.asyncio
    async def test_get_first_coach_message_returns_404_when_no_first_message(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/first returns 404 when no first message exists."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        # Create a non-first-message type
        message = make_coach_message(athlete_id=athlete_id, message_type=MessageType.DAILY_BRIEFING)
        test_db_session.add(message)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/first")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_coach_messages_respects_limit(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?limit=1 respects limit parameter."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        # Create multiple messages
        for i in range(3):
            message = make_coach_message(athlete_id=athlete_id)
            test_db_session.add(message)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_coach_messages_respects_offset(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?offset=1 respects offset parameter."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        # Create multiple messages
        for i in range(3):
            message = make_coach_message(athlete_id=athlete_id)
            test_db_session.add(message)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?offset=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2  # 3 total - 1 offset

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_422_for_limit_0(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?limit=0 returns 422."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?limit=0")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_422_for_limit_too_high(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?limit=1001 returns 422."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?limit=1001")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_422_for_negative_offset(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?offset=-1 returns 422."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?offset=-1")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_response_items_contain_all_expected_fields(self, client, test_db_session):
        """Verify response items contain all expected fields."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0
        item = data["items"][0]

        assert "id" in item
        assert "athlete_id" in item
        assert "twin_state_id" in item
        assert "training_block_id" in item
        assert "message_type" in item
        assert "content" in item
        assert "generation_metadata" in item
        assert "created_at" in item

    @pytest.mark.asyncio
    async def test_results_ordered_by_created_at_desc(self, client, test_db_session):
        """Verify results are ordered by created_at descending."""
        athlete_id = await create_athlete_and_onboard(client, test_db_session)

        # Create messages with different timestamps
        older = make_coach_message(athlete_id=athlete_id, created_at=datetime(2024, 1, 1))
        newer = make_coach_message(athlete_id=athlete_id, created_at=datetime(2024, 1, 2))
        test_db_session.add(older)
        test_db_session.add(newer)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages")

        assert response.status_code == 200
        data = response.json()
        # Newer should be first
        assert data["items"][0]["created_at"] >= data["items"][1]["created_at"]

    @pytest.mark.asyncio
    async def test_get_latest_coach_message_returns_404_for_unknown_athlete(self, client, test_db_session):
        """Verify GET /athletes/{nonexistent_id}/coach-messages/latest returns 404 for unknown athlete."""
        nonexistent_id = uuid.uuid4()

        response = await client.get(f"/athletes/{nonexistent_id}/coach-messages/latest")

        assert response.status_code == 404