"""Integration tests for Athletes API endpoints.

These tests verify API endpoints with database dependencies
and JWT authentication.
"""

import uuid

import pytest
from httpx import AsyncClient


# ============================================================================
# Auth Registration Tests (replaces old POST /athletes/ tests)
# ============================================================================


class TestRegisterAthleteEndpoint:
    """Tests for POST /auth/register endpoint."""

    @pytest.mark.asyncio
    async def test_register_athlete_endpoint(self, client: AsyncClient):
        """Test registering an athlete via auth returns 201 and TokenResponse."""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123456",
        }

        response = await client.post("/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "athlete_id" in data

    @pytest.mark.asyncio
    async def test_register_athlete_invalid_email(self, client: AsyncClient):
        """Test registering with invalid email returns 422."""
        payload = {
            "email": "not-an-email",
            "password": "securepassword123456",
        }

        response = await client.post("/auth/register", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_athlete_short_password(self, client: AsyncClient):
        """Test registering with password less than 12 chars returns 422."""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "short1",
        }

        response = await client.post("/auth/register", json=payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_register_athlete_duplicate_email_returns_conflict(
        self, client: AsyncClient
    ):
        """Test registering with the same email returns 409 Conflict."""
        email = f"duplicate_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": email,
            "password": "securepassword123456",
        }

        # Register first athlete
        response1 = await client.post("/auth/register", json=payload)
        assert response1.status_code == 201

        # Try to register second athlete with the same email
        response2 = await client.post("/auth/register", json=payload)

        assert response2.status_code == 409


# ============================================================================
# Athlete Endpoint Tests
# ============================================================================


class TestGetAthleteEndpoint:
    """Tests for GET /athletes/{athlete_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_athlete_endpoint(self, client: AsyncClient, registered_athlete: dict):
        """Test getting an athlete by ID returns 200 and nested profile."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == athlete_id
        assert "status" in data

    @pytest.mark.asyncio
    async def test_get_athlete_endpoint_401_without_auth(self, client: AsyncClient):
        """Test getting an athlete without auth returns 401."""
        athlete_id = str(uuid.uuid4())
        response = await client.get(f"/athletes/{athlete_id}")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_athlete_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test getting a nonexistent athlete returns 403 (require_self rejects mismatched athlete_id)."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/athletes/{fake_id}", headers=headers)

        assert response.status_code == 403


class TestUpdateAthleteEndpoint:
    """Tests for PATCH /athletes/{athlete_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_athlete_endpoint(self, client: AsyncClient, registered_athlete: dict):
        """Test updating an athlete's status returns 200 and updated value."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        update_payload = {"status": "inactive"}
        response = await client.patch(f"/athletes/{athlete_id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_update_athlete_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test updating a nonexistent athlete returns 403 (require_self rejects mismatched athlete_id)."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        update_payload = {"status": "inactive"}
        response = await client.patch(f"/athletes/{fake_id}", json=update_payload, headers=headers)

        assert response.status_code == 403


class TestUpsertProfileEndpoint:
    """Tests for PUT /athletes/{athlete_id}/profile endpoint."""

    @pytest.mark.asyncio
    async def test_upsert_profile_endpoint(self, client: AsyncClient, registered_athlete: dict):
        """Test creating/updating a profile returns 200 and profile data."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        response = await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == athlete_id
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["display_name"] == "johndoe"

    @pytest.mark.asyncio
    async def test_upsert_profile_update_existing(self, client: AsyncClient, registered_athlete: dict):
        """Test updating an existing profile returns 200 with updated values."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        initial_profile = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=initial_profile, headers=headers)

        updated_profile = {
            "first_name": "Jane",
            "last_name": "Smith",
            "display_name": "janesmith",
        }
        response = await client.put(f"/athletes/{athlete_id}/profile", json=updated_profile, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Smith"
        assert data["display_name"] == "janesmith"


class TestGetProfileEndpoint:
    """Tests for GET /athletes/{athlete_id}/profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_profile_endpoint(self, client: AsyncClient, registered_athlete: dict):
        """Test getting an athlete's profile returns 200."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/profile", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == athlete_id
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_get_profile_endpoint_404(self, client: AsyncClient, registered_athlete: dict):
        """Test getting profile for athlete without one returns 404."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/profile", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Profile not found"


# ============================================================================
# Onboarding Endpoint Tests
# ============================================================================


class TestOnboardAthleteEndpoint:
    """Tests for POST /athletes/{athlete_id}/onboarding endpoint."""

    @pytest.mark.asyncio
    async def test_onboard_athlete_success(self, client: AsyncClient, registered_athlete: dict):
        """Test successful athlete onboarding."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile (required for onboarding)
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        # Perform onboarding
        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "name": "Base Building",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "goal": "Build aerobic base",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["onboarding_complete"] is True
        assert "preferences" in data
        assert "training_block" in data

    @pytest.mark.asyncio
    async def test_onboard_athlete_malformed_payload(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with malformed payload returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json={"preferences": {"invalid": "data"}},
            headers=headers,
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_malformed_weekly_schedule(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with malformed weekly_schedule (invalid day key) returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "xyz": {"available": True, "max_hours": 1.0, "long_workout": False},
                    },
                    "available_days_count": 2,
                },
            },
            "training_block": {
                "goal_type": "race",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_long_workout_on_unavailable_day(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with long_workout=True on unavailable day returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": False, "max_hours": 0, "long_workout": True},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": False, "max_hours": 0, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": False, "max_hours": 0, "long_workout": False},
                        "sat": {"available": False, "max_hours": 0, "long_workout": False},
                        "sun": {"available": False, "max_hours": 0, "long_workout": False},
                    },
                    "available_days_count": 0,
                },
            },
            "training_block": {
                "goal_type": "race",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_available_days_count_mismatch(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with available_days_count mismatch returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 3,  # Should be 5
                },
            },
            "training_block": {
                "goal_type": "race",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_missing_day_entries(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with missing day entries returns 422."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                    },
                    "available_days_count": 1,
                },
            },
            "training_block": {
                "goal_type": "race",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_not_found(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with nonexistent athlete returns 403 (require_self rejects mismatched athlete_id)."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "goal_type": "race",
            },
        }
        response = await client.post(f"/athletes/{fake_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_onboard_athlete_response_includes_twin_state(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding response includes populated twin_state."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert "twin_state" in data
        assert data["twin_state"] is not None
        assert data["twin_state"]["athlete_id"] == athlete_id
        assert "computation_summary" in data["twin_state"]
        assert "computation_metadata" in data["twin_state"]

    @pytest.mark.asyncio
    async def test_onboard_athlete_valid_weekly_schedule_returns_201(self, client: AsyncClient, registered_athlete: dict):
        """Test onboarding with valid weekly_schedule containing all 7 days returns 201."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_onboard_athlete_already_onboarded_returns_409(self, client: AsyncClient, registered_athlete: dict):
        """Test re-onboarding returns 409 Conflict."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "name": "Test Block",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "goal": "Test",
            },
        }
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        # Try to onboard again
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        assert response.status_code == 409


class TestGetOnboardingStatusEndpoint:
    """Tests for GET /athletes/{athlete_id}/onboarding/status endpoint."""

    @pytest.mark.asyncio
    async def test_get_onboarding_status_not_onboarded(self, client: AsyncClient, registered_athlete: dict):
        """Test getting onboarding status before onboarding."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/onboarding/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is False
        assert data["preferences"] is None
        assert data["training_block"] is None

    @pytest.mark.asyncio
    async def test_get_onboarding_status_after_onboarding(self, client: AsyncClient, registered_athlete: dict):
        """Test getting onboarding status after successful onboarding."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "name": "Test Block",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "goal": "Test",
            },
        }
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/onboarding/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["preferences"] is not None
        assert data["training_block"] is not None

    @pytest.mark.asyncio
    async def test_get_onboarding_status_404_for_nonexistent_athlete(self, client: AsyncClient, registered_athlete: dict):
        """Test getting onboarding status for nonexistent athlete returns 403 (require_self rejects mismatched athlete_id)."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/athletes/{fake_id}/onboarding/status", headers=headers)

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_onboarding_status_returns_populated_preferences_and_training_block(self, client: AsyncClient, registered_athlete: dict):
        """Test returns preferences and training_block populated after onboarding."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon",
            },
        }
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/onboarding/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["preferences"] is not None
        assert data["preferences"]["sport_background"] == "running_primary"
        assert data["training_block"] is not None
        assert data["training_block"]["goal_type"] == "race"

    @pytest.mark.asyncio
    async def test_get_onboarding_status_returns_twin_state(self, client: AsyncClient, registered_athlete: dict):
        """Test returns populated twin_state in status response."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "goal_type": "race",
            },
        }
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers)

        response = await client.get(f"/athletes/{athlete_id}/onboarding/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "twin_state" in data
        assert data["twin_state"] is not None
        assert data["twin_state"]["athlete_id"] == athlete_id
        assert "computation_summary" in data["twin_state"]
        assert "computation_metadata" in data["twin_state"]


# ============================================================================
# Onboarding State Transition Tests
# ============================================================================


class TestAthleteOnboardingStateTransitions:
    """Tests for athlete onboarding state transitions."""

    @pytest.mark.asyncio
    async def test_athlete_onboarding_transitions_to_active(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test that completing onboarding changes athlete status to active."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile (required for onboarding)
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1990-01-01",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        profile_response = await client.put(
            f"/athletes/{athlete_id}/profile",
            json=profile_payload,
            headers=headers,
        )
        assert profile_response.status_code == 200

        # Complete onboarding
        onboarding_payload = {
            "preferences": {
                "weekly_schedule": {
                    "days": {
                        "mon": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "tue": {"available": False, "max_hours": 0, "long_workout": False},
                        "wed": {"available": True, "max_hours": 1.5, "long_workout": False},
                        "thu": {"available": False, "max_hours": 0, "long_workout": False},
                        "fri": {"available": True, "max_hours": 1.0, "long_workout": False},
                        "sat": {"available": True, "max_hours": 2.5, "long_workout": True},
                        "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
                    },
                    "available_days_count": 5,
                },
            },
            "training_block": {
                "name": "Base Building",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "goal": "Build aerobic base",
            },
        }
        onboard_response = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload,
            headers=headers,
        )
        assert onboard_response.status_code == 201

        # Verify athlete status has changed to "active" and onboarding_complete is True
        final_get_response = await client.get(f"/athletes/{athlete_id}", headers=headers)
        assert final_get_response.status_code == 200
        final_data = final_get_response.json()
        assert final_data["status"] == "active"
        assert final_data["onboarding_complete"] is True
