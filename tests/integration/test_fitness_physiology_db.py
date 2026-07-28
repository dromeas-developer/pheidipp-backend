import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_fitness import AthleteFitness
from app.models.athlete_physiology import AthletePhysiology
from tests.utils.factories import make_athlete


class TestAthleteFitnessUniqueAthleteId:
    async def test_duplicate_athlete_id_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        await db_session.commit()

        fitness2 = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 50, "fatigue": 20, "form": 30},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestAthleteFitnessFormInvariant:
    async def test_valid_aggregate_form_succeeds(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        await db_session.commit()

    async def test_invalid_aggregate_form_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 50},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()


class TestAthleteFitnessDimensionalFormInvariant:
    async def test_valid_aerobic_form_succeeds(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            aerobic={"fitness": 50, "fatigue": 20, "form": 30},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        await db_session.commit()

    async def test_invalid_aerobic_form_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            aerobic={"fitness": 50, "fatigue": 20, "form": 25},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_null_aerobic_skips_check(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            aerobic=None,
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        await db_session.commit()


class TestAthleteFitnessTimeConstantsSource:
    async def test_invalid_source_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            time_constants={"source": "custom_value"},
        )
        db_session.add(fitness)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_population_default_source_succeeds(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            time_constants={"source": "population_default"},
        )
        db_session.add(fitness)
        await db_session.commit()

    async def test_individual_fitted_source_succeeds(self, db_session: AsyncSession):
        athlete = await make_athlete(db_session)
        fitness = AthleteFitness(
            athlete_id=athlete.id,
            aggregate={"fitness": 100, "fatigue": 40, "form": 60},
            time_constants={"source": "individual_fitted"},
        )
        db_session.add(fitness)
        await db_session.commit()


class TestAthletePhysiologyUniqueAthleteId:
    async def test_duplicate_physiology_athlete_id_raises_integrity_error(
        self, db_session: AsyncSession
    ):
        athlete = await make_athlete(db_session)
        phys = AthletePhysiology(
            athlete_id=athlete.id,
            lt1={},
            lt2={},
        )
        db_session.add(phys)
        await db_session.commit()

        phys2 = AthletePhysiology(
            athlete_id=athlete.id,
            lt1={},
            lt2={},
        )
        db_session.add(phys2)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()
