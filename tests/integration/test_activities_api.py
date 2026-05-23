"""Integration tests for Activity API endpoints.

These tests verify API endpoints with database dependencies
and JWT authentication.
"""

import uuid
from datetime import datetime

import pytest
from httpx import AsyncClient


# ============================================================================
# Activity Endpoint Tests
# ============================================================================


class TestGetActivityEndpoint:
    """Tests for GET /activities/{activity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_activity_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test getting an activity returns 200 with full payload."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "description": "A nice morning run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
            "perceived_effort": "moderate",
            "avg_heart_rate": 145,
            "max_heart_rate": 175,
            "distance_meters": 10000.0,
            "calories": 500,
        }
        create_response = await client.post("/activities/", json=create_payload, headers=headers)
        activity_id = create_response.json()["id"]

        response = await client.get(f"/activities/{activity_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == activity_id
        assert data["title"] == "Morning Run"
        assert data["description"] == "A nice morning run"
        assert data["activity_type"] == "running"
        assert data["avg_heart_rate"] == 145

    @pytest.mark.asyncio
    async def test_get_activity_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test getting a nonexistent activity returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/activities/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"


class TestUpdateActivityEndpoint:
    """Tests for PATCH /activities/{activity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_activity_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test updating an activity's title and description returns 200."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "description": "Original description",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
        }
        create_response = await client.post("/activities/", json=create_payload, headers=headers)
        activity_id = create_response.json()["id"]

        update_payload = {
            "title": "Evening Run",
            "description": "Updated description",
        }
        response = await client.patch(f"/activities/{activity_id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Evening Run"
        assert data["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_update_activity_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test updating a nonexistent activity returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        update_payload = {"title": "New Title"}
        response = await client.patch(f"/activities/{fake_id}", json=update_payload, headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Activity not found"


class TestDeleteActivityEndpoint:
    """Tests for DELETE /activities/{activity_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_activity_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test deleting an activity returns 204."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
        }
        create_response = await client.post("/activities/", json=create_payload, headers=headers)
        activity_id = create_response.json()["id"]

        response = await client.delete(f"/activities/{activity_id}", headers=headers)

        assert response.status_code == 204

        get_response = await client.get(f"/activities/{activity_id}", headers=headers)
        assert get_response.status_code == 404


class TestCreateActivityEndpoint:
    """Tests for POST /activities/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_activity_nonexistent_athlete(self, client: AsyncClient, registered_athlete: dict):
        """Test creating an activity for nonexistent athlete returns 403 (auth guard rejects mismatched athlete_id)."""
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": str(uuid.uuid4()),
            "activity_type": "running",
            "title": "Morning Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
        }

        response = await client.post("/activities/", json=payload, headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_create_activity_invalid_times(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating an activity with finished_at <= started_at returns 400."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Invalid Run",
            "started_at": "2024-01-01T11:00:00",
            "finished_at": "2024-01-01T10:00:00",
        }

        response = await client.post("/activities/", json=payload, headers=headers)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_create_activity_with_notes_and_planned_workout(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating an activity with notes and planned_workout_id persists and returns them."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        planned_workout_id = uuid.uuid4()
        payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
            "notes": "Felt great today!",
            "planned_workout_id": str(planned_workout_id),
        }

        response = await client.post("/activities/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["notes"] == "Felt great today!"
        assert data["planned_workout_id"] == str(planned_workout_id)

    @pytest.mark.asyncio
    async def test_create_activity_equal_times(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating an activity with finished_at == started_at returns 400."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Invalid Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T10:00:00",
        }

        response = await client.post("/activities/", json=payload, headers=headers)

        assert response.status_code == 400


class TestListAthleteActivitiesEndpoint:
    """Tests for GET /athletes/{athlete_id}/activities endpoint."""

    @pytest.mark.asyncio
    async def test_list_activities_invalid_query_param(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing activities with invalid query param returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
        }
        await client.post("/activities/", json=create_payload, headers=headers)

        response = await client.get(
            f"/athletes/{athlete_id}/activities?activity_type=invalid_type",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_activities_invalid_limit(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing activities with invalid limit returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(
            f"/athletes/{athlete_id}/activities?limit=0",
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_activities_invalid_offset(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing activities with negative offset returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(
            f"/athletes/{athlete_id}/activities?offset=-1",
            headers=headers,
        )

        assert response.status_code == 422
