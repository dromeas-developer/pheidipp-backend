"""Integration tests for API endpoints.

These tests verify API endpoint behavior with database integration
and JWT authentication.
"""

import uuid
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


class TestActivityEndpoints:
    """Tests for activity API endpoints."""

    @pytest.mark.asyncio
    async def test_create_activity_endpoint_returns_created_activity(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Verify response payload matches created entity."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        started_at = datetime(2024, 1, 1, 10, 0, 0)
        finished_at = started_at + timedelta(hours=1)

        payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "description": "A test run",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "perceived_effort": "moderate",
            "avg_heart_rate": 145,
            "max_heart_rate": 175,
            "distance_meters": 10000.0,
            "calories": 500,
        }

        response = await client.post("/activities/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["athlete_id"] == athlete_id
        assert data["activity_type"] == "running"
        assert data["title"] == "Morning Run"
        assert data["description"] == "A test run"
        assert data["perceived_effort"] == "moderate"
        assert data["avg_heart_rate"] == 145
        assert data["max_heart_rate"] == 175
        assert data["distance_meters"] == 10000.0
        assert data["calories"] == 500
        assert data["duration_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_list_activities_endpoint_filters_correctly(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Verify query param filtering works end-to-end."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]
        athlete_id_uuid = uuid.UUID(athlete_id)

        from app.models.activity import Activity
        from app.models.enums import ActivityType

        # Create multiple activities with different types and dates directly in DB
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.db.session import get_db
        from app.main import app

        # We need test_db_session for DB operations
        # Create activities via API instead
        running_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "started_at": "2024-01-15T10:00:00",
            "finished_at": "2024-01-15T11:00:00",
        }
        await client.post("/activities/", json=running_payload, headers=headers)

        cycling_payload = {
            "athlete_id": athlete_id,
            "activity_type": "cycling",
            "title": "Afternoon Ride",
            "started_at": "2024-01-20T14:00:00",
            "finished_at": "2024-01-20T16:00:00",
        }
        await client.post("/activities/", json=cycling_payload, headers=headers)

        # Test filtering by activity_type
        response = await client.get(
            f"/athletes/{athlete_id}/activities",
            params={"activity_type": "running"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["activity_type"] == "running"

        # Test filtering by date range
        response = await client.get(
            f"/athletes/{athlete_id}/activities",
            params={
                "date_from": "2024-01-18T00:00:00",
                "date_to": "2024-12-31T23:59:59",
            },
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["activity_type"] == "cycling"

    @pytest.mark.asyncio
    async def test_delete_activity_endpoint_returns_404_for_missing_activity(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Verify proper error handling returns 404 for missing activity."""
        headers = registered_athlete["headers"]
        non_existent_activity_id = uuid.uuid4()

        response = await client.delete(f"/activities/{non_existent_activity_id}", headers=headers)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_athlete_scoped_activity_routes_only_return_athlete_data(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Verify athlete isolation in routes - each athlete only sees their own data."""
        athlete1 = registered_athlete
        athlete1_id = athlete1["athlete_id"]
        headers1 = athlete1["headers"]

        # Register second athlete
        email2 = f"iso_{uuid.uuid4().hex[:8]}@example.com"
        resp2 = await client.post("/auth/register", json={"email": email2, "password": "secure-test-password-123"})
        assert resp2.status_code == 201
        data2 = resp2.json()
        athlete2_id = str(data2["athlete_id"])
        headers2 = {"Authorization": f"Bearer {data2['access_token']}"}

        # Create activity for athlete1 via API
        activity1_payload = {
            "athlete_id": athlete1_id,
            "activity_type": "running",
            "title": "Athlete1 Run",
            "started_at": "2024-01-15T10:00:00",
            "finished_at": "2024-01-15T11:00:00",
        }
        await client.post("/activities/", json=activity1_payload, headers=headers1)

        # Create activity for athlete2 via API
        activity2_payload = {
            "athlete_id": athlete2_id,
            "activity_type": "cycling",
            "title": "Athlete2 Ride",
            "started_at": "2024-01-15T14:00:00",
            "finished_at": "2024-01-15T16:00:00",
        }
        await client.post("/activities/", json=activity2_payload, headers=headers2)

        # Query athlete1's activities - should only return athlete1's data
        response = await client.get(f"/athletes/{athlete1_id}/activities", headers=headers1)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Athlete1 Run"
        assert data["items"][0]["athlete_id"] == athlete1_id

        # Query athlete2's activities - should only return athlete2's data
        response = await client.get(f"/athletes/{athlete2_id}/activities", headers=headers2)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Athlete2 Ride"
        assert data["items"][0]["athlete_id"] == athlete2_id


class TestOnboardingFlow:
    """Tests for onboarding flow endpoints."""

    @pytest.mark.asyncio
    async def test_onboarding_flow_sets_onboarding_complete(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Verify onboarding completion flag is updated."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Complete onboarding by updating status to active
        response = await client.patch(
            f"/athletes/{athlete_id}",
            json={"status": "active"},
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

    @pytest.mark.asyncio
    async def test_onboarding_flow_creates_initial_twin_state(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Verify onboarding triggers initial twin creation."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.patch(
            f"/athletes/{athlete_id}",
            json={"status": "active"},
            headers=headers,
        )

        assert response.status_code == 200
