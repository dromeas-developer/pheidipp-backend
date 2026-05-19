"""Integration tests for Athletes API endpoints.

These tests verify API endpoints with database dependencies.
"""

import uuid

import pytest
from httpx import AsyncClient


# ============================================================================
# Athlete Endpoint Tests
# ============================================================================


class TestCreateAthleteEndpoint:
    """Tests for POST /athletes/ endpoint."""

    @pytest.mark.asyncio
    async def test_create_athlete_endpoint(self, client: AsyncClient):
        """Test creating an athlete via API returns 200 and expected fields."""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }

        response = await client.post("/athletes/", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == payload["email"]
        assert "status" in data
        assert data["status"] == "onboarding"  # Default status

    @pytest.mark.asyncio
    async def test_create_athlete_email_only(self, client: AsyncClient):
        """Test creating an athlete with email only (no password)."""
        payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        }

        response = await client.post("/athletes/", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["email"] == payload["email"]

    @pytest.mark.asyncio
    async def test_create_athlete_invalid_email(self, client: AsyncClient):
        """Test creating an athlete with invalid email returns 422."""
        payload = {
            "email": "not-an-email",
            "password": "securepassword123",
        }

        response = await client.post("/athletes/", json=payload)

        assert response.status_code == 422


class TestGetAthleteEndpoint:
    """Tests for GET /athletes/{athlete_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_athlete_endpoint(self, client: AsyncClient, test_db_session):
        """Test getting an athlete by ID returns 200 and nested profile."""
        # First create an athlete via the API
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        # Now get the athlete
        response = await client.get(f"/athletes/{athlete_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == athlete_id
        assert data["email"] == create_payload["email"]
        assert "status" in data

    @pytest.mark.asyncio
    async def test_get_athlete_endpoint_404(self, client: AsyncClient):
        """Test getting a nonexistent athlete returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/athletes/{fake_id}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Athlete not found"


class TestUpdateAthleteEndpoint:
    """Tests for PATCH /athletes/{athlete_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_athlete_endpoint(self, client: AsyncClient):
        """Test updating an athlete's status returns 200 and updated value."""
        # First create an athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        # Update the athlete's status
        update_payload = {"status": "inactive"}
        response = await client.patch(f"/athletes/{athlete_id}", json=update_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "inactive"

    @pytest.mark.asyncio
    async def test_update_athlete_endpoint_404(self, client: AsyncClient):
        """Test updating a nonexistent athlete returns 404."""
        fake_id = str(uuid.uuid4())
        update_payload = {"status": "inactive"}
        response = await client.patch(f"/athletes/{fake_id}", json=update_payload)

        assert response.status_code == 404
        assert response.json()["detail"] == "Athlete not found"


class TestUpsertProfileEndpoint:
    """Tests for PUT /athletes/{athlete_id}/profile endpoint."""

    @pytest.mark.asyncio
    async def test_upsert_profile_endpoint(self, client: AsyncClient):
        """Test creating/updating a profile returns 200 and profile data."""
        # First create an athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        # Create a profile
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
        response = await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == athlete_id
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"
        assert data["display_name"] == "johndoe"

    @pytest.mark.asyncio
    async def test_upsert_profile_update_existing(self, client: AsyncClient):
        """Test updating an existing profile returns 200 with updated values."""
        # Create athlete and profile
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        initial_profile = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=initial_profile)

        # Update the profile
        updated_profile = {
            "first_name": "Jane",
            "last_name": "Smith",
            "display_name": "janesmith",
        }
        response = await client.put(f"/athletes/{athlete_id}/profile", json=updated_profile)

        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "Jane"
        assert data["last_name"] == "Smith"
        assert data["display_name"] == "janesmith"


class TestGetProfileEndpoint:
    """Tests for GET /athletes/{athlete_id}/profile endpoint."""

    @pytest.mark.asyncio
    async def test_get_profile_endpoint(self, client: AsyncClient):
        """Test getting an athlete's profile returns 200."""
        # Create athlete and profile
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Get the profile
        response = await client.get(f"/athletes/{athlete_id}/profile")

        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == athlete_id
        assert data["first_name"] == "John"
        assert data["last_name"] == "Doe"

    @pytest.mark.asyncio
    async def test_get_profile_endpoint_404(self, client: AsyncClient):
        """Test getting profile for athlete without one returns 404."""
        # Create athlete without profile
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        # Try to get the profile
        response = await client.get(f"/athletes/{athlete_id}/profile")

        assert response.status_code == 404
        assert response.json()["detail"] == "Profile not found"


# ============================================================================
# Onboarding Endpoint Tests
# ============================================================================


class TestOnboardAthleteEndpoint:
    """Tests for POST /athletes/{athlete_id}/onboarding endpoint."""

    @pytest.mark.asyncio
    async def test_onboard_athlete_success(self, client: AsyncClient):
        """Test successful athlete onboarding."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active (required for onboarding)
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["onboarding_complete"] is True
        assert "preferences" in data
        assert "training_block" in data

    @pytest.mark.asyncio
    async def test_onboard_athlete_no_profile_returns_422(self, client: AsyncClient):
        """Test onboarding without profile returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        # Try to onboard without profile
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_invalid_status_returns_422(self, client: AsyncClient):
        """Test onboarding with invalid athlete status returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Keep status as "onboarding" (not active) - should fail
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_malformed_weekly_schedule(self, client: AsyncClient):
        """Test onboarding with malformed weekly_schedule (invalid day key) returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # Try onboarding with invalid day key
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_long_workout_on_unavailable_day(self, client: AsyncClient):
        """Test onboarding with long_workout=True on unavailable day returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # Try onboarding with long_workout on unavailable day
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_available_days_count_mismatch(self, client: AsyncClient):
        """Test onboarding with available_days_count mismatch returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # Try onboarding with mismatched available_days_count
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_missing_day_entries(self, client: AsyncClient):
        """Test onboarding with missing day entries returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # Try onboarding with missing days
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_not_found(self, client: AsyncClient):
        """Test onboarding with athlete not found returns 404."""
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
        response = await client.post(f"/athletes/{fake_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_onboard_athlete_inactive_status_returns_422(self, client: AsyncClient):
        """Test onboarding with inactive athlete status returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Set athlete to inactive
        await client.patch(f"/athletes/{athlete_id}", json={"status": "inactive"})

        # Try onboarding
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_suspended_status_returns_422(self, client: AsyncClient):
        """Test onboarding with suspended athlete status returns 422."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Set athlete to suspended
        await client.patch(f"/athletes/{athlete_id}", json={"status": "suspended"})

        # Try onboarding
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboard_athlete_response_includes_twin_state_null(self, client: AsyncClient):
        """Test onboarding response includes twin_state: null."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

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
                "goal_type": "race",
                "goal_event_type": "marathon",
            },
        }
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201
        data = response.json()
        assert "twin_state" in data
        assert data["twin_state"] is None

    @pytest.mark.asyncio
    async def test_onboard_athlete_valid_weekly_schedule_returns_201(self, client: AsyncClient):
        """Test onboarding with valid weekly_schedule containing all 7 days returns 201."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # Perform onboarding with valid weekly_schedule
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
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_onboard_athlete_already_onboarded_returns_409(self, client: AsyncClient):
        """Test re-onboarding returns 409 Conflict."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # First onboarding
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
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        # Try to onboard again
        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 409


class TestGetOnboardingStatusEndpoint:
    """Tests for GET /athletes/{athlete_id}/onboarding endpoint."""

    @pytest.mark.asyncio
    async def test_get_onboarding_status_not_onboarded(self, client: AsyncClient):
        """Test getting onboarding status before onboarding."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

        response = await client.get(f"/athletes/{athlete_id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is False
        assert data["preferences"] is None
        assert data["training_block"] is None

    @pytest.mark.asyncio
    async def test_get_onboarding_status_after_onboarding(self, client: AsyncClient):
        """Test getting onboarding status after successful onboarding."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

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
                "name": "Test Block",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "goal": "Test",
            },
        }
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        # Get onboarding status
        response = await client.get(f"/athletes/{athlete_id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["preferences"] is not None
        assert data["training_block"] is not None

    @pytest.mark.asyncio
    async def test_get_onboarding_status_404_for_nonexistent_athlete(self, client: AsyncClient):
        """Test getting onboarding status for nonexistent athlete returns 404."""
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/athletes/{fake_id}/onboarding")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_onboarding_status_returns_populated_preferences_and_training_block(self, client: AsyncClient):
        """Test returns preferences and training_block populated after onboarding."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

        # Perform onboarding
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
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        # Get onboarding status
        response = await client.get(f"/athletes/{athlete_id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["preferences"] is not None
        assert data["preferences"]["sport_background"] == "running_primary"
        assert data["training_block"] is not None
        assert data["training_block"]["goal_type"] == "race"

    @pytest.mark.asyncio
    async def test_get_onboarding_status_returns_twin_state_null(self, client: AsyncClient):
        """Test returns twin_state: null in status response."""
        # Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        athlete_id = create_response.json()["id"]

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
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

        # Update athlete status to active
        await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})

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
                "goal_type": "race",
            },
        }
        await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        # Get onboarding status
        response = await client.get(f"/athletes/{athlete_id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert "twin_state" in data
        assert data["twin_state"] is None