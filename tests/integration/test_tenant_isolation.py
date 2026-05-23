"""Integration tests for tenant isolation across all resource endpoints.

These tests verify that all endpoints properly scope data to the requesting athlete,
ensuring no cross-athlete data leakage.
"""

import uuid

import pytest
from httpx import AsyncClient


class TestWellnessTenantIsolation:
    """Tests for wellness data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_wellness(
        self, client: AsyncClient
    ):
        """Test that athlete B cannot see athlete A's wellness records."""
        # Register athlete A
        email_a = f"iso_a_{uuid.uuid4().hex[:8]}@example.com"
        resp_a = await client.post("/auth/register", json={"email": email_a, "password": "secure-test-password-123"})
        assert resp_a.status_code == 201
        data_a = resp_a.json()
        athlete_a_id = str(data_a["athlete_id"])
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        # Register athlete B
        email_b = f"iso_b_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        data_b = resp_b.json()
        athlete_b_id = str(data_b["athlete_id"])
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        # Create wellness records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": athlete_a_id,
                "metric_date": f"2024-01-0{i+1}",
                "sleep_total": 480 + i * 10,
                "source": "manual",
                "timezone": "UTC",
            }
            response = await client.post("/wellness/", json=payload, headers=headers_a)
            assert response.status_code == 201

        # List wellness for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b_id}/wellness", headers=headers_b)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestFitnessTenantIsolation:
    """Tests for fitness data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_fitness(
        self, client: AsyncClient
    ):
        """Test that athlete B cannot see athlete A's fitness records."""
        email_a = f"iso_fit_a_{uuid.uuid4().hex[:8]}@example.com"
        resp_a = await client.post("/auth/register", json={"email": email_a, "password": "secure-test-password-123"})
        assert resp_a.status_code == 201
        data_a = resp_a.json()
        athlete_a_id = str(data_a["athlete_id"])
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        email_b = f"iso_fit_b_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        data_b = resp_b.json()
        athlete_b_id = str(data_b["athlete_id"])
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        # Create fitness records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": athlete_a_id,
                "metric_date": f"2024-01-0{i+1}",
                "tss": 75.5 + i * 10,
            }
            response = await client.post("/fitness/", json=payload, headers=headers_a)
            assert response.status_code == 201

        # List fitness for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b_id}/fitness", headers=headers_b)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestActivityTenantIsolation:
    """Tests for activity data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_activities(
        self, client: AsyncClient
    ):
        """Test that athlete B cannot see athlete A's activities."""
        email_a = f"iso_act_a_{uuid.uuid4().hex[:8]}@example.com"
        resp_a = await client.post("/auth/register", json={"email": email_a, "password": "secure-test-password-123"})
        assert resp_a.status_code == 201
        data_a = resp_a.json()
        athlete_a_id = str(data_a["athlete_id"])
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        email_b = f"iso_act_b_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        data_b = resp_b.json()
        athlete_b_id = str(data_b["athlete_id"])
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        # Create activities for athlete A
        for i in range(3):
            payload = {
                "athlete_id": athlete_a_id,
                "activity_type": "running",
                "title": f"Morning Run {i+1}",
                "started_at": f"2024-01-0{i+1}T10:00:00",
                "finished_at": f"2024-01-0{i+1}T11:00:00",
            }
            response = await client.post("/activities/", json=payload, headers=headers_a)
            assert response.status_code == 201

        # List activities for athlete B - should be empty
        response = await client.get(f"/athletes/{athlete_b_id}/activities", headers=headers_b)

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


class TestPhysiologyTenantIsolation:
    """Tests for physiology data tenant isolation."""

    @pytest.mark.asyncio
    async def test_athlete_b_cannot_see_athlete_a_physiology(
        self, client: AsyncClient
    ):
        """Test that athlete B cannot see athlete A's physiology records."""
        email_a = f"iso_phy_a_{uuid.uuid4().hex[:8]}@example.com"
        resp_a = await client.post("/auth/register", json={"email": email_a, "password": "secure-test-password-123"})
        assert resp_a.status_code == 201
        data_a = resp_a.json()
        athlete_a_id = str(data_a["athlete_id"])
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        email_b = f"iso_phy_b_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        data_b = resp_b.json()
        athlete_b_id = str(data_b["athlete_id"])
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        # Create physiology records for athlete A
        for i in range(3):
            payload = {
                "athlete_id": athlete_a_id,
                "ftp": 280 + i * 5,
                "lt1": 220 + i,
                "lt2": 250 + i,
                "source": "manual",
                "effective_from": f"2024-0{i+1}-01",
                "effective_to": f"2024-0{i+1}-28",
            }
            response = await client.post("/physiology/", json=payload, headers=headers_a)
            assert response.status_code == 201

        # List physiology for athlete B - should be empty (plain list, not paginated)
        response = await client.get(f"/athletes/{athlete_b_id}/physiology", headers=headers_b)

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestPaginationTenantIsolation:
    """Tests for pagination scoping to the correct tenant."""

    @pytest.mark.asyncio
    async def test_pagination_respects_tenant_boundaries(
        self, client: AsyncClient
    ):
        """Test that pagination returns correct totals scoped to each athlete."""
        email_a = f"iso_pag_a_{uuid.uuid4().hex[:8]}@example.com"
        resp_a = await client.post("/auth/register", json={"email": email_a, "password": "secure-test-password-123"})
        assert resp_a.status_code == 201
        data_a = resp_a.json()
        athlete_a_id = str(data_a["athlete_id"])
        headers_a = {"Authorization": f"Bearer {data_a['access_token']}"}

        email_b = f"iso_pag_b_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        data_b = resp_b.json()
        athlete_b_id = str(data_b["athlete_id"])
        headers_b = {"Authorization": f"Bearer {data_b['access_token']}"}

        # Create 5 wellness records for athlete A
        for i in range(5):
            payload = {
                "athlete_id": athlete_a_id,
                "metric_date": f"2024-01-{i+1:02d}",
                "sleep_total": 480,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload, headers=headers_a)

        # Create 3 wellness records for athlete B
        for i in range(3):
            payload = {
                "athlete_id": athlete_b_id,
                "metric_date": f"2024-02-{i+1:02d}",
                "sleep_total": 480,
                "source": "manual",
                "timezone": "UTC",
            }
            await client.post("/wellness/", json=payload, headers=headers_b)

        # List wellness for athlete A - should have 5
        response_a = await client.get(f"/athletes/{athlete_a_id}/wellness", headers=headers_a)
        assert response_a.status_code == 200
        data_a = response_a.json()
        assert len(data_a["items"]) == 5
        assert data_a["total"] == 5

        # List wellness for athlete B - should have 3
        response_b = await client.get(f"/athletes/{athlete_b_id}/wellness", headers=headers_b)
        assert response_b.status_code == 200
        data_b = response_b.json()
        assert len(data_b["items"]) == 3
        assert data_b["total"] == 3
