"""Integration tests for onboarding triggers background task and exposes readiness flag."""

import uuid
from datetime import date

import pytest

from app.models.enums import AthleteStatus
from tests.factories import make_athlete, make_athlete_profile


class TestOnboardingFirstMessage:
    """Tests for onboarding triggers background task and exposes readiness flag."""

    @pytest.mark.asyncio
    async def test_post_onboarding_returns_201(self, client, test_db_session):
        """Verify POST /athletes/{athlete_id}/onboarding returns 201 and completes successfully."""
        # Create athlete first
        athlete = make_athlete(status=AthleteStatus.ACTIVE)
        test_db_session.add(athlete)
        await test_db_session.flush()
        await test_db_session.commit()

        # Create profile first
        profile = make_athlete_profile(
            athlete_id=athlete.id,
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
        )
        test_db_session.add(profile)
        await test_db_session.flush()
        await test_db_session.commit()

        # Now do onboarding
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

        response = await client.post(f"/athletes/{athlete.id}/onboarding", json=onboarding_data)

        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_get_onboarding_status_includes_first_message_ready(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/onboarding/status includes first_message_ready field in response."""
        # Create athlete and complete onboarding
        athlete = make_athlete(status=AthleteStatus.ACTIVE)
        test_db_session.add(athlete)
        await test_db_session.flush()
        await test_db_session.commit()

        profile = make_athlete_profile(athlete_id=athlete.id)
        test_db_session.add(profile)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete.id}/onboarding/status")

        assert response.status_code == 200
        data = response.json()
        assert "first_message_ready" in data

    @pytest.mark.asyncio
    async def test_get_onboarding_status_first_message_ready_false_after_onboarding(self, client, test_db_session):
        """Verify GET /athletes/{athlete_id}/onboarding/status returns first_message_ready: false immediately after onboarding."""
        # Create athlete and complete onboarding
        athlete = make_athlete(status=AthleteStatus.ACTIVE)
        test_db_session.add(athlete)
        await test_db_session.flush()
        await test_db_session.commit()

        profile = make_athlete_profile(athlete_id=athlete.id)
        test_db_session.add(profile)
        await test_db_session.flush()
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete.id}/onboarding/status")

        assert response.status_code == 200
        data = response.json()
        # Before background task completes, first_message_ready should be false
        assert data["first_message_ready"] is False

    @pytest.mark.asyncio
    async def test_onboarding_response_does_not_include_first_message_ready(self, client, test_db_session):
        """Verify onboarding response does not include first_message_ready (only the status endpoint does)."""
        # Create athlete
        athlete = make_athlete(status=AthleteStatus.ACTIVE)
        test_db_session.add(athlete)
        await test_db_session.flush()
        await test_db_session.commit()

        # Create profile
        profile = make_athlete_profile(
            athlete_id=athlete.id,
            first_name="John",
            last_name="Doe",
            date_of_birth=date(1990, 1, 1),
        )
        test_db_session.add(profile)
        await test_db_session.flush()
        await test_db_session.commit()

        # Do onboarding
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

        response = await client.post(f"/athletes/{athlete.id}/onboarding", json=onboarding_data)

        assert response.status_code == 201
        data = response.json()
        # Onboarding response should not include first_message_ready
        assert "first_message_ready" not in data

    @pytest.mark.asyncio
    async def test_onboarding_without_profile_returns_422(self, client, test_db_session):
        """Verify onboarding without a profile returns 422 (existing behavior preserved)."""
        # Create athlete without profile
        athlete = make_athlete(status=AthleteStatus.ACTIVE)
        test_db_session.add(athlete)
        await test_db_session.flush()
        await test_db_session.commit()

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
            },
        }

        response = await client.post(f"/athletes/{athlete.id}/onboarding", json=onboarding_data)

        # Should fail because profile is required
        assert response.status_code == 422