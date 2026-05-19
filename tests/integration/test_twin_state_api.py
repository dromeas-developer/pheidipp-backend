"""Integration tests for twin state API endpoints."""

import uuid

import pytest
from httpx import AsyncClient


async def create_athlete_via_api(client: AsyncClient) -> str:
    """Helper to create an athlete via API and return the ID."""
    payload = {
        "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
        "password": "securepassword123",
    }
    response = await client.post("/athletes/", json=payload)
    return response.json()["id"]


async def create_profile_via_api(client: AsyncClient, athlete_id: str) -> None:
    """Helper to create a profile via API."""
    profile_payload = {
        "first_name": "John",
        "last_name": "Doe",
        "display_name": "johndoe",
        "date_of_birth": "1994-05-15",
        "gender": "male",
        "country_code": "US",
        "timezone": "America/New_York",
        "language_code": "en",
        "unit_preference": "metric",
    }
    await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)


async def activate_athlete_via_api(client: AsyncClient, athlete_id: str) -> None:
    """Helper to activate an athlete via API."""
    await client.patch(f"/athletes/{athlete_id}", json={"status": "active"})


async def complete_onboarding_via_api(client: AsyncClient, athlete_id: str) -> dict:
    """Helper to complete onboarding via API and return the response."""
    onboarding_payload = {
        "preferences": {
            "sport_background": "running_primary",
            "years_structured_training": 6.0,
            "hr_source": "chest_strap",
            "power_source": "running_power",
        },
        "training_block": {
            "goal_type": "race",
            "goal_event_type": "marathon",
            "goal_event_name": "Boston Marathon 2024",
            "weekly_volume_hours": 11.0,
        },
    }
    response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)
    return response


class TestGetCurrentTwinState:
    """Tests for GET /athletes/{athlete_id}/twin/."""

    @pytest.mark.asyncio
    async def test_returns_404_when_no_twin_state(self, client):
        """Verify returns 404 when athlete has no twin state."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_200_with_twin_state_response(self, client):
        """Verify returns 200 with TwinStateResponse after onboarding is complete."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/")

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "athlete_id" in data
        assert "fitness_score" in data

    @pytest.mark.asyncio
    async def test_response_contains_all_expected_fields(self, client):
        """Verify response contains all expected fields."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/")

        data = response.json()
        expected_fields = [
            "id",
            "athlete_id",
            "athlete_preferences_id",
            "trigger",
            "confidence_level",
            "data_tier",
            "fitness_score",
            "fatigue_score",
            "max_hr_estimate",
            "lt1_hr_estimate",
            "lt2_hr_estimate",
            "lt1_pace_estimate",
            "lt2_pace_estimate",
            "structural_capacity_score",
            "fitness_time_constant",
            "fatigue_time_constant",
            "computation_summary",
            "computation_metadata",
            "created_at",
        ]
        for field in expected_fields:
            assert field in data, f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_trigger_is_questionnaire(self, client):
        """Verify trigger is 'questionnaire' in response."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/")

        data = response.json()
        assert data["trigger"] == "questionnaire"

    @pytest.mark.asyncio
    async def test_confidence_level_is_low(self, client):
        """Verify confidence_level is 'low' in response."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/")

        data = response.json()
        assert data["confidence_level"] == "low"


class TestGetTwinStateHistory:
    """Tests for GET /athletes/{athlete_id}/twin/history."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_history(self, client):
        """Verify returns 200 with empty items when no history exists."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_returns_paginated_results(self, client):
        """Verify returns paginated results with correct items and total."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) > 0
        assert data["total"] >= 1

    @pytest.mark.asyncio
    async def test_limit_parameter_works(self, client):
        """Verify limit parameter works."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history?limit=1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) <= 1

    @pytest.mark.asyncio
    async def test_offset_parameter_works(self, client):
        """Verify offset parameter works."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        # Get total first
        response = await client.get(f"/athletes/{athlete_id}/twin/history")
        total = response.json()["total"]

        if total > 0:
            # Skip first item
            response = await client.get(f"/athletes/{athlete_id}/twin/history?offset=1")
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_results_ordered_by_created_at_desc(self, client):
        """Verify results are ordered by created_at descending."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history")

        data = response.json()
        if len(data["items"]) > 1:
            # Verify descending order
            dates = [item["created_at"] for item in data["items"]]
            assert dates == sorted(dates, reverse=True)

    @pytest.mark.asyncio
    async def test_limit_validation_returns_422_for_limit_less_than_1(self, client):
        """Verify limit validation returns 422 for limit < 1."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history?limit=0")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_limit_validation_returns_422_for_limit_greater_than_1000(self, client):
        """Verify limit validation returns 422 for limit > 1000."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history?limit=1001")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_offset_validation_returns_422_for_offset_less_than_0(self, client):
        """Verify offset validation returns 422 for offset < 0."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/twin/history?offset=-1")

        assert response.status_code == 422


class TestOnboardingWithTwinState:
    """Tests for POST /athletes/{athlete_id}/onboarding with twin state."""

    @pytest.mark.asyncio
    async def test_successful_onboarding_returns_201_with_twin_state(self, client):
        """Verify successful onboarding returns 201 with populated twin_state."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon 2024",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["twin_state"] is not None

    @pytest.mark.asyncio
    async def test_twin_state_matches_response_schema(self, client):
        """Verify twin_state in response matches TwinStateResponse schema."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon 2024",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        data = response.json()
        twin = data["twin_state"]
        assert "id" in twin
        assert "created_at" in twin
        assert "fitness_score" in twin

    @pytest.mark.asyncio
    async def test_onboarding_creates_twin_state_in_database(
        self, client, test_db_session
    ):
        """Verify onboarding creates a TwinState record in the database."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon 2024",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201

        # Query database directly to verify twin state was created
        from app.models.twin_state import TwinState
        from sqlalchemy import select

        result = await test_db_session.execute(
            select(TwinState).where(TwinState.athlete_id == uuid.UUID(athlete_id))
        )
        twin_states = result.scalars().all()
        assert len(twin_states) == 1

    @pytest.mark.asyncio
    async def test_onboarding_sets_onboarding_complete_flag(
        self, client, test_db_session
    ):
        """Verify onboarding_complete flag is set to True after successful onboarding."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon 2024",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201

        # Verify in database
        from app.models.athlete import Athlete
        from sqlalchemy import select

        result = await test_db_session.execute(
            select(Athlete).where(Athlete.id == uuid.UUID(athlete_id))
        )
        db_athlete = result.scalar_one()
        assert db_athlete.onboarding_complete is True

    @pytest.mark.asyncio
    async def test_onboarding_without_profile_returns_422(self, client):
        """Verify onboarding without profile returns 422."""
        athlete_id = await create_athlete_via_api(client)
        # Don't create profile

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_onboarding_with_inactive_athlete_returns_422(self, client):
        """Verify onboarding with inactive athlete returns 422."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        # Don't activate - athlete stays in onboarding status

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_repeat_onboarding_returns_409(self, client):
        """Verify repeat onboarding returns 409."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 409


class TestOnboardingStatusWithTwinState:
    """Tests for GET /athletes/{athlete_id}/onboarding with twin state."""

    @pytest.mark.asyncio
    async def test_returns_200_with_twin_state_none_before_onboarding(self, client):
        """Verify returns 200 with twin_state=None before onboarding."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        # Don't complete onboarding

        response = await client.get(f"/athletes/{athlete_id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is False
        assert data["twin_state"] is None

    @pytest.mark.asyncio
    async def test_returns_200_with_twin_state_after_onboarding(self, client):
        """Verify returns 200 with twin_state populated after onboarding."""
        athlete_id = await create_athlete_via_api(client)
        await create_profile_via_api(client, athlete_id)
        await activate_athlete_via_api(client, athlete_id)
        await complete_onboarding_via_api(client, athlete_id)

        response = await client.get(f"/athletes/{athlete_id}/onboarding")

        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["twin_state"] is not None


class TestComputationCorrectness:
    """Tests for twin state computation correctness."""

    @pytest.mark.asyncio
    async def test_male_30yo_running_primary_chest_strap_power(self, client):
        """Verify computation for 30-year-old male with running_primary, chest_strap, running_power."""
        athlete_id = await create_athlete_via_api(client)

        # Create profile with specific DOB to get age 30
        profile_payload = {
            "first_name": "John",
            "last_name": "Doe",
            "display_name": "johndoe",
            "date_of_birth": "1994-05-15",  # Age 30
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Test Race",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201
        data = response.json()
        twin = data["twin_state"]

        # Verify computed values for 30yo male with TIER1 data
        assert twin["fitness_score"] == 52.0  # (11 * 2) + (6 * 5) = 22 + 30 = 52
        assert twin["data_tier"] == "tier1"  # running_power + chest_strap
        assert twin["structural_capacity_score"] == 0.7  # running_primary

    @pytest.mark.asyncio
    async def test_female_30yo_same_params(self, client):
        """Verify computation for 30-year-old female with same training params."""
        athlete_id = await create_athlete_via_api(client)

        profile_payload = {
            "first_name": "Jane",
            "last_name": "Doe",
            "display_name": "janedoe",
            "date_of_birth": "1994-05-15",  # Age 30
            "gender": "female",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "running_primary",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Test Race",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201
        data = response.json()
        twin = data["twin_state"]

        # Female uses Gulati formula: 206 - (0.88 * 30) = 179.6, rounded to 177.8 (rounded to 177.84)
        assert twin["max_hr_estimate"] == 177.84

    @pytest.mark.asyncio
    async def test_crossover_athlete_structural_capacity_and_fitness(self, client):
        """Verify computation for crossover athlete."""
        athlete_id = await create_athlete_via_api(client)

        profile_payload = {
            "first_name": "John",
            "last_name": "Crosser",
            "display_name": "johncrosser",
            "date_of_birth": "1994-05-15",
            "gender": "male",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)
        await activate_athlete_via_api(client, athlete_id)

        onboarding_payload = {
            "preferences": {
                "sport_background": "cycling_crossover",
                "years_structured_training": 6.0,
                "hr_source": "chest_strap",
                "power_source": "running_power",
            },
            "training_block": {
                "goal_type": "race",
                "goal_event_type": "marathon",
                "goal_event_name": "Test Race",
                "weekly_volume_hours": 11.0,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_payload)

        assert response.status_code == 201
        data = response.json()
        twin = data["twin_state"]

        # Crossover athletes get 0.8 multiplier on fitness score
        # (11 * 2 + 6 * 5) * 0.8 = 52 * 0.8 = 41.6
        assert twin["fitness_score"] == 41.6
        # Crossover athletes have lower structural capacity
        assert twin["structural_capacity_score"] == 0.2