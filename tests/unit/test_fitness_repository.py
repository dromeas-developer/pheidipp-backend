"""DB-backed tests for FitnessRepository methods."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete import Athlete
from app.models.enums import AthleteStatus
from app.models.fitness import AthleteFitness
from app.models.enums import DataSource
from app.repositories.fitness_repository import FitnessRepository


@pytest.fixture
async def athlete(test_db_session: AsyncSession) -> Athlete:
    """Create a test athlete in the database."""
    athlete = Athlete(
        id=uuid.uuid4(),
        email=f"test_{uuid.uuid4().hex[:8]}@example.com",
        hashed_password=None,
        status=AthleteStatus.ACTIVE,
    )
    test_db_session.add(athlete)
    await test_db_session.commit()
    await test_db_session.refresh(athlete)
    return athlete


@pytest.fixture
def fitness_repo(test_db_session: AsyncSession) -> FitnessRepository:
    """Create a FitnessRepository instance with the test session."""
    return FitnessRepository(test_db_session)


async def _create_fitness(
    session: AsyncSession,
    athlete_id: uuid.UUID,
    metric_date: date,
    **kwargs,
) -> AthleteFitness:
    """Helper to create a fitness record in the database."""
    fitness = AthleteFitness(
        athlete_id=athlete_id,
        metric_date=metric_date,
        tss=kwargs.get('tss', 75.5),
        atl=kwargs.get('atl', 42.0),
        ctl=kwargs.get('ctl', 65.0),
        tsb=kwargs.get('tsb', 23.0),
        source=kwargs.get('source', DataSource.MANUAL),
    )
    session.add(fitness)
    await session.commit()
    await session.refresh(fitness)
    return fitness


class TestCreate:
    """Test FitnessRepository.create method."""

    async def test_create_persists_athlete_fitness_record(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test create persists an AthleteFitness record."""
        fitness = await fitness_repo.create(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
            tss=75.5,
            atl=42.0,
            ctl=65.0,
            tsb=23.0,
            source=DataSource.MANUAL,
        )

        assert fitness.id is not None
        assert fitness.athlete_id == athlete.id
        assert fitness.metric_date == date(2024, 1, 1)
        assert fitness.tss == 75.5
        assert fitness.atl == 42.0
        assert fitness.ctl == 65.0
        assert fitness.tsb == 23.0
        assert fitness.source == DataSource.MANUAL


class TestGetById:
    """Test FitnessRepository.get_by_id inherited from BaseRepository."""

    async def test_get_by_id_returns_the_record(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_id returns the record."""
        created = await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        result = await fitness_repo.get_by_id(created.id)

        assert result is not None
        assert result.id == created.id
        assert result.athlete_id == athlete.id
        assert result.metric_date == date(2024, 1, 1)


class TestGetByAthleteDate:
    """Test FitnessRepository.get_by_athlete_date method."""

    async def test_get_by_athlete_date_returns_record_for_composite_key(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete_date returns the record for composite key."""
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        result = await fitness_repo.get_by_athlete_date(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        assert result is not None
        assert result.athlete_id == athlete.id
        assert result.metric_date == date(2024, 1, 1)

    async def test_get_by_athlete_date_returns_none_when_not_found(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete_date returns None when not found."""
        result = await fitness_repo.get_by_athlete_date(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        assert result is None


class TestGetByAthlete:
    """Test FitnessRepository.get_by_athlete method."""

    async def test_get_by_athlete_returns_paginated_records_ordered_by_date_desc(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete returns paginated records ordered by metric_date descending."""
        # Create multiple fitness records with different dates
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 2, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 3, 1),
        )

        result = await fitness_repo.get_by_athlete(
            athlete_id=athlete.id,
            skip=0,
            limit=10,
        )

        assert len(result) == 3
        # Should be ordered by metric_date descending
        assert result[0].metric_date == date(2024, 3, 1)
        assert result[1].metric_date == date(2024, 2, 1)
        assert result[2].metric_date == date(2024, 1, 1)

    async def test_get_by_athlete_respects_pagination(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete respects skip and limit pagination."""
        # Create multiple fitness records
        for i in range(5):
            await _create_fitness(
                session=fitness_repo.session,
                athlete_id=athlete.id,
                metric_date=date(2024, 1, i + 1),
            )

        result = await fitness_repo.get_by_athlete(
            athlete_id=athlete.id,
            skip=2,
            limit=2,
        )

        assert len(result) == 2

    async def test_get_by_athlete_filters_by_date_from(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete filters by date_from."""
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 6, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 12, 1),
        )

        result = await fitness_repo.get_by_athlete(
            athlete_id=athlete.id,
            date_from=date(2024, 6, 1),
        )

        assert len(result) == 2
        assert all(r.metric_date >= date(2024, 6, 1) for r in result)

    async def test_get_by_athlete_filters_by_date_to(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete filters by date_to."""
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 6, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 12, 1),
        )

        result = await fitness_repo.get_by_athlete(
            athlete_id=athlete.id,
            date_to=date(2024, 6, 1),
        )

        assert len(result) == 2
        assert all(r.metric_date <= date(2024, 6, 1) for r in result)

    async def test_get_by_athlete_filters_by_date_range(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test get_by_athlete filters by both date_from and date_to."""
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 6, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 12, 1),
        )

        result = await fitness_repo.get_by_athlete(
            athlete_id=athlete.id,
            date_from=date(2024, 3, 1),
            date_to=date(2024, 9, 1),
        )

        assert len(result) == 1
        assert result[0].metric_date == date(2024, 6, 1)


class TestUpdateByAthleteDate:
    """Test FitnessRepository.update_by_athlete_date method."""

    async def test_update_by_athlete_date_modifies_and_returns_record(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test update_by_athlete_date modifies and returns the record."""
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
            tss=50.0,
        )

        result = await fitness_repo.update_by_athlete_date(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
            tss=100.0,
        )

        assert result is not None
        assert result.tss == 100.0

    async def test_update_by_athlete_date_returns_none_when_composite_key_missing(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test update_by_athlete_date returns None when composite key missing."""
        result = await fitness_repo.update_by_athlete_date(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
            tss=100.0,
        )

        assert result is None


class TestDeleteByCompositeKey:
    """Test FitnessRepository.delete_by_composite_key method."""

    async def test_delete_by_composite_key_removes_record_and_returns_true(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test delete_by_composite_key removes the record and returns True."""
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        result = await fitness_repo.delete_by_composite_key(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        assert result is True

        # Verify the record is deleted
        deleted = await fitness_repo.get_by_athlete_date(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )
        assert deleted is None

    async def test_delete_by_composite_key_returns_false_when_composite_key_missing(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test delete_by_composite_key returns False when composite key missing."""
        result = await fitness_repo.delete_by_composite_key(
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        assert result is False


class TestCountByAthlete:
    """Test FitnessRepository.count_by_athlete method."""

    async def test_count_by_athlete_returns_correct_count(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test count_by_athlete returns correct count."""
        # Create multiple fitness records
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 2, 1),
        )
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 3, 1),
        )

        count = await fitness_repo.count_by_athlete(athlete.id)

        assert count == 3

    async def test_count_by_athlete_returns_zero_when_no_records(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
    ):
        """Test count_by_athlete returns 0 when no records exist."""
        count = await fitness_repo.count_by_athlete(athlete.id)

        assert count == 0

    async def test_count_by_athlete_only_counts_for_specific_athlete(
        self,
        athlete: Athlete,
        fitness_repo: FitnessRepository,
        test_db_session: AsyncSession,
    ):
        """Test count_by_athlete only counts records for the specific athlete."""
        # Create records for the test athlete
        await _create_fitness(
            session=fitness_repo.session,
            athlete_id=athlete.id,
            metric_date=date(2024, 1, 1),
        )

        # Create another athlete with records
        other_athlete = Athlete(
            id=uuid.uuid4(),
            email=f"other_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(other_athlete)
        await test_db_session.commit()

        await _create_fitness(
            session=test_db_session,
            athlete_id=other_athlete.id,
            metric_date=date(2024, 1, 1),
        )
        await _create_fitness(
            session=test_db_session,
            athlete_id=other_athlete.id,
            metric_date=date(2024, 2, 1),
        )

        # Count should only include the original athlete's records
        count = await fitness_repo.count_by_athlete(athlete.id)

        assert count == 1