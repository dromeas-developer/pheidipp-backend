"""Integration tests for workflow and cross-service interactions.

These tests verify multi-service athlete lifecycle, transactional consistency,
and data integrity across related services.
"""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import AthleteStatus, TrainingPlanStatus
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.tasks.plan_generation_task import _generate_plan
from tests.factories import (
    make_training_plan,
)


class TestAthleteLifecycleWorkflow:
    """Tests for complete athlete lifecycle workflow across multiple services."""

    @pytest.mark.asyncio
    async def test_athlete_full_lifecycle_creates_all_related_resources(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test that the full athlete lifecycle creates all related resources correctly."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Step 1: Create profile
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
            f"/athletes/{athlete_id}/profile", json=profile_payload, headers=headers
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["athlete_id"] == athlete_id
        assert profile_data["first_name"] == "John"

        # Step 2: Complete onboarding
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
            f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers
        )
        assert onboard_response.status_code == 201
        onboard_data = onboard_response.json()
        assert onboard_data["onboarding_complete"] is True
        assert "preferences" in onboard_data
        assert "training_block" in onboard_data

        # Step 3: Verify final athlete state
        get_response = await client.get(f"/athletes/{athlete_id}", headers=headers)
        assert get_response.status_code == 200
        final_data = get_response.json()
        assert final_data["status"] == "active"
        assert final_data["onboarding_complete"] is True


class TestActivityAndWellnessCoexistence:
    """Tests for activity and wellness data coexisting for the same athlete."""

    @pytest.mark.asyncio
    async def test_activity_and_wellness_coexist_independently(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test that activity and wellness records coexist independently for the same athlete."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]

        # Create an activity
        activity_payload = {
            "athlete_id": athlete_id,
            "activity_type": "running",
            "title": "Morning Long Run",
            "started_at": "2024-01-15T08:00:00",
            "finished_at": "2024-01-15T10:30:00",
            "perceived_effort": "hard",
            "avg_heart_rate": 155,
            "distance_meters": 15000.0,
        }
        activity_response = await client.post("/activities/", json=activity_payload, headers=headers)
        assert activity_response.status_code == 201
        activity_data = activity_response.json()
        assert activity_data["athlete_id"] == athlete_id
        assert activity_data["title"] == "Morning Long Run"

        # Create a wellness record for the same athlete
        wellness_payload = {
            "athlete_id": athlete_id,
            "metric_date": "2024-01-15",
            "sleep_total": 480,
            "sleep_light": 240,
            "sleep_deep": 120,
            "sleep_rem": 90,
            "sleep_awake": 30,
            "resting_hr": 52,
            "hrv": 70,
            "weight": 75.5,
            "source": "manual",
            "timezone": "UTC",
        }
        wellness_response = await client.post("/wellness/", json=wellness_payload, headers=headers)
        assert wellness_response.status_code == 201
        wellness_data = wellness_response.json()
        assert wellness_data["athlete_id"] == athlete_id
        assert wellness_data["sleep_total"] == 480

        # Verify both are independently retrievable
        activity_get = await client.get(f"/activities/{activity_data['id']}", headers=headers)
        assert activity_get.status_code == 200
        assert activity_get.json()["title"] == "Morning Long Run"

        wellness_get = await client.get(f"/wellness/{wellness_data['id']}", headers=headers)
        assert wellness_get.status_code == 200
        assert wellness_get.json()["sleep_total"] == 480

        assert activity_get.json()["athlete_id"] == wellness_get.json()["athlete_id"] == athlete_id

        activities_list = await client.get(f"/athletes/{athlete_id}/activities", headers=headers)
        assert activities_list.status_code == 200
        assert len(activities_list.json()["items"]) == 1

        wellness_list = await client.get(f"/athletes/{athlete_id}/wellness", headers=headers)
        assert wellness_list.status_code == 200
        assert len(wellness_list.json()["items"]) == 1


class TestFitnessAndWellnessSameDay:
    """Tests for fitness and wellness records coexisting on the same date."""

    @pytest.mark.asyncio
    async def test_fitness_and_wellness_same_date_independent(
        self, client: AsyncClient, registered_athlete: dict
    ):
        """Test that fitness and wellness records for the same date are independent domains."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]
        target_date = "2024-01-15"

        # Create fitness record for date 2024-01-15
        fitness_payload = {
            "athlete_id": athlete_id,
            "metric_date": target_date,
            "tss": 85.0,
            "atl": 45.0,
            "ctl": 70.0,
            "tsb": 25.0,
        }
        fitness_response = await client.post("/fitness/", json=fitness_payload, headers=headers)
        assert fitness_response.status_code == 201
        fitness_data = fitness_response.json()
        assert fitness_data["athlete_id"] == athlete_id
        assert fitness_data["metric_date"] == target_date
        assert fitness_data["tss"] == 85.0

        # Create wellness record for same date 2024-01-15
        wellness_payload = {
            "athlete_id": athlete_id,
            "metric_date": target_date,
            "sleep_total": 450,
            "resting_hr": 58,
            "hrv": 62,
            "source": "manual",
            "timezone": "UTC",
        }
        wellness_response = await client.post("/wellness/", json=wellness_payload, headers=headers)
        assert wellness_response.status_code == 201
        wellness_data = wellness_response.json()
        assert wellness_data["athlete_id"] == athlete_id
        assert wellness_data["metric_date"] == target_date
        assert wellness_data["sleep_total"] == 450

        fitness_get = await client.get(f"/fitness/{fitness_data['id']}", headers=headers)
        assert fitness_get.status_code == 200
        assert fitness_get.json()["tss"] == 85.0

        wellness_get = await client.get(f"/wellness/{wellness_data['id']}", headers=headers)
        assert wellness_get.status_code == 200
        assert wellness_get.json()["sleep_total"] == 450

        assert fitness_get.json()["id"] == fitness_data["id"]
        assert wellness_get.json()["id"] == wellness_data["id"]

        fitness_list = await client.get(f"/athletes/{athlete_id}/fitness", headers=headers)
        assert fitness_list.status_code == 200
        assert len(fitness_list.json()["items"]) == 1

        wellness_list = await client.get(f"/athletes/{athlete_id}/wellness", headers=headers)
        assert wellness_list.status_code == 200
        assert len(wellness_list.json()["items"]) == 1


class TestTrainingPlanWorkflow:
    """Workflow tests for training plan generation, retrieval, and archival."""

    @pytest.mark.asyncio
    async def test_onboarding_triggers_plan_generation(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        """Full onboarding-to-plan-generation workflow via HTTP."""
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
                "name": "Marathon Build",
                "start_date": "2024-01-01",
                "end_date": "2024-04-30",
                "goal_event_type": "marathon",
                "goal_event_name": "Boston Marathon",
                "goal_event_date": "2024-04-15",
            },
        }
        onboard_response = await client.post(
            f"/athletes/{athlete_id}/onboarding", json=onboarding_payload, headers=headers
        )
        assert onboard_response.status_code in (200, 201)

        # Generate training plan using real LLM via Litellm
        from app.models.athlete import Athlete as AthleteModel
        from app.models.athlete_profile import AthleteProfile as AthleteProfileModel

        athlete_id_uuid = uuid.UUID(athlete_id)
        athlete_obj = await test_db_session.get(AthleteModel, athlete_id_uuid)
        await test_db_session.refresh(athlete_obj, ["profile"])

        await _generate_plan(athlete_id=athlete_id_uuid, session=test_db_session)

        # Plan should be immediately available
        resp = await client.get(f"/athletes/{athlete_id}/training-plans/active", headers=headers)
        assert resp.status_code == 200
        plan_resp = resp.json()
        assert plan_resp["training_plan"]["status"] == "active"
        assert len(plan_resp["planned_sessions"]) > 0

        session = plan_resp["planned_sessions"][0]
        assert session["session_type"] is not None
        assert session["dominant_physiological_intent"] is not None
        assert session["week_number"] is not None
        assert session["phase"] is not None

    @pytest.mark.asyncio
    async def test_plan_retrieval_and_archival_workflow(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        """Plan retrieval and archival workflow."""
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]
        athlete_id_uuid = uuid.UUID(athlete_id)

        # Insert plan directly via DB
        plan = make_training_plan(athlete_id=athlete_id_uuid)
        test_db_session.add(plan)
        await test_db_session.commit()
        plan_id = plan.id

        # Retrieve active plan
        resp = await client.get(f"/athletes/{athlete_id}/training-plans/active", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_plan"]["id"] == str(plan_id)

        # Retrieve by ID
        resp2 = await client.get(f"/athletes/{athlete_id}/training-plans/{plan_id}", headers=headers)
        assert resp2.status_code == 200

        # Archive the plan via DB update
        repo = TrainingPlanRepository(test_db_session)
        archived = await repo.archive_plan(plan_id)
        await test_db_session.commit()
        assert archived.status == TrainingPlanStatus.ARCHIVED

        # Active plan should now return 404
        resp3 = await client.get(f"/athletes/{athlete_id}/training-plans/active", headers=headers)
        assert resp3.status_code == 404
