"""Integration tests for Fitness API endpoints.

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
# Fitness Endpoint Tests
# ============================================================================


class TestCreateFitnessEndpoint:
    """Tests for POST /fitness/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_fitness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a fitness record returns 201 and response fields."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "tss": 75.5,
            "atl": 42.0,
            "ctl": 65.0,
            "tsb": 23.0,
            "source": "manual",
        }

        response = await client.post("/fitness/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["athlete_id"] == str(athlete_in_db.id)
        assert data["metric_date"] == "2024-01-01"
        assert data["tss"] == 75.5
        assert data["atl"] == 42.0
        assert data["ctl"] == 65.0
        assert data["tsb"] == 23.0

    @pytest.mark.asyncio
    async def test_create_fitness_minimal(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a fitness record with minimal fields."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
        }

        response = await client.post("/fitness/", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["metric_date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_create_fitness_duplicate_date(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a fitness record with duplicate date returns 400."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }

        # Create first record
        response1 = await client.post("/fitness/", json=payload)
        assert response1.status_code == 201

        # Try to create duplicate
        response2 = await client.post("/fitness/", json=payload)
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_create_fitness_nonexistent_athlete(self, client: AsyncClient):
        """Test creating a fitness record for nonexistent athlete returns 400."""
        payload = {
            "athlete_id": str(uuid.uuid4()),
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }

        response = await client.post("/fitness/", json=payload)

        assert response.status_code == 400


class TestGetFitnessEndpoint:
    """Tests for GET /fitness/{fitness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_fitness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test getting a fitness record returns 200 and correct payload."""
        # First create a fitness record
        create_payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "tss": 75.5,
            "atl": 42.0,
            "ctl": 65.0,
            "tsb": 23.0,
        }
        create_response = await client.post("/fitness/", json=create_payload)
        fitness_id = create_response.json()["id"]

        # Now get the fitness record
        response = await client.get(f"/fitness/{fitness_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == fitness_id
        assert data["tss"] == 75.5

    @pytest.mark.asyncio
    async def test_get_fitness_endpoint_404(self, client: AsyncClient):
        """Test getting a nonexistent fitness record returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/fitness/{fake_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Fitness record not found"


class TestUpdateFitnessEndpoint:
    """Tests for PATCH /fitness/{fitness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_fitness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test updating a fitness record returns 200 with updated fields."""
        # Create a fitness record
        create_payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }
        create_response = await client.post("/fitness/", json=create_payload)
        fitness_id = create_response.json()["id"]

        # Update the fitness record
        update_payload = {"tss": 100.0, "atl": 50.0}
        response = await client.patch(f"/fitness/{fitness_id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["tss"] == 100.0
        assert data["atl"] == 50.0

    @pytest.mark.asyncio
    async def test_update_fitness_conflicting_date(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test updating a fitness record with conflicting date returns 400."""
        # Create first fitness record
        create_payload1 = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }
        response1 = await client.post("/fitness/", json=create_payload1)
        fitness_id1 = response1.json()["id"]

        # Create second fitness record
        create_payload2 = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-02",
            "tss": 80.0,
        }
        response2 = await client.post("/fitness/", json=create_payload2)
        fitness_id2 = response2.json()["id"]

        # Try to update second record with first record's date
        update_payload = {"metric_date": "2024-01-01"}
        response = await client.patch(f"/fitness/{fitness_id2}", json=update_payload)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_fitness_endpoint_404(self, client: AsyncClient):
        """Test updating a nonexistent fitness record returns 404."""
        fake_id = str(uuid.uuid4())
        update_payload = {"tss": 100.0}
        response = await client.patch(f"/fitness/{fake_id}", json=update_payload)

        assert response.status_code == 404


class TestDeleteFitnessEndpoint:
    """Tests for DELETE /fitness/{fitness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_fitness_endpoint(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test deleting a fitness record returns 204."""
        # Create a fitness record
        create_payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }
        create_response = await client.post("/fitness/", json=create_payload)
        fitness_id = create_response.json()["id"]

        # Delete the fitness record
        response = await client.delete(f"/fitness/{fitness_id}")

        assert response.status_code == 204

        # Verify it's gone
        get_response = await client.get(f"/fitness/{fitness_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_fitness_endpoint_404(self, client: AsyncClient):
        """Test deleting a nonexistent fitness record returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/fitness/{fake_id}")

        assert response.status_code == 404


class TestListAthleteFitnessEndpoint:
    """Tests for GET /athletes/{athlete_id}/fitness endpoint."""

    @pytest.mark.asyncio
    async def test_list_athlete_fitness(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing fitness records returns 200 with items/total structure."""
        # Create multiple fitness records
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_in_db.id),
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            await client.post("/fitness/", json=payload)

        # List fitness records
        response = await client.get(f"/athletes/{athlete_in_db.id}/fitness")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_with_pagination(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing fitness records with pagination."""
        # Create multiple fitness records
        for i in range(5):
            payload = {
                "athlete_id": str(athlete_in_db.id),
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            await client.post("/fitness/", json=payload)

        # List with limit and offset
        response = await client.get(
            f"/athletes/{athlete_in_db.id}/fitness?limit=2&offset=0"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_with_date_filters(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing fitness records with date filters."""
        # Create fitness records across different dates
        dates = ["2024-01-01", "2024-01-15", "2024-02-01"]
        for d in dates:
            payload = {
                "athlete_id": str(athlete_in_db.id),
                "metric_date": d,
                "tss": 75.5,
            }
            await client.post("/fitness/", json=payload)

        # Filter by date range
        response = await client.get(
            f"/athletes/{athlete_in_db.id}/fitness?date_from=2024-01-10&date_to=2024-01-20"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["metric_date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_empty(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test listing fitness records for athlete with none returns empty list."""
        response = await client.get(f"/athletes/{athlete_in_db.id}/fitness")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestCreateFitnessInvalidPayload:
    """Tests for invalid payload handling on POST /fitness/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_fitness_missing_required_fields_returns_422(
        self, client: AsyncClient
    ):
        """Test creating a fitness record with missing required fields returns 422."""
        # Payload missing athlete_id and metric_date (both required)
        payload = {
            "tss": 75.5,
        }

        response = await client.post("/fitness/", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_fitness_invalid_date_format_returns_422(
        self, client: AsyncClient, athlete_in_db: Athlete
    ):
        """Test creating a fitness record with invalid metric_date format returns 422."""
        payload = {
            "athlete_id": str(athlete_in_db.id),
            "metric_date": "not-a-date",
            "tss": 75.5,
        }

        response = await client.post("/fitness/", json=payload)

        assert response.status_code == 422


class TestFitnessAthleteIsolation:
    """Tests for athlete data isolation on fitness endpoints."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_fitness_records(
        self, test_db_session: AsyncSession, client: AsyncClient
    ):
        """Test that athlete B cannot see athlete A's fitness records via list endpoint."""
        athlete_repo = AthleteRepository(test_db_session)

        # Create two athletes
        athlete_a = await athlete_repo.create(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        athlete_b = await athlete_repo.create(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )

        # Create fitness records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_a.id),
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            response = await client.post("/fitness/", json=payload)
            assert response.status_code == 201

        # List fitness records for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b.id}/fitness")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_athlete_b_list_does_not_include_athlete_a_records(
        self, test_db_session: AsyncSession, client: AsyncClient
    ):
        """Test that athlete B's fitness list does not contain athlete A's specific record IDs."""
        athlete_repo = AthleteRepository(test_db_session)

        # Create two athletes
        athlete_a = await athlete_repo.create(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        athlete_b = await athlete_repo.create(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )

        # Create fitness records for athlete A
        fitness_ids_athlete_a = []
        for i in range(2):
            payload = {
                "athlete_id": str(athlete_a.id),
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5,
            }
            response = await client.post("/fitness/", json=payload)
            assert response.status_code == 201
            fitness_ids_athlete_a.append(response.json()["id"])

        # List fitness records for athlete B - should not include athlete A's IDs
        response = await client.get(f"/athletes/{athlete_b.id}/fitness")

        assert response.status_code == 200
        data = response.json()

        for item in data["items"]:
            assert item["id"] not in fitness_ids_athlete_a