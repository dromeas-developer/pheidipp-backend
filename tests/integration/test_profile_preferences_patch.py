from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.onboarding import AthletePreferencesPatchIn, AthleteProfilePatchIn
from app.services.onboarding_service import OnboardingService
from tests.utils.onboarding_builders import (
    make_goal_input,
    make_preferences_input,
    make_profile_input,
)


async def _onboarded_athlete(db_session: AsyncSession, **prefs_overrides: Any):
    from tests.utils.factories import make_athlete_with_profile as _make

    athlete, _ = await _make(db_session)
    service = OnboardingService(db_session)
    await service.complete_onboarding(
        athlete_id=athlete.id,
        profile_input=make_profile_input(),
        prefs_input=make_preferences_input(**prefs_overrides),
        goal_input=make_goal_input(),
    )
    return athlete


class TestProfilePatchMutable:
    async def test_patch_height_cm_updates_profile(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)
        updated = await service.update_profile(athlete.id, height_cm=180.0)
        assert updated.height_cm is not None
        assert float(updated.height_cm) == 180.0

    async def test_patch_location_lat_lng_updates_profile(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)
        updated = await service.update_profile(
            athlete.id,
            location_lat=40.7128,
            location_lng=-74.0060,
        )
        assert updated.location_lat is not None
        assert updated.location_lng is not None
        assert float(updated.location_lat) == pytest.approx(40.7128, abs=1e-4)
        assert float(updated.location_lng) == pytest.approx(-74.0060, abs=1e-4)

    async def test_patch_training_window_updates_profile(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)
        updated = await service.update_profile(
            athlete.id,
            training_window={"start": "06:00", "end": "20:00"},
        )
        assert updated.training_window == {"start": "06:00", "end": "20:00"}

    async def test_patch_no_args_is_noop(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)
        profile = await service.get_profile(athlete.id)
        assert profile is not None
        original_height = profile.height_cm
        updated = await service.update_profile(athlete.id)
        assert updated.height_cm == original_height


class TestProfilePatchImmutability:
    async def test_patch_schema_rejects_date_of_birth(self):
        with pytest.raises(ValidationError) as exc_info:
            AthleteProfilePatchIn.model_validate({"date_of_birth": "1995-01-01"})
        assert any(
            "profile fields are immutable after registration: date_of_birth" in e["msg"]
            for e in exc_info.value.errors()
        )

    async def test_patch_schema_rejects_timezone(self):
        with pytest.raises(ValidationError):
            AthleteProfilePatchIn.model_validate({"timezone": "UTC"})

    async def test_patch_schema_rejects_sex(self):
        with pytest.raises(ValidationError):
            AthleteProfilePatchIn.model_validate({"sex": "female"})

    async def test_patch_schema_rejects_unknown_field(self):
        with pytest.raises(ValidationError):
            AthleteProfilePatchIn.model_validate({"unknown_field": "value"})


class TestPreferencesPatchMerge:
    async def test_patch_saturday_available_flips_only_saturday(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)

        before = await service.get_preferences(athlete.id)
        assert before is not None
        original_monday = before.weekly_schedule["monday"]

        updated = await service.update_preferences(
            athlete.id,
            {"weekly_schedule": {"saturday": {"available": False}}},
        )

        assert updated.weekly_schedule["saturday"]["available"] is False
        assert (
            updated.weekly_schedule["saturday"]["max_hours"]
            == original_monday["max_hours"]
        )
        assert updated.weekly_schedule["saturday"]["long_workout"] is False
        assert updated.weekly_schedule["saturday"]["doubles_eligible"] is False
        for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "sunday"]:
            assert updated.weekly_schedule[day] == before.weekly_schedule[day]

    async def test_patch_top_level_field_overwrites(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)

        updated = await service.update_preferences(
            athlete.id,
            {"years_structured_training": 10},
        )
        assert updated.years_structured_training == 10

    async def test_patch_idempotent_re_applying_same_patch(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)

        first = await service.update_preferences(
            athlete.id,
            {"weekly_schedule": {"saturday": {"available": False}}},
        )
        second = await service.update_preferences(
            athlete.id,
            {"weekly_schedule": {"saturday": {"available": False}}},
        )
        assert first.weekly_schedule == second.weekly_schedule

    async def test_patch_unknown_key_silently_ignored(self, db_session: AsyncSession):
        athlete = await _onboarded_athlete(db_session)
        service = OnboardingService(db_session)

        updated = await service.update_preferences(
            athlete.id,
            {"unknown_field": "value", "years_structured_training": 7},
        )
        assert updated.years_structured_training == 7

    async def test_patch_schema_rejects_unknown_field(self):
        with pytest.raises(ValidationError):
            AthletePreferencesPatchIn.model_validate({"unknown_field": "value"})


class TestPreferencesPatchSchema:
    def test_patch_schema_accepts_partial_weekday(self):
        patch = AthletePreferencesPatchIn.model_validate(
            {
                "weekly_schedule": {"monday": {"available": False}},
            }
        )
        assert patch.weekly_schedule is not None
        assert patch.weekly_schedule["monday"].available is False

    def test_patch_schema_rejects_non_canonical_weekday(self):
        with pytest.raises(ValidationError) as exc_info:
            AthletePreferencesPatchIn.model_validate(
                {
                    "weekly_schedule": {"funday": {"available": True}},
                }
            )
        assert any(
            "non-canonical weekday keys" in e["msg"] for e in exc_info.value.errors()
        )

    def test_patch_schema_empty_weekly_schedule_accepted(self):
        patch = AthletePreferencesPatchIn.model_validate({"weekly_schedule": {}})
        assert patch.weekly_schedule == {}
