"""Integration tests for Wellness API endpoints.

These tests verify API endpoints with database dependencies.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import AthleteStatus
from app.repositories.athlete_repository import AthleteRepository


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
async def athlete_in_db(test_db_session: AsyncSession) -> Athlete:
    """Create an athlete in the database for testing."""
    athlete_repo = AthleteRepository(test_db_session)
    athlete = await athlete_repo.create(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
    )
    return athlete


# ============================================================================
# Wellness Endpoint Tests
# ============================================================================


class TestCreateWellnessEndpoint:
    """Tests for POST /wellness/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_wellness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a wellness record returns 201."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
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

        response = await client.post("/wellness/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["athlete_id"] == str(athlete_in_db.id)
        assert data["metric_date"] == "2024-01-01"
        assert data["sleep_total"] == 480
        assert data["resting_hr"] == 55

    @pytest.mark.asyncio
    async def test_create_wellness_minimal(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a wellness record with minimal fields."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "source": "manual",
            "timezone": "UTC",
        }

        response = await client.post("/wellness/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["metric_date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_create_wellness_duplicate_date(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a wellness record with duplicate date returns 400."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }

        # Create first record
        response1 = await client.post("/wellness/", json=payload)
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await client.post("/wellness/", json=payload)
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_create_wellness_nonexistent_athlete(self, client: AsyncClient):
        """Test creating a wellness record for nonexistent athlete returns 400."""
        payload = {
            "athlete_id": str(uuid.uuid4()),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }

        response = await client.post("/wellness/", json=payload)

        assert response.status_code == 400


class TestGetWellnessEndpoint:
    """Tests for GET /wellness/{wellness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_wellness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test getting a wellness record returns 200."""
        # First create a wellness record
        create_payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "resting_hr": 55,
            "source": "manual",
            "timezone": "UTC",
        }
        create_response = await client.post("/wellness/", json=create_payload)
        wellness_id = create_response.json()["id"]

        # Now get the wellness record
        response = await client.get(f"/wellness/{wellness_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == wellness_id
        assert data["sleep_total"] == 480

    @pytest.mark.asyncio
    async def test_get_wellness_endpoint_404(self, client: AsyncClient):
        """Test getting a nonexistent wellness record returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/wellness/{fake_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Wellness record not found"


class TestUpdateWellnessEndpoint:
    """Tests for PATCH /wellness/{wellness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_wellness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test updating a wellness record returns 200 with updated fields."""
        # Create a wellness record
        create_payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "resting_hr": 55,
            "source": "manual",
            "timezone": "UTC",
        }
        create_response = await client.post("/wellness/", json=create_payload)
        wellness_id = create_response.json()["id"]

        # Update the wellness record
        update_payload = {"sleep_total": 500, "resting_hr": 50}
        response = await client.patch(f"/wellness/{wellness_id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["sleep_total"] == 500
        assert data["resting_hr"] == 50

    @pytest.mark.asyncio
    async def test_update_wellness_conflicting_date(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test updating a wellness record with conflicting date returns 400."""
        # Create first wellness record
        create_payload1 = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }
        response1 = await client.post("/wellness/", json=create_payload1)
        wellness_id1 = response1.json()["id"]

        # Create second wellness record
        create_payload2 = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-02",
            "sleep_total": 490,
            "source": "manual",
            "timezone": "UTC",
        }
        response2 = await client.post("/wellness/", json=create_payload2)
        wellness_id2 = response2.json()["id"]

        # Try to update second record with first record's date
        update_payload = {"metric_date": "2024-01-01"}
        response = await client.patch(f"/wellness/{wellness_id2}", json=update_payload)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_wellness_endpoint_404(self, client: AsyncClient):
        """Test updating a nonexistent wellness record returns 404."""
        fake_id = str(uuid.uuid4())
        update_payload = {"sleep_total": 500}
        response = await client.patch(f"/wellness/{fake_id}", json=update_payload)

        assert response.status_code == 404


class TestDeleteWellnessEndpoint:
    """Tests for DELETE /wellness/{wellness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_wellness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test deleting a wellness record returns 204."""
        # Create a wellness record
        create_payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }
        create_response = await client.post("/wellness/", json=create_payload)
        wellness_id = create_response.json()["id"]

        # Delete the wellness record
        response = await client.delete(f"/wellness/{wellness_id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"/wellness/{wellness_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_wellness_endpoint_404(self, client: AsyncClient):
        """Test deleting a nonexistent wellness record returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/wellness/{fake_id}")

        assert response.status_code == 404


class TestListAthleteWellnessEndpoint:
    """Tests for GET /athletes/{athlete_id}/wellness endpoint."""

    @pytest.mark.asyncio
    async def test_list_athlete_wellness(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing wellness records returns 200 with items/total structure."""
        # Create multiple wellness records
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_in_db.id),
                "metric_date": f"2024-01-0{i+1}",
                "sleep_total": 480 + i * 10,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload)

        # List wellness records
        response = await client.get(f"/athletes/{athlete_in_db.id}/wellness")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_with_pagination(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing wellness records with pagination."""
        # Create multiple wellness records
        for i in range(5):
            payload = {
                "athlete_id": str(athlete_in_db.id),
                "metric_date": f"2024-01-0{i+1}",
                "sleep_total": 480 + i * 10,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload)

        # List with limit and offset
        response = await client.get(
            f"/athletes/{athlete_in_db.id}/wellness?limit=2&offset=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_with_date_filters(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing wellness records with date filters."""
        # Create wellness records across different dates
        dates = ["2024-01-01", "2024-01-15", "2024-02-01"]
        for d in dates:
            payload = {
                "athlete_id": str(athlete_in_db.id),
                "metric_date": d,
                "sleep_total": 480,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload)

        # Filter by date range
        response = await client.get(
            f"/athletes/{athlete_in_db.id}/wellness?date_from=2024-01-10&date_to=2024-01-20"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["metric_date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_list_athlete_wellness_empty(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing wellness records for athlete with none returns empty list."""
        response = await client.get(f"/athletes/{athlete_in_db.id}/wellness")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0