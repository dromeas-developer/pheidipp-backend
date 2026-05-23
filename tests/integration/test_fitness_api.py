"""Integration tests for Fitness API endpoints.

These tests verify API endpoints with database dependencies
and JWT authentication.
"""

import uuid
from datetime import date

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


# ============================================================================
# Fitness Endpoint Tests
# ============================================================================


class TestCreateFitnessEndpoint:
    """Tests for POST /fitness/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_fitness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a fitness record returns 201 and response fields."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
            "atl": 42.0,
            "ctl": 65.0,
            "tsb": 23.0,
            "source": "manual",
        }

        response = await client.post("/fitness/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["athlete_id"] == athlete_id
        assert data["metric_date"] == "2024-01-01"
        assert data["tss"] == 75.5
        assert data["atl"] == 42.0
        assert data["ctl"] == 65.0
        assert data["tsb"] == 23.0

    @pytest.mark.asyncio
    async def test_create_fitness_minimal(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a fitness record with minimal fields."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
        }

        response = await client.post("/fitness/", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["metric_date"] == "2024-01-01"

    @pytest.mark.asyncio
    async def test_create_fitness_duplicate_date(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a fitness record with duplicate date returns 400."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }

        response1 = await client.post("/fitness/", json=payload, headers=headers)
        assert response1.status_code == 201

        response2 = await client.post("/fitness/", json=payload, headers=headers)
        assert response2.status_code == 400

    @pytest.mark.asyncio
    async def test_create_fitness_nonexistent_athlete(self, client: AsyncClient, registered_athlete: dict):
        """Test creating a fitness record for nonexistent athlete returns 400."""
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": str(uuid.uuid4()),
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }

        response = await client.post("/fitness/", json=payload, headers=headers)

        assert response.status_code == 403


class TestGetFitnessEndpoint:
    """Tests for GET /fitness/{fitness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_fitness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test getting a fitness record returns 200 and correct payload."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
            "atl": 42.0,
            "ctl": 65.0,
            "tsb": 23.0,
        }
        create_response = await client.post("/fitness/", json=create_payload, headers=headers)
        fitness_id = create_response.json()["id"]

        response = await client.get(f"/fitness/{fitness_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == fitness_id
        assert data["tss"] == 75.5

    @pytest.mark.asyncio
    async def test_get_fitness_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test getting a nonexistent fitness record returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/fitness/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Fitness record not found"


class TestUpdateFitnessEndpoint:
    """Tests for PATCH /fitness/{fitness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_fitness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test updating a fitness record returns 200 with updated fields."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }
        create_response = await client.post("/fitness/", json=create_payload, headers=headers)
        fitness_id = create_response.json()["id"]

        update_payload = {"tss": 100.0, "atl": 50.0}
        response = await client.patch(f"/fitness/{fitness_id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["tss"] == 100.0
        assert data["atl"] == 50.0

    @pytest.mark.asyncio
    async def test_update_fitness_conflicting_date(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test updating a fitness record with conflicting date returns 400."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload1 = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }
        response1 = await client.post("/fitness/", json=create_payload1, headers=headers)
        fitness_id1 = response1.json()["id"]

        create_payload2 = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-02",
            "tss": 80.0,
        }
        response2 = await client.post("/fitness/", json=create_payload2, headers=headers)
        fitness_id2 = response2.json()["id"]

        update_payload = {"metric_date": "2024-01-01"}
        response = await client.patch(f"/fitness/{fitness_id2}", json=update_payload, headers=headers)

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_update_fitness_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test updating a nonexistent fitness record returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        update_payload = {"tss": 100.0}
        response = await client.patch(f"/fitness/{fake_id}", json=update_payload, headers=headers)

        assert response.status_code == 404


class TestDeleteFitnessEndpoint:
    """Tests for DELETE /fitness/{fitness_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_fitness_endpoint(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test deleting a fitness record returns 204."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        create_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
        }
        create_response = await client.post("/fitness/", json=create_payload, headers=headers)
        fitness_id = create_response.json()["id"]

        response = await client.delete(f"/fitness/{fitness_id}", headers=headers)

        assert response.status_code == 204

        get_response = await client.get(f"/fitness/{fitness_id}", headers=headers)
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_fitness_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test deleting a nonexistent fitness record returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.delete(f"/fitness/{fake_id}", headers=headers)

        assert response.status_code == 404


class TestListAthleteFitnessEndpoint:
    """Tests for GET /athletes/{athlete_id}/fitness endpoint."""

    @pytest.mark.asyncio
    async def test_list_athlete_fitness(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing fitness records returns 200 with items/total structure."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        for i in range(3):
            payload = {
                "athlete_id": athlete_id,
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            await client.post("/fitness/", json=payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/fitness", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 3
        assert data["total"] == 3

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_with_pagination(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing fitness records with pagination."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        for i in range(5):
            payload = {
                "athlete_id": athlete_id,
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            await client.post("/fitness/", json=payload, headers=headers)

        response = await client.get(
            f"/athletes/{athlete_id}/fitness?limit=2&offset=0", headers=headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 5

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_with_date_filters(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing fitness records with date filters."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        dates = ["2024-01-01", "2024-01-15", "2024-02-01"]
        for d in dates:
            payload = {
                "athlete_id": athlete_id,
                "metric_date": d,
                "tss": 75.5,
            }
            await client.post("/fitness/", json=payload, headers=headers)

        response = await client.get(
            f"/athletes/{athlete_id}/fitness?date_from=2024-01-10&date_to=2024-01-20",
            headers=headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["items"][0]["metric_date"] == "2024-01-15"

    @pytest.mark.asyncio
    async def test_list_athlete_fitness_empty(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test listing fitness records for athlete with none returns empty list."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/fitness", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestCreateFitnessInvalidPayload:
    """Tests for invalid payload handling on POST /fitness/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_fitness_missing_required_fields_returns_422(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a fitness record with missing required fields returns 422."""
        headers = registered_athlete["headers"]
        payload = {"tss": 75.5}

        response = await client.post("/fitness/", json=payload, headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_fitness_invalid_date_format_returns_422(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test creating a fitness record with invalid metric_date format returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        payload = {
            "athlete_id": athlete_id,
            "metric_date": "not-a-date",
            "tss": 75.5,
        }

        response = await client.post("/fitness/", json=payload, headers=headers)

        assert response.status_code == 422


class TestFitnessAthleteIsolation:
    """Tests for athlete data isolation on fitness endpoints."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_fitness_records(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test that a different athlete cannot see another's fitness records via list endpoint."""
        athlete_a = registered_athlete
        athlete_a_id = athlete_a["athlete_id"]
        headers_a = athlete_a["headers"]

        # Register a second athlete for isolation testing
        email_b = f"isolate_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        athlete_b_data = resp_b.json()
        athlete_b_id = str(athlete_b_data["athlete_id"])
        headers_b = {"Authorization": f"Bearer {athlete_b_data['access_token']}"}

        # Create fitness records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": athlete_a_id,
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            response = await client.post("/fitness/", json=payload, headers=headers_a)
            assert response.status_code == 201

        # List fitness records for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b_id}/fitness", headers=headers_b)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 0
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_athlete_b_list_does_not_include_athlete_a_records(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test that athlete B's list does not include athlete A's fitness records."""
        athlete_a = registered_athlete
        athlete_a_id = athlete_a["athlete_id"]
        headers_a = athlete_a["headers"]

        # Register a second athlete
        email_b = f"isolate2_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        athlete_b_data = resp_b.json()
        athlete_b_id = str(athlete_b_data["athlete_id"])
        headers_b = {"Authorization": f"Bearer {athlete_b_data['access_token']}"}

        # Create fitness records for both athletes
        for i in range(2):
            payload_a = {
                "athlete_id": athlete_a_id,
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5,
            }
            await client.post("/fitness/", json=payload_a, headers=headers_a)

            payload_b = {
                "athlete_id": athlete_b_id,
                "metric_date": f"2024-01-0{i+1}",
                "tss": 80.0,
            }
            await client.post("/fitness/", json=payload_b, headers=headers_b)

        # List fitness for athlete A - should only have A's records
        response_a = await client.get(f"/athletes/{athlete_a_id}/fitness", headers=headers_a)
        assert response_a.status_code == 200
        data_a = response_a.json()
        for item in data_a["items"]:
            assert item["athlete_id"] == athlete_a_id

        # List fitness for athlete B - should only have B's records
        response_b = await client.get(f"/athletes/{athlete_b_id}/fitness", headers=headers_b)
        assert response_b.status_code == 200
        data_b = response_b.json()
        for item in data_b["items"]:
            assert item["athlete_id"] == athlete_b_id
