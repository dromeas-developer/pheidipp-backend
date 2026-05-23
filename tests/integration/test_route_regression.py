"""Route regression tests to verify old nested routes are removed.

These tests ensure that Phase 0 cleanup properly removed the old nested routes
and that the canonical routes on /athletes/{id}/* work correctly.
"""

import uuid

import pytest
from httpx import AsyncClient


# ============================================================================
# Route Regression Tests
# ============================================================================


class TestOldNestedRoutesRemoved:
    """Tests to verify old nested routes have been removed."""

    @pytest.mark.asyncio
    async def test_old_activities_nested_route_removed(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /activities/athletes/{athlete_id}/activities returns 404 (old route removed)."""
        athlete_id = registered_athlete["athlete_id"]
        response = await client.get(f"/activities/athletes/{athlete_id}/activities")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_old_wellness_nested_route_removed(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /wellness/athletes/{athlete_id}/wellness returns 404 (old route removed)."""
        athlete_id = registered_athlete["athlete_id"]
        response = await client.get(f"/wellness/athletes/{athlete_id}/wellness")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_old_fitness_nested_route_removed(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /fitness/athletes/{athlete_id}/fitness returns 404 (old route removed)."""
        athlete_id = registered_athlete["athlete_id"]
        response = await client.get(f"/fitness/athletes/{athlete_id}/fitness")
        assert response.status_code == 404


class TestCanonicalRoutesWork:
    """Tests to verify canonical routes on /athletes/{id}/* work correctly."""

    @pytest.mark.asyncio
    async def test_canonical_activities_route_works(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{athlete_id}/activities returns 200 with proper structure."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        activity_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Test Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
        }
        await client.post("/activities/", json=activity_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/activities", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_canonical_wellness_route_works(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{athlete_id}/wellness returns 200 with proper structure."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        wellness_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }
        await client.post("/wellness/", json=wellness_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/wellness", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_canonical_fitness_route_works(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{athlete_id}/fitness returns 200 with proper structure."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        fitness_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
            "source": "manual",
        }
        await client.post("/fitness/", json=fitness_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/fitness", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert len(data["items"]) == 1

    @pytest.mark.asyncio
    async def test_canonical_activities_empty(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{athlete_id}/activities returns empty list when no data."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/activities", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_canonical_wellness_empty(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{athlete_id}/wellness returns empty list when no data."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/wellness", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_canonical_fitness_empty(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{athlete_id}/fitness returns empty list when no data."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/fitness", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0


# ============================================================================
# Phase 1 Regression Tests
# ============================================================================


class TestPhase1Regression:
    """Regression tests for Phase 1 features."""

    @pytest.mark.asyncio
    async def test_get_athlete_includes_onboarding_complete_field(self, client: AsyncClient, registered_athlete: dict):
        """Test GET /athletes/{id} includes onboarding_complete field in response."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "onboarding_complete" in data
        assert data["onboarding_complete"] is False

    @pytest.mark.asyncio
    async def test_post_athletes_creates_athlete_with_onboarding_complete_false(self, client: AsyncClient, registered_athlete: dict):
        """Test registered athlete has onboarding_complete=false by default."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "onboarding_complete" in data
        assert data["onboarding_complete"] is False

    @pytest.mark.asyncio
    async def test_existing_activity_endpoints_unaffected(self, client: AsyncClient, registered_athlete: dict):
        """Test existing activity endpoints are unaffected by the model split."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        activity_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Test Run",
            "started_at": "2024-01-01T10:00:00",
            "finished_at": "2024-01-01T11:00:00",
        }
        post_response = await client.post("/activities/", json=activity_payload, headers=headers)
        assert post_response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_existing_wellness_endpoints_unaffected(self, client: AsyncClient, registered_athlete: dict):
        """Test existing wellness endpoints are unaffected by the model split."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        wellness_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "sleep_total": 480,
            "source": "manual",
            "timezone": "UTC",
        }
        post_response = await client.post("/wellness/", json=wellness_payload, headers=headers)
        assert post_response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_existing_fitness_endpoints_unaffected(self, client: AsyncClient, registered_athlete: dict):
        """Test existing fitness endpoints are unaffected by the model split."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        fitness_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-01",
            "tss": 75.5,
            "source": "manual",
        }
        post_response = await client.post("/fitness/", json=fitness_payload, headers=headers)
        assert post_response.status_code in [200, 201]

    def test_athlete_profile_import_path(self):
        """Test AthleteProfile import path is app.models.athlete_profile (not app.models.athlete)."""
        from app.models import athlete_profile
        from app.models.athlete_profile import AthleteProfile

        assert athlete_profile.AthleteProfile is AthleteProfile
        assert hasattr(AthleteProfile, "athlete_id")
        assert hasattr(AthleteProfile, "first_name")
