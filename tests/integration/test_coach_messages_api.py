"""Integration tests for coach messages REST endpoints."""

import uuid
from datetime import datetime

import pytest

from app.models.coach_message import CoachMessage
from app.models.enums import MessageType, AthleteStatus
from tests.factories import make_athlete, make_coach_message


async def create_athlete_and_onboard(client, db_session):
    """Helper: registers athlete, creates profile, completes onboarding, returns (athlete_id, headers)."""
    from tests.factories import make_athlete_profile

    email = f"coach_{uuid.uuid4().hex[:8]}@example.com"
    resp = await client.post("/auth/register", json={"email": email, "password": "secure-test-password-123"})
    assert resp.status_code == 201
    data = resp.json()
    athlete_id = str(data["athlete_id"])
    headers = {"Authorization": f"Bearer {data['access_token']}"}

    # Create profile via API
    profile_payload = {
        "first_name": "John", "last_name": "Doe", "display_name": "johndoe",
        "date_of_birth": "1990-01-01", "gender": "male",
        "country_code": "US", "timezone": "America/New_York",
        "language_code": "en", "unit_preference": "metric",
    }
    await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

    return athlete_id, headers


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
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, uuid.UUID(athlete_id))

        response = await client.get(f"/athletes/{athlete_id}/coach-messages", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_empty_when_no_messages(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages returns empty items and total=0 when no messages exist."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_get_latest_coach_message_returns_200(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/latest returns 200 with message data when messages exist."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, uuid.UUID(athlete_id))

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/latest", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "athlete_id" in data
        assert "content" in data
        assert "message_type" in data

    @pytest.mark.asyncio
    async def test_get_latest_coach_message_returns_404_when_no_messages(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/latest returns 404 when no messages exist."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/latest", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_first_coach_message_returns_200(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/first returns 200 with first message data when it exists."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, uuid.UUID(athlete_id))

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/first", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["message_type"] == "first_message"

    @pytest.mark.asyncio
    async def test_get_first_coach_message_returns_404_when_no_first_message(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages/first returns 404 when no first message exists."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        # Create a non-first-message type
        message = make_coach_message(athlete_id=uuid.UUID(athlete_id), message_type=MessageType.DAILY_BRIEFING)
        test_db_session.add(message)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages/first", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_coach_messages_respects_limit(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?limit=1 respects limit parameter."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        for i in range(3):
            message = make_coach_message(athlete_id=uuid.UUID(athlete_id))
            test_db_session.add(message)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?limit=1", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_list_coach_messages_respects_offset(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?offset=1 respects offset parameter."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        for i in range(3):
            message = make_coach_message(athlete_id=uuid.UUID(athlete_id))
            test_db_session.add(message)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?offset=1", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_422_for_limit_0(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?limit=0 returns 422."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?limit=0", headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_422_for_limit_too_high(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?limit=1001 returns 422."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?limit=1001", headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_coach_messages_returns_422_for_negative_offset(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/coach-messages?offset=-1 returns 422."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        response = await client.get(f"/athletes/{athlete_id}/coach-messages?offset=-1", headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_response_items_contain_all_expected_fields(self, client, test_db_session):
        """Verify response items contain all expected fields."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)
        await seed_coach_message(test_db_session, uuid.UUID(athlete_id))

        response = await client.get(f"/athletes/{athlete_id}/coach-messages", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0
        item = data["items"][0]
        expected = ["id", "athlete_id", "twin_state_id", "training_block_id",
                     "message_type", "content", "generation_metadata", "created_at"]
        for field in expected:
            assert field in item, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_results_ordered_by_created_at_desc(self, client, test_db_session):
        """Verify results are ordered by created_at descending."""
        athlete_id, headers = await create_athlete_and_onboard(client, test_db_session)

        older = make_coach_message(athlete_id=uuid.UUID(athlete_id), created_at=datetime(2024, 1, 1))
        newer = make_coach_message(athlete_id=uuid.UUID(athlete_id), created_at=datetime(2024, 1, 2))
        test_db_session.add(older)
        test_db_session.add(newer)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/coach-messages", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"][0]["created_at"] >= data["items"][1]["created_at"]

    @pytest.mark.asyncio
    async def test_get_latest_coach_message_returns_404_for_unknown_athlete(self, client, test_db_session):
        """Verify GET /athletes/{nonexistent_id}/coach-messages/latest returns 403 (require_self rejects mismatched athlete_id)."""
        # Register an athlete just to get a valid token for auth
        email = f"unknown_{uuid.uuid4().hex[:8]}@example.com"
        resp = await client.post("/auth/register", json={"email": email, "password": "secure-test-password-123"})
        assert resp.status_code == 201
        auth_data = resp.json()
        headers = {"Authorization": f"Bearer {auth_data['access_token']}"}

        nonexistent_id = uuid.uuid4()
        response = await client.get(f"/athletes/{nonexistent_id}/coach-messages/latest", headers=headers)

        assert response.status_code == 403
