import uuid
from datetime import date, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security.token_service import TokenService
from app.models.athlete import Athlete
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


async def _issue_token(athlete_id: uuid.UUID) -> str:
    svc = TokenService()
    token, _ = svc.issue_access_token(athlete_id)
    return token


async def _auth_header(athlete_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {await _issue_token(athlete_id)}"}


class TestOnboardingJourney:
    async def test_full_journey_register_to_get_twin(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        athlete, _ = await make_athlete_with_profile(db_session)
        header = await _auth_header(athlete.id)

        before = await client.get(f"/athletes/{athlete.id}/onboarding", headers=header)
        assert before.status_code == 200
        assert before.json()["onboarding_complete"] is False

        profile_before = await client.get(
            f"/athletes/{athlete.id}/profile", headers=header
        )
        assert profile_before.status_code == 200
        assert profile_before.json()["timezone"] is None

        prefs_before = await client.get(
            f"/athletes/{athlete.id}/preferences", headers=header
        )
        assert prefs_before.status_code == 404

        twin_before = await client.get(f"/athletes/{athlete.id}/twin", headers=header)
        assert twin_before.status_code == 404

        payload = {
            "profile": {
                "timezone": "Europe/London",
                "height_cm": 175.0,
            },
            "preferences": {
                "sport_background": SportBackground.RUNNING_PRIMARY.value,
                "years_structured_training": 5,
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
                "goal_event_date": (date.today() + timedelta(days=180)).isoformat(),
                "weekly_volume_hours": 10.0,
                "weekly_volume_km": 80.0,
                "fitness_level": 4,
            },
        }
        post = await client.post(
            f"/athletes/{athlete.id}/onboarding", json=payload, headers=header
        )
        assert post.status_code == 201
        post_data = post.json()
        twin_state_id = post_data["twin_state_id"]
        training_goal_id = post_data["training_goal_id"]

        after = await client.get(f"/athletes/{athlete.id}/onboarding", headers=header)
        assert after.status_code == 200
        assert after.json()["onboarding_complete"] is True
        assert after.json()["has_preferences"] is True
        assert after.json()["has_training_goal"] is True
        assert after.json()["has_twin_state"] is True

        profile_after = await client.get(
            f"/athletes/{athlete.id}/profile", headers=header
        )
        assert profile_after.status_code == 200
        assert profile_after.json()["timezone"] == "Europe/London"
        assert profile_after.json()["structural_risk_flag"] is False

        prefs_after = await client.get(
            f"/athletes/{athlete.id}/preferences", headers=header
        )
        assert prefs_after.status_code == 200
        prefs_data = prefs_after.json()
        assert prefs_data["hr_source"] == HrSource.CHEST_STRAP_RR.value
        assert prefs_data["years_structured_training"] == 5

        twin_after = await client.get(f"/athletes/{athlete.id}/twin", headers=header)
        assert twin_after.status_code == 200
        twin_data = twin_after.json()
        assert twin_data["id"] == twin_state_id
        assert twin_data["training_goal_id"] == training_goal_id
        assert twin_data["fitness"] == 0.0
        assert twin_data["fatigue"] == 0.0
        assert twin_data["form"] == 0.0
        assert twin_data["lt1_hr_bpm"] is not None
        assert twin_data["lt2_hr_bpm"] is not None
        assert twin_data["lt1_hr_bpm"] < twin_data["lt2_hr_bpm"]

        history = await client.get(
            f"/athletes/{athlete.id}/twin/history", headers=header
        )
        assert history.status_code == 200
        assert history.json()["count"] == 1

        duplicate = await client.post(
            f"/athletes/{athlete.id}/onboarding", json=payload, headers=header
        )
        assert duplicate.status_code == 409

    async def test_cross_athlete_403_blocks_every_endpoint(
        self, client: AsyncClient, db_session: AsyncSession
    ):
        athlete, _ = await make_athlete_with_profile(db_session)
        other_athlete = Athlete(email=f"other-{uuid.uuid4()}@example.com")
        db_session.add(other_athlete)
        await db_session.commit()
        await db_session.refresh(other_athlete)

        header = await _auth_header(athlete.id)
        for path in (
            f"/athletes/{other_athlete.id}/onboarding",
            f"/athletes/{other_athlete.id}/profile",
            f"/athletes/{other_athlete.id}/preferences",
            f"/athletes/{other_athlete.id}/twin",
            f"/athletes/{other_athlete.id}/twin/history",
        ):
            response = await client.get(path, headers=header)
            assert response.status_code == 403, (
                f"path {path} got {response.status_code}"
            )
