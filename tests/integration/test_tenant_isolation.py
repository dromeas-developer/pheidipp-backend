"""Integration tests for tenant isolation across all resource endpoints.

These tests verify that all endpoints properly scope data to the requesting athlete,
ensuring no cross-athlete data leakage.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import AthleteStatus
from app.repositories.athlete_repository import AthleteRepository


@pytest.fixture
async def athlete_a(test_db_session: AsyncSession) -> Athlete:
    """Create athlete A in the database for testing."""
    athlete_repo = AthleteRepository(test_db_session)
    athlete = await athlete_repo.create(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
    )
    return athlete


@pytest.fixture
async def athlete_b(test_db_session: AsyncSession) -> Athlete:
    """Create athlete B in the database for testing."""
    athlete_repo = AthleteRepository(test_db_session)
    athlete = await athlete_repo.create(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
    )
    return athlete


class TestWellnessTenantIsolation:
    """Tests for wellness data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_wellness(
        self, client: AsyncClient, athlete_a: Athlete, athlete_b: Athlete
    ):
        """Test that athlete B cannot see athlete A's wellness records."""
        # Create wellness records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_a.id),
                "metric_date": f"2024-01-0{i+1}",
                "sleep_total": 480 + i * 10,
                "source": "manual",
                "timezone": "UTC",
            }
            response = await client.post("/wellness/", json=payload)
            assert response.status_code == 201

        # List wellness for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b.id}/wellness")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestFitnessTenantIsolation:
    """Tests for fitness data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_fitness(
        self, client: AsyncClient, athlete_a: Athlete, athlete_b: Athlete
    ):
        """Test that athlete B cannot see athlete A's fitness records."""
        # Create fitness records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_a.id),
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            response = await client.post("/fitness/", json=payload)
            assert response.status_code == 201

        # List fitness for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b.id}/fitness")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestActivityTenantIsolation:
    """Tests for activity data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_activities(
        self, client: AsyncClient, athlete_a: Athlete, athlete_b: Athlete
    ):
        """Test that athlete B cannot see athlete A's activities."""
        # Create activities for athlete A
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_a.id),
                "activity_type": "running",
                "title": f"Morning Run {i+1}",
                "started_at": f"2024-01-0{i+1}T10:00:00",
                "finished_at": f"2024-01-0{i+1}T11:00:00",
            }
            response = await client.post("/activities/", json=payload)
            assert response.status_code == 201

        # List activities for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b.id}/activities")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestPhysiologyTenantIsolation:
    """Tests for physiology data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_physiology(
        self, client: AsyncClient, athlete_a: Athlete, athlete_b: Athlete
    ):
        """Test that athlete B cannot see athlete A's physiology records."""
        # Create physiology records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_a.id),
                "ftp": 280 + i * 5,
                "lt1": 220 + i,
                "lt2": 250 + i,
                "source": "manual",
                "effective_from": f"2024-0{i+1}-01",
                "effective_to": f"2024-0{i+1}-28",
            }
            response = await client.post("/physiology/", json=payload)
            assert response.status_code == 201

        # List physiology for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b.id}/physiology")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestPaginationTenantIsolation:
    """Tests for pagination scoping to the correct tenant."""

    @pytest.mark.asyncio
    async def test_pagination_respects_tenant_boundaries(
        self, client: AsyncClient, athlete_a: Athlete, athlete_b: Athlete
    ):
        """Test that pagination returns correct totals scoped to each athlete."""
        # Create 5 wellness records for athlete A
        for i in range(5):
            payload = {
                "athlete_id": str(athlete_a.id),
                "metric_date": f"2024-01-{i+1:02d}",
                "sleep_total": 480,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload)

        # Create 3 wellness records for athlete B
        for i in range(3):
            payload = {
                "athlete_id": str(athlete_b.id),
                "metric_date": f"2024-02-{i+1:02d}",
                "sleep_total": 480,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload)

        # List wellness for athlete A - should have 5
        response_a = await client.get(f"/athletes/{athlete_a.id}/wellness")
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert len(data_a["items"]) == 5
        assert data_a["total"] == 5

        # List wellness for athlete B - should have 3
        response_b = await client.get(f"/athletes/{athlete_b.id}/wellness")
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert len(data_b["items"]) == 3
        assert data_b["total"] == 3