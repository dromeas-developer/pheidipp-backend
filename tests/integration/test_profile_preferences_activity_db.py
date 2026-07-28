from datetime import date, datetime, timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    ActivitySource,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    Sex,
    SportBackground,
    TrainingTimeOfDay,
)
from tests.utils.factories import make_athlete


class TestAthleteProfileUniqueAthleteId:
    async def test_duplicate_athlete_id_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        profile = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1990, 1, 1),
            sex=Sex.MALE,
        )
        db_session.add(profile)
        await db_session.commit()

        profile2 = AthleteProfile(
            athlete_id=athlete.id,
            date_of_birth=date(1995, 6, 15),
            sex=Sex.FEMALE,
        )
        db_session.add(profile2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestAthletePreferencesUniqueAthleteId:
    async def test_duplicate_preferences_athlete_id_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=5,
            training_time_of_day=TrainingTimeOfDay.MORNING,
            weekly_schedule={"monday": {"available": True}},
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.RUNNING_POWER_METER,
            primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
        )
        db_session.add(prefs)
        await db_session.commit()

        prefs2 = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.CYCLING_PRIMARY,
            years_structured_training=3,
            training_time_of_day=TrainingTimeOfDay.EVENING,
            weekly_schedule={"tuesday": {"available": True}},
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.WRIST_OPTICAL,
            power_source=PowerSource.NONE,
            primary_training_platform=PrimaryTrainingPlatform.INTERVALS_ICU,
        )
        db_session.add(prefs2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestAthletePreferencesYearsStructuredTrainingCheck:
    async def test_negative_years_structured_training_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        prefs = AthletePreferences(
            athlete_id=athlete.id,
            sport_background=SportBackground.RUNNING_PRIMARY,
            years_structured_training=-1,
            training_time_of_day=TrainingTimeOfDay.MORNING,
            weekly_schedule={"monday": {"available": True}},
            gps_source=GpsSource.GARMIN_WATCH,
            hr_source=HrSource.CHEST_STRAP_RR,
            power_source=PowerSource.RUNNING_POWER_METER,
            primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
        )
        db_session.add(prefs)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestActivityDedupExternalId:
    async def test_duplicate_external_id_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            external_id="ext123",
            activity_date=date(2025, 6, 1),
            start_time=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
        )
        db_session.add(activity)
        await db_session.commit()

        activity2 = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_UPLOAD,
            external_id="ext123",
            activity_date=date(2025, 6, 2),
            start_time=datetime(2025, 6, 2, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
        )
        db_session.add(activity2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestActivityDedupExemptManualEntry:
    async def test_null_external_id_duplicates_succeed(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        activity = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
            activity_date=date(2025, 6, 1),
            start_time=datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=3600,
        )
        db_session.add(activity)
        await db_session.commit()

        activity2 = Activity(
            athlete_id=athlete.id,
            source=ActivitySource.MANUAL_ENTRY,
            external_id=None,
            activity_date=date(2025, 6, 2),
            start_time=datetime(2025, 6, 2, 10, 0, 0, tzinfo=timezone.utc),
            duration_seconds=1800,
        )
        db_session.add(activity2)
        await db_session.commit()
