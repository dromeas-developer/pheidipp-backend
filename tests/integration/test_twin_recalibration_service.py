"""Integration tests for TwinRecalibrationService.recalibrate — DB-touching path.

Covers the recalibrate method that appends a new TwinState via the
ACTIVITY_SYNC trigger. The service does not commit; tests commit
explicitly. Event emission is covered where applicable.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TwinTrigger
from app.models.twin_state import TwinState
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.twin_recalibration_service import (
    MissingAthleteFitnessError,
    MissingTrainingGoalError,
    TwinRecalibrationService,
)
from tests.utils.factories import (
    make_activity,
    make_athlete_fitness,
    make_athlete_physiology,
    make_athlete_preferences,
    make_athlete_with_profile,
    make_training_goal,
    make_twin_state,
)


async def _build_full_setup(
    db_session: AsyncSession,
    *,
    aggregate: dict[str, float] | None = None,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    athlete, _ = await make_athlete_with_profile(db_session)
    await make_athlete_preferences(db_session, athlete_id=athlete.id)
    await make_athlete_fitness(
        db_session,
        athlete_id=athlete.id,
        aggregate=aggregate or {"fitness": 100.0, "fatigue": 40.0, "form": 60.0},
    )
    await make_athlete_physiology(db_session, athlete_id=athlete.id)
    goal = await make_training_goal(db_session, athlete_id=athlete.id)
    await make_twin_state(
        db_session,
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        trigger=TwinTrigger.QUESTIONNAIRE,
    )
    activity = await make_activity(db_session, athlete_id=athlete.id)
    return athlete.id, goal.id, activity.id


class TestRecalibrateAppendsNewState:
    async def test_recalibrate_inserts_new_twin_state_with_activity_sync_trigger(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _, activity_id = await _build_full_setup(db_session)

        service = TwinRecalibrationService(db_session)
        result = await service.recalibrate(
            athlete_id=athlete_id,
            activity_id=activity_id,
            aerobic_load=50.0,
        )
        await db_session.commit()

        assert result.twin_state.trigger == TwinTrigger.ACTIVITY_SYNC
        assert result.twin_state.model_version == "v1-activity-sync"

    async def test_recalibrate_updates_fitness_aggregate(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _, activity_id = await _build_full_setup(
            db_session,
            aggregate={"fitness": 100.0, "fatigue": 40.0, "form": 60.0},
        )

        service = TwinRecalibrationService(db_session)
        await service.recalibrate(
            athlete_id=athlete_id,
            activity_id=activity_id,
            aerobic_load=50.0,
        )
        await db_session.commit()

        from app.models.athlete_fitness import AthleteFitness

        result = await db_session.execute(
            select(AthleteFitness).where(AthleteFitness.athlete_id == athlete_id)
        )
        fitness = result.scalar_one()
        assert fitness.aggregate["fitness"] > 100.0
        assert fitness.aggregate["fatigue"] > 40.0
        assert fitness.aggregate["form"] == pytest.approx(
            fitness.aggregate["fitness"] - fitness.aggregate["fatigue"], abs=0.001
        )

    async def test_recalibrate_preserves_latest_thresholds(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, goal_id, activity_id = await _build_full_setup(db_session)

        from app.models.twin_state import TwinState as TSType
        from app.models.enums import RecoveryModifierLevel

        ts = TSType(
            athlete_id=athlete_id,
            training_goal_id=goal_id,
            data_tier=3,
            confidence_level="low",
            trigger=TwinTrigger.QUESTIONNAIRE,
            model_version="v1-questionnaire-bootstrap",
            fitness=0.0,
            fatigue=0.0,
            form=0.0,
            lt1_hr_bpm=138.0,
            lt2_hr_bpm=161.0,
            readiness_level=RecoveryModifierLevel.GREEN,
            metric_confidence={},
        )
        db_session.add(ts)
        await db_session.commit()

        service = TwinRecalibrationService(db_session)
        result = await service.recalibrate(
            athlete_id=athlete_id,
            activity_id=activity_id,
            aerobic_load=50.0,
        )
        await db_session.commit()

        assert result.twin_state.lt1_hr_bpm == 138.0
        assert result.twin_state.lt2_hr_bpm == 161.0

    async def test_recalibrate_preserves_latest_confidence_level(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _, activity_id = await _build_full_setup(db_session)

        service = TwinRecalibrationService(db_session)
        result = await service.recalibrate(
            athlete_id=athlete_id,
            activity_id=activity_id,
            aerobic_load=50.0,
        )
        await db_session.commit()

        assert result.twin_state.confidence_level == "low"

    async def test_existing_twin_state_unchanged_after_recalibrate(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _, activity_id = await _build_full_setup(db_session)
        latest_before = await TwinStateRepository(db_session).get_latest(athlete_id)
        assert latest_before is not None
        before_id = latest_before.id

        service = TwinRecalibrationService(db_session)
        await service.recalibrate(
            athlete_id=athlete_id,
            activity_id=activity_id,
            aerobic_load=50.0,
        )
        await db_session.commit()

        result = await db_session.execute(
            select(TwinState).where(TwinState.id == before_id)
        )
        persisted = result.scalar_one()
        assert persisted.id == before_id
        assert persisted.trigger == TwinTrigger.QUESTIONNAIRE

    async def test_no_athlete_update_via_update_method_in_recalibrate(
        self, db_session: AsyncSession
    ) -> None:
        athlete_id, _, activity_id = await _build_full_setup(db_session)
        count_before_query = select(TwinState).where(
            TwinState.athlete_id == athlete_id
        )

        result_before = await db_session.execute(count_before_query)
        count_before = len(list(result_before.scalars()))

        service = TwinRecalibrationService(db_session)
        await service.recalibrate(
            athlete_id=athlete_id,
            activity_id=activity_id,
            aerobic_load=50.0,
        )
        await db_session.commit()

        result_after = await db_session.execute(
            select(TwinState).where(TwinState.athlete_id == athlete_id)
        )
        count_after = len(list(result_after.scalars()))

        assert count_after == count_before + 1


class TestRecalibrateMissingDependencies:
    async def test_no_active_goal_raises(
        self, db_session: AsyncSession
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        await make_athlete_fitness(db_session, athlete_id=athlete.id)

        service = TwinRecalibrationService(db_session)
        with pytest.raises(MissingTrainingGoalError):
            await service.recalibrate(
                athlete_id=athlete.id,
                activity_id=uuid.uuid4(),
                aerobic_load=50.0,
            )

    async def test_no_fitness_row_raises(
        self, db_session: AsyncSession
    ) -> None:
        athlete, _ = await make_athlete_with_profile(db_session)
        await make_athlete_preferences(db_session, athlete_id=athlete.id)
        await make_training_goal(db_session, athlete_id=athlete.id)

        service = TwinRecalibrationService(db_session)
        with pytest.raises(MissingAthleteFitnessError):
            await service.recalibrate(
                athlete_id=athlete.id,
                activity_id=uuid.uuid4(),
                aerobic_load=50.0,
            )
