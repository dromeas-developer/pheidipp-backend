"""Integration tests for onboarding triggers background task and exposes readiness flag."""

import uuid
from datetime import date

import pytest

from app.models.enums import AthleteStatus


class TestOnboardingFirstMessage:
    """Tests for onboarding triggers background task and exposes readiness flag."""

    @pytest.mark.asyncio
    async def test_post_onboarding_returns_201(self, client, registered_athlete: dict):
        """Verify POST /athletes/{athlete_id}/onboarding returns 201 and completes successfully."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile first
        profile_payload = {
            "first_name": "John", "last_name": "Doe", "display_name": "johndoe",
            "date_of_birth": "1990-01-01", "gender": "male",
            "country_code": "US", "timezone": "America/New_York",
            "language_code": "en", "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_data = {
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
                "goal_event_name": "Boston Marathon 2024",
                "goal_event_date": "2024-04-15",
                "goal_description": "Prepare for Boston Marathon",
                "custom_distance_km": 42.195,
                "weekly_volume_hours": 10.0,
                "weekly_volume_km": 80.0,
                "fitness_level": 3,
                "recent_injury": False,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_data, headers=headers)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_get_onboarding_status_includes_first_message_ready(self, client, registered_athlete: dict):
        """Verify GET /athletes/{athlete_id}/onboarding/status includes first_message_ready field in response."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/onboarding/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert "first_message_ready" in data

    @pytest.mark.asyncio
    async def test_get_onboarding_status_first_message_ready_false_after_onboarding(self, client, registered_athlete: dict):
        """Verify GET /athletes/{athlete_id}/onboarding/status returns first_message_ready: false immediately after onboarding."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        response = await client.get(f"/athletes/{athlete_id}/onboarding/status", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["first_message_ready"] is False

    @pytest.mark.asyncio
    async def test_onboarding_response_does_not_include_first_message_ready(self, client, registered_athlete: dict):
        """Verify onboarding response does not include first_message_ready (only the status endpoint does)."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile
        profile_payload = {
            "first_name": "John", "last_name": "Doe", "display_name": "johndoe",
            "date_of_birth": "1990-01-01", "gender": "male",
            "country_code": "US", "timezone": "America/New_York",
            "language_code": "en", "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers)

        onboarding_data = {
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
                "goal_event_name": "Boston Marathon 2024",
                "goal_event_date": "2024-04-15",
                "goal_description": "Prepare for Boston Marathon",
                "custom_distance_km": 42.195,
                "weekly_volume_hours": 10.0,
                "weekly_volume_km": 80.0,
                "fitness_level": 3,
                "recent_injury": False,
            },
        }

        response = await client.post(f"/athletes/{athlete_id}/onboarding", json=onboarding_data, headers=headers)

        assert response.status_code == 201
        data = response.json()
        # Onboarding response should not include first_message_ready
        assert "first_message_ready" not in data
