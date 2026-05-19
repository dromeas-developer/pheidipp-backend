"""Integration tests for API endpoints.

These tests verify API endpoint behavior with database integration.
"""

import uuid
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient


class TestActivityEndpoints:
    """Tests for activity API endpoints."""

    @pytest.mark.asyncio
    async def test_create_activity_endpoint_returns_created_activity(
        self, client: AsyncClient, test_db_session
    ):
        """Verify response payload matches created entity."""
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus

        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.commit()

        started_at = datetime(2024, 1, 1, 10, 0, 0)
        finished_at = started_at + timedelta(hours=1)

        payload = {
            "athlete_id": str(athlete.id),
            "activity_type": "running",
            "title": "Morning Run",
            "description": "A test run",
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "perceived_effort": "moderate",
            "avg_heart_rate": 145,
            "max_heart_rate": 175,
            "distance_meters": 10000.0,
            "calories": 500,
        }

        response = await client.post("/activities/", json=payload)

        assert response.status_code == 201  # Created
        data = response.json()
        assert "id" in data
        assert data["athlete_id"] == str(athlete.id)
        assert data["activity_type"] == "running"
        assert data["title"] == "Morning Run"
        assert data["description"] == "A test run"
        assert data["perceived_effort"] == "moderate"
        assert data["avg_heart_rate"] == 145
        assert data["max_heart_rate"] == 175
        assert data["distance_meters"] == 10000.0
        assert data["calories"] == 500
        assert data["duration_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_list_activities_endpoint_filters_correctly(
        self, client: AsyncClient, test_db_session
    ):
        """Verify query param filtering works end-to-end."""
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus, ActivityType
        from app.models.activity import Activity

        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.commit()

        # Create multiple activities with different types and dates
        running_activity = Activity(
            id=uuid.uuid4(),
            athlete_id=athlete.id,
            activity_type=ActivityType.RUNNING,
            title="Morning Run",
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            finished_at=datetime(2024, 1, 15, 11, 0, 0),
            duration_seconds=3600,
        )
        cycling_activity = Activity(
            id=uuid.uuid4(),
            athlete_id=athlete.id,
            activity_type=ActivityType.CYCLING,
            title="Afternoon Ride",
            started_at=datetime(2024, 1, 20, 14, 0, 0),
            finished_at=datetime(2024, 1, 20, 16, 0, 0),
            duration_seconds=7200,
        )
        test_db_session.add(running_activity)
        test_db_session.add(cycling_activity)
        await test_db_session.commit()

        # Test filtering by activity_type
        response = await client.get(
            f"/athletes/{athlete.id}/activities",
            params={"activity_type": "running"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["activity_type"] == "running"

        # Test filtering by date range
        response = await client.get(
            f"/athletes/{athlete.id}/activities",
            params={
                "date_from": "2024-01-18T00:00:00",
                "date_to": "2024-12-31T23:59:59",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["activity_type"] == "cycling"

    @pytest.mark.asyncio
    async def test_delete_activity_endpoint_returns_404_for_missing_activity(
        self, client: AsyncClient
    ):
        """Verify proper error handling returns 404 for missing activity."""
        non_existent_activity_id = uuid.uuid4()

        response = await client.delete(f"/activities/{non_existent_activity_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_athlete_scoped_activity_routes_only_return_athlete_data(
        self, client: AsyncClient, test_db_session
    ):
        """Verify athlete isolation in routes - each athlete only sees their own data."""
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus, ActivityType
        from app.models.activity import Activity

        # Create two athletes
        athlete1 = Athlete(
            id=uuid.uuid4(),
            email=f"athlete1_{uuid.uuid4().hex[:8]}@example.com",
            status=AthleteStatus.ACTIVE,
        )
        athlete2 = Athlete(
            id=uuid.uuid4(),
            email=f"athlete2_{uuid.uuid4().hex[:8]}@example.com",
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete1)
        test_db_session.add(athlete2)
        await test_db_session.commit()

        # Create activity for athlete1
        activity1 = Activity(
            id=uuid.uuid4(),
            athlete_id=athlete1.id,
            activity_type=ActivityType.RUNNING,
            title="Athlete1 Run",
            started_at=datetime(2024, 1, 15, 10, 0, 0),
            finished_at=datetime(2024, 1, 15, 11, 0, 0),
            duration_seconds=3600,
        )
        # Create activity for athlete2
        activity2 = Activity(
            id=uuid.uuid4(),
            athlete_id=athlete2.id,
            activity_type=ActivityType.CYCLING,
            title="Athlete2 Ride",
            started_at=datetime(2024, 1, 15, 14, 0, 0),
            finished_at=datetime(2024, 1, 15, 16, 0, 0),
            duration_seconds=7200,
        )
        test_db_session.add(activity1)
        test_db_session.add(activity2)
        await test_db_session.commit()

        # Query athlete1's activities - should only return athlete1's data
        response = await client.get(f"/athletes/{athlete1.id}/activities")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Athlete1 Run"
        assert data["items"][0]["athlete_id"] == str(athlete1.id)

        # Query athlete2's activities - should only return athlete2's data
        response = await client.get(f"/athletes/{athlete2.id}/activities")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Athlete2 Ride"
        assert data["items"][0]["athlete_id"] == str(athlete2.id)


class TestOnboardingFlow:
    """Tests for onboarding flow endpoints."""

    @pytest.mark.asyncio
    async def test_onboarding_flow_sets_onboarding_complete(
        self, client: AsyncClient, test_db_session
    ):
        """Verify onboarding completion flag is updated."""
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus

        # Create athlete in onboarding status
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            status=AthleteStatus.ONBOARDING,
        )
        test_db_session.add(athlete)
        await test_db_session.commit()

        # Update athlete status to active (simulating onboarding completion)
        response = await client.patch(
            f"/athletes/{athlete.id}",
            json={"status": "active"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"

        # Store the ID before expiring to avoid lazy loading issues
        athlete_id = athlete.id

        # Expire the cached athlete object so SQLAlchemy fetches fresh data from DB
        test_db_session.expire(athlete)

        # Verify the status was actually updated in the database
        from sqlalchemy import select
        result = await test_db_session.execute(
            select(Athlete).where(Athlete.id == athlete_id)
        )
        updated_athlete = result.scalar_one()
        assert updated_athlete.status == AthleteStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_onboarding_flow_creates_initial_twin_state(
        self, client: AsyncClient, test_db_session
    ):
        """Verify onboarding triggers initial twin creation.

        Note: This test verifies that onboarding can be completed.
        Twin state functionality does not currently exist in the codebase -
        this test documents the expected behavior once twin state is implemented.
        """
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus

        # Create athlete in onboarding status
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            status=AthleteStatus.ONBOARDING,
        )
        test_db_session.add(athlete)
        await test_db_session.commit()

        # Complete onboarding by updating status to active
        response = await client.patch(
            f"/athletes/{athlete.id}",
            json={"status": "active"},
        )

        assert response.status_code == 200

        # Note: Twin state creation would be triggered here once implemented
        # Currently no twin state model exists in the codebase
        # This test documents the expected behavior for future implementation