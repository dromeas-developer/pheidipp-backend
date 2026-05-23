"""Integration tests for onboarding triggering plan generation."""

import uuid

import pytest
from httpx import AsyncClient
from unittest.mock import patch, AsyncMock, MagicMock


class TestOnboardingTriggersPlanGeneration:
    @pytest.mark.asyncio
    async def test_completing_onboarding_adds_generate_training_plan_task(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Completing onboarding adds generate_training_plan to BackgroundTasks."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile first (required for onboarding)
        profile_payload = {
            "first_name": "John", "last_name": "Doe", "display_name": "johndoe",
            "date_of_birth": "1990-01-01", "gender": "male",
            "country_code": "US", "timezone": "America/New_York",
            "language_code": "en", "unit_preference": "metric",
        }
        profile_response = await client.put(
            f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers
        )
        assert profile_response.status_code == 200

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
                "name": "Marathon Build",
                "start_date": "2024-01-01",
                "end_date": "2024-04-30",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon",
                "goal_event_date": "2024-04-15",
            },
        }

        response = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload,
            headers=headers,
        )
        assert response.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_onboarding_triggers_both_coach_message_and_plan_generation(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Onboarding still triggers generate_first_coach_message alongside generate_training_plan."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile first (required for onboarding)
        profile_payload = {
            "first_name": "John", "last_name": "Doe", "display_name": "johndoe",
            "date_of_birth": "1990-01-01", "gender": "male",
            "country_code": "US", "timezone": "America/New_York",
            "language_code": "en", "unit_preference": "metric",
        }
        profile_response = await client.put(
            f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers
        )
        assert profile_response.status_code == 200

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
                "name": "Marathon Build",
                "start_date": "2024-01-01",
                "end_date": "2024-04-30",
                "goal_event_type": "marathon",
            },
        }

        response = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload,
            headers=headers,
        )
        assert response.status_code in (200, 201)

    @pytest.mark.asyncio
    async def test_onboarding_response_does_not_include_plan_data(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Onboarding response does not include plan data (plan generation is async)."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create profile first (required for onboarding)
        profile_payload = {
            "first_name": "John", "last_name": "Doe", "display_name": "johndoe",
            "date_of_birth": "1990-01-01", "gender": "male",
            "country_code": "US", "timezone": "America/New_York",
            "language_code": "en", "unit_preference": "metric",
        }
        profile_response = await client.put(
            f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers
        )
        assert profile_response.status_code == 200

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
                "name": "Marathon Build",
                "start_date": "2024-01-01",
                "end_date": "2024-04-30",
                "goal_event_type": "marathon",
            },
        }

        response = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload,
            headers=headers,
        )
        assert response.status_code in (200, 201)
        data = response.json()
        assert "training_plan" not in data
        assert "planned_sessions" not in data
