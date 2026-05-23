"""Integration tests for Athlete Preferences API endpoints."""

import uuid

import pytest
from httpx import AsyncClient


class TestGetPreferencesEndpoint:
    """Tests for GET /athlete-preferences/{preferences_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_preferences_returns_200(self, client: AsyncClient, registered_athlete: dict, test_db_session):
        """Test getting preferences returns 200 with preferences data when found."""
        from tests.factories.athlete_preferences_factory import make_athlete_preferences_full

        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]

        prefs = make_athlete_preferences_full(athlete_id=athlete_id)
        test_db_session.add(prefs)
        await test_db_session.commit()
        await test_db_session.refresh(prefs)

        response = await client.get(f"/athlete-preferences/{prefs.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(prefs.id)
        assert data["athlete_id"] == str(athlete_id)
        assert data["sport_background"] == "running_primary"

    @pytest.mark.asyncio
    async def test_get_preferences_returns_404(self, client: AsyncClient, registered_athlete: dict):
        """Test getting nonexistent preferences returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        response = await client.get(f"/athlete-preferences/{fake_id}", headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Preferences not found"


class TestUpdatePreferencesEndpoint:
    """Tests for PATCH /athlete-preferences/{preferences_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_preferences_returns_200(self, client: AsyncClient, registered_athlete: dict, test_db_session):
        """Test updating preferences returns 200 with updated data."""
        from tests.factories.athlete_preferences_factory import make_athlete_preferences

        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]

        prefs = make_athlete_preferences(athlete_id=athlete_id)
        test_db_session.add(prefs)
        await test_db_session.commit()
        await test_db_session.refresh(prefs)

        update_payload = {"sport_background": "cycling_crossover"}
        response = await client.patch(f"/athlete-preferences/{prefs.id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["sport_background"] == "cycling_crossover"

    @pytest.mark.asyncio
    async def test_update_preferences_partial(self, client: AsyncClient, registered_athlete: dict, test_db_session):
        """Test partial update with only sport_background."""
        from tests.factories.athlete_preferences_factory import make_athlete_preferences_full

        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]

        prefs = make_athlete_preferences_full(athlete_id=athlete_id)
        test_db_session.add(prefs)
        await test_db_session.commit()
        await test_db_session.refresh(prefs)

        original_years = prefs.years_structured_training

        update_payload = {"sport_background": "multi_sport"}
        response = await client.patch(f"/athlete-preferences/{prefs.id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["sport_background"] == "multi_sport"
        assert data["years_structured_training"] == original_years

    @pytest.mark.asyncio
    async def test_update_preferences_returns_404(self, client: AsyncClient, registered_athlete: dict):
        """Test updating nonexistent preferences returns 404."""
        headers = registered_athlete["headers"]
        fake_id = str(uuid.uuid4())
        update_payload = {"sport_background": "cycling_crossover"}
        response = await client.patch(f"/athlete-preferences/{fake_id}", json=update_payload, headers=headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Preferences not found"

    @pytest.mark.asyncio
    async def test_update_weekly_schedule(self, client: AsyncClient, registered_athlete: dict, test_db_session):
        """Test that weekly_schedule can be updated (full replacement)."""
        from tests.factories.athlete_preferences_factory import make_athlete_preferences

        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]

        prefs = make_athlete_preferences(athlete_id=athlete_id)
        test_db_session.add(prefs)
        await test_db_session.commit()
        await test_db_session.refresh(prefs)

        new_schedule = {
            "days": {
                "mon": {"available": True, "max_hours": 2.0, "long_workout": False},
                "tue": {"available": False, "max_hours": 0, "long_workout": False},
                "wed": {"available": True, "max_hours": 2.0, "long_workout": False},
                "thu": {"available": False, "max_hours": 0, "long_workout": False},
                "fri": {"available": True, "max_hours": 2.0, "long_workout": False},
                "sat": {"available": True, "max_hours": 3.0, "long_workout": True},
                "sun": {"available": True, "max_hours": 3.0, "long_workout": True},
            },
            "available_days_count": 5,
        }
        update_payload = {"weekly_schedule": new_schedule}
        response = await client.patch(f"/athlete-preferences/{prefs.id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["weekly_schedule"]["days"]["mon"]["max_hours"] == 2.0

    @pytest.mark.asyncio
    async def test_update_changes_updated_at(self, client: AsyncClient, registered_athlete: dict, test_db_session):
        """Test that updated_at timestamp changes after patch."""
        from tests.factories.athlete_preferences_factory import make_athlete_preferences
        from datetime import datetime

        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]

        prefs = make_athlete_preferences(athlete_id=athlete_id)
        prefs.created_at = datetime(2024, 1, 1, 0, 0, 0)
        prefs.updated_at = datetime(2024, 1, 1, 0, 0, 0)
        test_db_session.add(prefs)
        await test_db_session.commit()
        await test_db_session.refresh(prefs)

        original_updated_at = prefs.updated_at

        update_payload = {"sport_background": "cycling_crossover"}
        response = await client.patch(f"/athlete-preferences/{prefs.id}", json=update_payload, headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data["updated_at"] != original_updated_at.isoformat()
