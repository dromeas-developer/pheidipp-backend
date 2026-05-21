"""Integration tests for workflow and cross-service interactions.

These tests verify multi-service athlete lifecycle, transactional consistency,
and data integrity across related services.
"""

import uuid
import time
import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import AthleteStatus, SessionType, TrainingPlanStatus
from app.repositories.athlete_repository import AthleteRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from tests.factories import (
    make_training_plan,
    make_planned_session,
)


@pytest.fixture
async def test_athlete(test_db_session: AsyncSession) -> Athlete:
    """Create a test athlete in the database for testing."""
    athlete_repo = AthleteRepository(test_db_session)
    athlete = await athlete_repo.create(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
    )
    return athlete


class TestAthleteLifecycleWorkflow:
    """Tests for complete athlete lifecycle workflow across multiple services."""

    @pytest.mark.asyncio
    async def test_athlete_full_lifecycle_creates_all_related_resources(
        self, client: AsyncClient
    ):
        """Test that the full athlete lifecycle creates all related resources correctly."""
        # Step 1: Create athlete
        create_payload = {
            "email": f"test_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        assert create_response.status_code == 200
        athlete_id = create_response.json()["id"]

        # Step 2: Create profile
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
            json=profile_payload
        )
        assert profile_response.status_code == 200
        profile_data = profile_response.json()
        assert profile_data["athlete_id"] == athlete_id
        assert profile_data["first_name"] == "John"

        # Step 3: Update athlete status to active
        update_response = await client.patch(
            f"/athletes/{athlete_id}",
            json={"status": "active"}
        )
        assert update_response.status_code == 200
        assert update_response.json()["status"] == "active"

        # Step 4: Complete onboarding
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
            json=onboarding_payload
        )
        assert onboard_response.status_code == 201
        onboard_data = onboard_response.json()
        assert onboard_data["onboarding_complete"] is True
        assert "preferences" in onboard_data
        assert "training_block" in onboard_data

        # Step 5: Verify final athlete state
        get_response = await client.get(f"/athletes/{athlete_id}")
        assert get_response.status_code == 200
        final_data = get_response.json()
        assert final_data["status"] == "active"
        assert final_data["onboarding_complete"] is True


class TestActivityAndWellnessCoexistence:
    """Tests for activity and wellness data coexisting for the same athlete."""

    @pytest.mark.asyncio
    async def test_activity_and_wellness_coexist_independently(
        self, client: AsyncClient, test_athlete: Athlete
    ):
        """Test that activity and wellness records coexist independently for the same athlete."""
        athlete_id = str(test_athlete.id)

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
        activity_response = await client.post("/activities/", json=activity_payload)
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
        wellness_response = await client.post("/wellness/", json=wellness_payload)
        assert wellness_response.status_code == 201
        wellness_data = wellness_response.json()
        assert wellness_data["athlete_id"] == athlete_id
        assert wellness_data["sleep_total"] == 480

        # Verify both are independently retrievable
        activity_get = await client.get(f"/activities/{activity_data['id']}")
        assert activity_get.status_code == 200
        assert activity_get.json()["title"] == "Morning Long Run"

        wellness_get = await client.get(f"/wellness/{wellness_data['id']}")
        assert wellness_get.status_code == 200
        assert wellness_get.json()["sleep_total"] == 480

        # Verify no cross-contamination - each resource has the correct athlete_id
        assert activity_get.json()["athlete_id"] == wellness_get.json()["athlete_id"] == athlete_id

        # List activities and wellness for the athlete
        activities_list = await client.get(f"/athletes/{athlete_id}/activities")
        assert activities_list.status_code == 200
        assert len(activities_list.json()["items"]) == 1

        wellness_list = await client.get(f"/athletes/{athlete_id}/wellness")
        assert wellness_list.status_code == 200
        assert len(wellness_list.json()["items"]) == 1


class TestFitnessAndWellnessSameDay:
    """Tests for fitness and wellness records coexisting on the same date."""

    @pytest.mark.asyncio
    async def test_fitness_and_wellness_same_date_independent(
        self, client: AsyncClient, test_athlete: Athlete
    ):
        """Test that fitness and wellness records for the same date are independent domains."""
        athlete_id = str(test_athlete.id)
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
        fitness_response = await client.post("/fitness/", json=fitness_payload)
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
        wellness_response = await client.post("/wellness/", json=wellness_payload)
        assert wellness_response.status_code == 201
        wellness_data = wellness_response.json()
        assert wellness_data["athlete_id"] == athlete_id
        assert wellness_data["metric_date"] == target_date
        assert wellness_data["sleep_total"] == 450

        # Verify both records exist and are retrievable
        fitness_get = await client.get(f"/fitness/{fitness_data['id']}")
        assert fitness_get.status_code == 200
        assert fitness_get.json()["tss"] == 85.0

        wellness_get = await client.get(f"/wellness/{wellness_data['id']}")
        assert wellness_get.status_code == 200
        assert wellness_get.json()["sleep_total"] == 450

        # Verify they don't interfere with each other
        assert fitness_get.json()["id"] == fitness_data["id"]
        assert wellness_get.json()["id"] == wellness_data["id"]

        # Both should be present in their respective lists
        fitness_list = await client.get(f"/athletes/{athlete_id}/fitness")
        assert fitness_list.status_code == 200
        assert len(fitness_list.json()["items"]) == 1

        wellness_list = await client.get(f"/athletes/{athlete_id}/wellness")
        assert wellness_list.status_code == 200
        assert len(wellness_list.json()["items"]) == 1


class TestTrainingPlanWorkflow:
    """Workflow tests for training plan generation, retrieval, and archival."""

    @pytest.mark.asyncio
    async def test_onboarding_triggers_plan_generation(
        self, client: AsyncClient
    ):
        """Full onboarding-to-plan-generation workflow via HTTP."""
        # Create athlete
        create_payload = {
            "email": f"workflow_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        assert create_response.status_code == 200
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
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload
        )
        # Accept both 200 and 201
        assert onboard_response.status_code in (200, 201)

        # Poll until plan is available or timeout
        plan = None
        for _ in range(60):  # 60 retries × 1s = 60s timeout
            await asyncio.sleep(1)
            resp = await client.get(f"/athletes/{athlete_id}/training-plans/active")
            if resp.status_code == 200:
                plan = resp.json()
                break

        assert plan is not None, "Plan was not generated within timeout"
        assert plan["training_plan"]["status"] == "active"
        assert len(plan["planned_sessions"]) > 0
        assert "methodology_profile" in plan["training_plan"] or "generation_metadata" in plan["training_plan"]

        # Verify planned sessions have correct structure
        session = plan["planned_sessions"][0]
        assert session["session_type"] is not None
        assert session["dominant_physiological_intent"] is not None
        assert session["week_number"] is not None
        assert session["phase"] is not None

    @pytest.mark.asyncio
    async def test_plan_retrieval_and_archival_workflow(
        self, client: AsyncClient, test_db_session: AsyncSession
    ):
        """Plan retrieval and archival workflow."""
        # Create athlete and plan via DB
        create_payload = {
            "email": f"archival_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        assert create_response.status_code == 200
        athlete_id = create_response.json()["id"]

        # Insert plan directly via DB
        plan = make_training_plan(athlete_id=uuid.UUID(athlete_id))
        test_db_session.add(plan)
        await test_db_session.commit()
        plan_id = plan.id

        # Retrieve active plan
        resp = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert resp.status_code == 200
        data = resp.json()
        assert data["training_plan"]["id"] == str(plan_id)

        # Retrieve by ID
        resp2 = await client.get(f"/athletes/{athlete_id}/training-plans/{plan_id}")
        assert resp2.status_code == 200

        # Archive the plan via DB update
        repo = TrainingPlanRepository(test_db_session)
        archived = await repo.archive_plan(plan_id)
        await test_db_session.commit()
        assert archived.status == TrainingPlanStatus.ARCHIVED

        # Active plan should now return 404
        resp3 = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert resp3.status_code == 404

        # Create new plan for same athlete
        new_plan = make_training_plan(athlete_id=uuid.UUID(athlete_id))
        test_db_session.add(new_plan)
        await test_db_session.commit()

        # Active plan should now return the new plan
        resp4 = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert resp4.status_code == 200
        assert resp4.json()["training_plan"]["id"] == str(new_plan.id)

    @pytest.mark.asyncio
    async def test_plan_generation_idempotency(
        self, client: AsyncClient
    ):
        """Triggering plan generation twice does not create duplicate active plans."""
        # Create athlete
        create_payload = {
            "email": f"idempotency_{uuid.uuid4().hex[:8]}@example.com",
            "password": "securepassword123",
        }
        create_response = await client.post("/athletes/", json=create_payload)
        assert create_response.status_code == 200
        athlete_id = create_response.json()["id"]

        # Create profile
        profile_payload = {
            "first_name": "Jane",
            "last_name": "Runner",
            "display_name": "janerunner",
            "date_of_birth": "1992-05-01",
            "gender": "female",
            "country_code": "US",
            "timezone": "America/New_York",
            "language_code": "en",
            "unit_preference": "metric",
        }
        await client.put(f"/athletes/{athlete_id}/profile", json=profile_payload)

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
                "name": "5K Build",
                "start_date": "2024-01-01",
                "end_date": "2024-03-31",
                "goal_event_type": "5k",
            },
        }
        onboard_response = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload
        )
        assert onboard_response.status_code in (200, 201)

        # Wait for plan
        first_plan = None
        for _ in range(60):
            await asyncio.sleep(1)
            resp = await client.get(f"/athletes/{athlete_id}/training-plans/active")
            if resp.status_code == 200:
                first_plan = resp.json()
                break

        assert first_plan is not None
        first_plan_id = first_plan["training_plan"]["id"]

        # Complete onboarding a second time
        onboard_response2 = await client.post(
            f"/athletes/{athlete_id}/onboarding",
            json=onboarding_payload
        )
        # Should accept second onboarding
        assert onboard_response2.status_code in (200, 201)

        # Only one active plan should exist
        resp = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert resp.status_code == 200
        current_plan = resp.json()
        # Plan ID should be the same as the first generation
        assert current_plan["training_plan"]["id"] == first_plan_id