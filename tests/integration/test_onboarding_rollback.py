import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.enums import (
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
    TrainingTimeOfDay,
)
from app.models.system_event import SystemEvent
from app.models.training_goal import TrainingGoal
from app.models.twin_state import TwinState
from app.services.onboarding_service import OnboardingService
from tests.utils.factories import make_athlete_with_profile
from tests.utils.onboarding_builders import (
    make_goal_input,
    make_preferences_input,
    make_profile_input,
)


def _make_existing_preferences(athlete_id: uuid.UUID) -> AthletePreferences:
    return AthletePreferences(
        athlete_id=athlete_id,
        sport_background=SportBackground.RUNNING_PRIMARY,
        years_structured_training=3,
        training_time_of_day=TrainingTimeOfDay.MORNING,
        weekly_schedule={"monday": {"available": True, "max_hours": 2.0}},
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.RUNNING_POWER_METER,
        primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
    )


class TestOnboardingMidTransactionRollback:
    async def test_failure_after_physiology_insert_rolls_back_all(
        self, db_session: AsyncSession
    ):
        athlete, _ = await make_athlete_with_profile(db_session)
        athlete_id = athlete.id

        db_session.add(_make_existing_preferences(athlete_id))
        await db_session.flush()

        service = OnboardingService(db_session)
        with pytest.raises(IntegrityError):
            await service.complete_onboarding(
                athlete_id=athlete_id,
                profile_input=make_profile_input(),
                prefs_input=make_preferences_input(),
                goal_input=make_goal_input(),
            )

        await db_session.rollback()
        db_session.expire_all()

        prefs_count = (
            (
                await db_session.execute(
                    select(AthletePreferences).where(
                        AthletePreferences.athlete_id == athlete_id
                    )
                )
            )
            .scalars()
            .all()
        )
        goal_count = (
            (
                await db_session.execute(
                    select(TrainingGoal).where(TrainingGoal.athlete_id == athlete_id)
                )
            )
            .scalars()
            .all()
        )
        physio_count = (
            (
                await db_session.execute(
                    select(AthletePhysiology).where(
                        AthletePhysiology.athlete_id == athlete_id
                    )
                )
            )
            .scalars()
            .all()
        )
        fitness_count = (
            (
                await db_session.execute(
                    select(AthleteFitness).where(
                        AthleteFitness.athlete_id == athlete_id
                    )
                )
            )
            .scalars()
            .all()
        )
        twin_count = (
            (
                await db_session.execute(
                    select(TwinState).where(TwinState.athlete_id == athlete_id)
                )
            )
            .scalars()
            .all()
        )
        events = (
            (
                await db_session.execute(
                    select(SystemEvent).where(SystemEvent.athlete_id == athlete_id)
                )
            )
            .scalars()
            .all()
        )

        assert prefs_count == []
        assert goal_count == []
        assert physio_count == []
        assert fitness_count == []
        assert twin_count == []
        assert events == []

        refreshed = await db_session.get(Athlete, athlete_id)
        assert refreshed is not None
        assert refreshed.onboarding_complete is False

    async def test_failure_after_fitness_insert_rolls_back(
        self, db_session: AsyncSession
    ):
        athlete, _ = await make_athlete_with_profile(db_session)
        athlete_id = athlete.id

        db_session.add(_make_existing_preferences(athlete_id))
        await db_session.flush()

        service = OnboardingService(db_session)
        with pytest.raises(IntegrityError):
            await service.complete_onboarding(
                athlete_id=athlete_id,
                profile_input=make_profile_input(),
                prefs_input=make_preferences_input(),
                goal_input=make_goal_input(),
            )

        await db_session.rollback()
        db_session.expire_all()

        prefs_count = (
            (
                await db_session.execute(
                    select(AthletePreferences).where(
                        AthletePreferences.athlete_id == athlete_id
                    )
                )
            )
            .scalars()
            .all()
        )
        goal_count = (
            (
                await db_session.execute(
                    select(TrainingGoal).where(TrainingGoal.athlete_id == athlete_id)
                )
            )
            .scalars()
            .all()
        )
        fitness_count = (
            (
                await db_session.execute(
                    select(AthleteFitness).where(
                        AthleteFitness.athlete_id == athlete_id
                    )
                )
            )
            .scalars()
            .all()
        )
        twin_count = (
            (
                await db_session.execute(
                    select(TwinState).where(TwinState.athlete_id == athlete_id)
                )
            )
            .scalars()
            .all()
        )

        assert prefs_count == []
        assert goal_count == []
        assert fitness_count == []
        assert twin_count == []

    async def test_failure_keeps_profile_state_unchanged(
        self, db_session: AsyncSession
    ):
        athlete, profile = await make_athlete_with_profile(db_session)
        profile.timezone = "Europe/London"
        await db_session.commit()

        athlete_id = athlete.id
        profile_id = profile.id
        db_session.add(_make_existing_preferences(athlete_id))
        await db_session.flush()

        service = OnboardingService(db_session)
        with pytest.raises(IntegrityError):
            await service.complete_onboarding(
                athlete_id=athlete_id,
                profile_input=make_profile_input(timezone="America/New_York"),
                prefs_input=make_preferences_input(),
                goal_input=make_goal_input(),
            )

        await db_session.rollback()
        db_session.expire_all()
        refreshed = await db_session.get(AthleteProfile, profile_id)
        assert refreshed is not None
        assert refreshed.timezone == "Europe/London"
