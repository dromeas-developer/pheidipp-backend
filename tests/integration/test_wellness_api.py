"""Integration tests for Wellness API endpoints.

These tests verify API endpoints with database dependencies
and JWT authentication.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================================
# Wellness Endpoint Tests
# ============================================================================


class TestCreateWellnessEndpoint:
    """Tests for POST /wellness/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_wellness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a wellness record returns 201."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "sleep_light": 240,
            "sleep_deep": 120,
            "sleep_rem": 90,
            "sleep_awake": 30,
            "resting_hr": 55,
            "hrv": 65,
            "weight": 75.5,
            "source": "manual",
            "timezone": "UTC",
        }

        response = await client.post("/wellness/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["athlete_id"] == athlete_id
        assert data["metric_date"] == "2024-01-01"
        assert data["sleep_total"] == 480
        assert data["resting_hr"] == 55

    @pytest.mark.asyncio
    async def test_create_wellness_minimal(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a wellness record with minimal fields."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "source": "manual",
            "timezone": "UTC",
        }

        response = await client.post("/wellness/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["metric_date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_create_wellness_duplicate_date(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a wellness record with duplicate date returns 400."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }

        response1 = await client.post("/wellness/", json=payload, headers=headers)
        assert response1.status_code == 201

        response2 = await client.post("/wellness/", json=payload, headers=headers)
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_create_wellness_nonexistent_athlete(self, client: AsyncClient, registered_athlete: dict):
        """Test creating a wellness record for nonexistent athlete returns 400."""
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": str(uuid.uuid4()),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }

        response = await client.post("/wellness/", json=payload, headers=headers)

        assert response.status_code == 403


class TestGetWellnessEndpoint:
    """Tests for GET /wellness/{wellness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_wellness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test getting a wellness record returns 200."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "resting_hr": 55,
            "source": "manual",
            "timezone": "UTC",
        }
        create_response = await client.post("/wellness/", json=create_payload, headers=headers)
        wellness_id = create_response.json()["id"]

        response = await client.get(f"/wellness/{wellness_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == wellness_id
        assert data["sleep_total"] == 480

    @pytest.mark.asyncio
    async def test_get_wellness_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test getting a nonexistent wellness record returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/wellness/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Wellness record not found"


class TestUpdateWellnessEndpoint:
    """Tests for PATCH /wellness/{wellness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_wellness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test updating a wellness record returns 200 with updated fields."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "resting_hr": 55,
            "source": "manual",
            "timezone": "UTC",
        }
        create_response = await client.post("/wellness/", json=create_payload, headers=headers)
        wellness_id = create_response.json()["id"]

        update_payload = {"sleep_total": 500, "resting_hr": 50}
        response = await client.patch(f"/wellness/{wellness_id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["sleep_total"] == 500
        assert data["resting_hr"] == 50

    @pytest.mark.asyncio
    async def test_update_wellness_conflicting_date(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test updating a wellness record with conflicting date returns 400."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload1 = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }
        response1 = await client.post("/wellness/", json=create_payload1, headers=headers)
        wellness_id1 = response1.json()["id"]

        create_payload2 = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-02",
            "sleep_total": 490,
            "source": "manual",
            "timezone": "UTC",
        }
        response2 = await client.post("/wellness/", json=create_payload2, headers=headers)
        wellness_id2 = response2.json()["id"]

        update_payload = {"metric_date": "2024-01-01"}
        response = await client.patch(f"/wellness/{wellness_id2}", json=update_payload, headers=headers)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_wellness_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test updating a nonexistent wellness record returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        update_payload = {"sleep_total": 500}
        response = await client.patch(f"/wellness/{fake_id}", json=update_payload, headers=headers)

        assert response.status_code == 404


class TestDeleteWellnessEndpoint:
    """Tests for DELETE /wellness/{wellness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_wellness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test deleting a wellness record returns 204."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }
        create_response = await client.post("/wellness/", json=create_payload, headers=headers)
        wellness_id = create_response.json()["id"]

        response = await client.delete(f"/wellness/{wellness_id}", headers=headers)

        assert response.status_code == 204

        get_response = await client.get(f"/wellness/{wellness_id}", headers=headers)
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_wellness_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test deleting a nonexistent wellness record returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/wellness/{fake_id}", headers=headers)

        assert response.status_code == 404


class TestListAthleteWellnessEndpoint:
    """Tests for GET /athletes/{athlete_id}/wellness endpoint."""

    @pytest.mark.asyncio
    async def test_list_athlete_wellness(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing wellness records returns 200 with items/total structure."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        for i in range(3):
            payload = {
                "athlete_id": athlete_id,
                "metric_date": f"2024-01-0{i+1}",
                "sleep_total": 480 + i * 10,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/wellness", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_with_pagination(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing wellness records with pagination."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        for i in range(5):
            payload = {
                "athlete_id": athlete_id,
                "metric_date": f"2024-01-0{i+1}",
                "sleep_total": 480 + i * 10,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload, headers=headers)

        response = await client.get(
            f"/athletes/{athlete_id}/wellness?limit=2&offset=0", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_with_date_filters(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing wellness records with date filters."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        dates = ["2024-01-01", "2024-01-15", "2024-02-01"]
        for d in dates:
            payload = {
                "athlete_id": athlete_id,
                "metric_date": d,
                "sleep_total": 480,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload, headers=headers)

        response = await client.get(
            f"/athletes/{athlete_id}/wellness?date_from=2024-01-10&date_to=2024-01-20",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["metric_date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_empty(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing wellness records for athlete with none returns empty list."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/wellness", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
