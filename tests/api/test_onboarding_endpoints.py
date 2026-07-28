import uuid
from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.token_service import TokenService
from app.models.enums import (
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
)
from tests.utils.factories import make_athlete_with_profile


def _weekday(available: bool = True, max_hours: float = 2.0) -> dict[str, bool | float]:
    return {
        "available": available,
        "max_hours": max_hours,
        "long_workout": False,
        "doubles_eligible": False,
    }


def _week_schedule() -> dict[str, dict[str, bool | float]]:
    return {
        day: _weekday()
        for day in [
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
        ]
    }


def _full_onboarding_payload() -> dict[str, dict[str, object]]:
    return {
        "profile": {
            "timezone": "Europe/London",
            "height_cm": 175.0,
        },
        "preferences": {
            "sport_background": SportBackground.RUNNING_PRIMARY.value,
            "years_structured_training": 3,
            "training_time_of_day": "morning",
            "weekly_schedule": _week_schedule(),
            "gps_source": GpsSource.GARMIN_WATCH.value,
            "hr_source": HrSource.CHEST_STRAP_RR.value,
            "power_source": PowerSource.RUNNING_POWER_METER.value,
            "primary_training_platform": PrimaryTrainingPlatform.GARMIN_CONNECT.value,
        },
        "goal": {
            "goal_type": GoalType.RACE_EVENT.value,
            "goal_event_type": GoalEventType.MARATHON.value,
            "goal_event_name": "Berlin Marathon",
            "goal_event_date": (date.today() + timedelta(days=120)).isoformat(),
            "weekly_volume_hours": 8.0,
            "weekly_volume_km": 60.0,
            "fitness_level": 3,
        },
    }


async def _issue_token(athlete_id: uuid.UUID) -> str:
    svc = TokenService()
    token, _ = svc.issue_access_token(athlete_id)
    return token


async def _auth_header(athlete_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {await _issue_token(athlete_id)}"}


@pytest.fixture
async def athlete_with_profile(db_session: AsyncSession) -> uuid.UUID:
    athlete, _ = await make_athlete_with_profile(db_session)
    return athlete.id


class TestPostOnboardingEndpoint:
    async def test_post_onboarding_201_returns_response(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["data_tier"] == 1
        assert "twin_state_id" in data
        assert "training_goal_id" in data

    async def test_post_onboarding_409_when_already_complete(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        first = await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        assert first.status_code == 201

        second = await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        assert second.status_code == 409

    async def test_post_onboarding_422_when_goal_type_invalid(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        payload = _full_onboarding_payload()
        payload["goal"]["goal_type"] = GoalType.FITNESS_IMPROVEMENT.value
        response = await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=payload,
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 422

    async def test_post_onboarding_404_when_athlete_missing(self, client: AsyncClient):
        missing_id = uuid.uuid4()
        response = await client.post(
            f"/athletes/{missing_id}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(missing_id),
        )
        assert response.status_code == 404

    async def test_post_onboarding_403_when_path_id_mismatches_jwt(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        other_id = uuid.uuid4()
        response = await client.post(
            f"/athletes/{other_id}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 403

    async def test_post_onboarding_422_when_timezone_invalid(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        payload = _full_onboarding_payload()
        payload["profile"]["timezone"] = "Not/A_Timezone"
        response = await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=payload,
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 422


class TestGetOnboardingStatusEndpoint:
    async def test_get_status_before_onboarding_returns_false(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.get(
            f"/athletes/{athlete_with_profile}/onboarding",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is False
        assert data["has_preferences"] is False
        assert data["has_training_goal"] is False
        assert data["has_twin_state"] is False

    async def test_get_status_after_onboarding_returns_true(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.get(
            f"/athletes/{athlete_with_profile}/onboarding",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["onboarding_complete"] is True
        assert data["has_preferences"] is True
        assert data["has_training_goal"] is True
        assert data["has_twin_state"] is True


class TestGetProfileEndpoint:
    async def test_get_profile_returns_registered_profile(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.get(
            f"/athletes/{athlete_with_profile}/profile",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == str(athlete_with_profile)
        assert "date_of_birth" in data
        assert "sex" in data

    async def test_get_profile_403_on_cross_athlete(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        other_id = uuid.uuid4()
        response = await client.get(
            f"/athletes/{other_id}/profile",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 403


class TestPatchProfileEndpoint:
    async def test_patch_profile_updates_height(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/profile",
            json={"height_cm": 180.0},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        assert response.json()["height_cm"] == pytest.approx(180.0, abs=0.01)

    async def test_patch_profile_rejects_immutable_timezone(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/profile",
            json={"timezone": "UTC"},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 422

    async def test_patch_profile_rejects_immutable_date_of_birth(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/profile",
            json={"date_of_birth": "1995-01-01"},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 422

    async def test_patch_profile_rejects_unknown_field(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/profile",
            json={"unknown_field": "value"},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 422


class TestGetPreferencesEndpoint:
    async def test_get_preferences_404_before_onboarding(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.get(
            f"/athletes/{athlete_with_profile}/preferences",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 404

    async def test_get_preferences_returns_after_onboarding(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.get(
            f"/athletes/{athlete_with_profile}/preferences",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == str(athlete_with_profile)
        assert data["hr_source"] == HrSource.CHEST_STRAP_RR.value
        assert data["power_source"] == PowerSource.RUNNING_POWER_METER.value


class TestPatchPreferencesEndpoint:
    async def test_patch_preferences_merges_day_level(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/preferences",
            json={"weekly_schedule": {"saturday": {"available": False}}},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        schedule = response.json()["weekly_schedule"]
        assert schedule["saturday"]["available"] is False
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "sunday"]:
            assert schedule[day]["available"] is True

    async def test_patch_preferences_updates_top_level(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/preferences",
            json={"years_structured_training": 15},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        assert response.json()["years_structured_training"] == 15

    async def test_patch_preferences_rejects_unknown_field(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.patch(
            f"/athletes/{athlete_with_profile}/preferences",
            json={"unknown_field": "value"},
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 422


class TestGetTwinEndpoints:
    async def test_get_twin_404_before_onboarding(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        response = await client.get(
            f"/athletes/{athlete_with_profile}/twin",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 404

    async def test_get_twin_returns_bootstrap_state(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.get(
            f"/athletes/{athlete_with_profile}/twin",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["athlete_id"] == str(athlete_with_profile)
        assert data["fitness"] == 0.0
        assert data["fatigue"] == 0.0
        assert data["form"] == 0.0
        assert data["lt1_hr_bpm"] is not None
        assert data["lt2_hr_bpm"] is not None
        assert data["lt1_hr_bpm"] < data["lt2_hr_bpm"]

    async def test_get_twin_history_returns_after_onboarding(
        self, client: AsyncClient, athlete_with_profile: uuid.UUID
    ):
        await client.post(
            f"/athletes/{athlete_with_profile}/onboarding",
            json=_full_onboarding_payload(),
            headers=await _auth_header(athlete_with_profile),
        )
        response = await client.get(
            f"/athletes/{athlete_with_profile}/twin/history",
            headers=await _auth_header(athlete_with_profile),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert len(data["items"]) == 1
