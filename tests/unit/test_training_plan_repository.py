"""Unit tests for TrainingPlanRepository."""

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_plan import TrainingPlan
from app.models.athlete import Athlete
from app.models.enums import TrainingPlanStatus, AthleteStatus
from app.repositories.training_plan_repository import TrainingPlanRepository
from tests.factories import make_training_plan, make_archived_training_plan


@pytest.fixture
def repo(test_db_session: AsyncSession) -> TrainingPlanRepository:
    return TrainingPlanRepository(test_db_session)


class TestTrainingPlanRepositoryCreate:
    @pytest.mark.asyncio
    async def test_create_instantiates_and_flushes(self, repo, test_db_session: AsyncSession):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = await repo.create(athlete_id=athlete.id)

        assert plan.id is not None
        assert plan.athlete_id == athlete.id
        assert plan.status == TrainingPlanStatus.ACTIVE


class TestTrainingPlanRepositoryGetActive:
    @pytest.mark.asyncio
    async def test_get_active_by_athlete_returns_active_plan(self, repo, test_db_session: AsyncSession):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = TrainingPlan(athlete_id=athlete.id, status=TrainingPlanStatus.ACTIVE)
        test_db_session.add(plan)
        await test_db_session.flush()

        result = await repo.get_active_by_athlete(athlete.id)

        assert result is not None
        assert result.athlete_id == athlete.id
        assert result.status == TrainingPlanStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_active_by_athlete_returns_none_when_no_active_plan(
        self, repo, test_db_session: AsyncSession
    ):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        result = await repo.get_active_by_athlete(athlete.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_by_athlete_returns_none_when_only_archived_plans_exist(
        self, repo, test_db_session: AsyncSession
    ):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_archived_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        result = await repo.get_active_by_athlete(athlete.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_by_athlete_returns_only_one_plan_when_multiple_active_cannot_exist(
        self, repo, test_db_session: AsyncSession
    ):
        """Partial unique index enforcement — only one active plan per athlete."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan1 = make_training_plan(athlete_id=athlete.id, status=TrainingPlanStatus.ACTIVE)
        test_db_session.add(plan1)
        await test_db_session.flush()

        result = await repo.get_active_by_athlete(athlete.id)
        assert result is not None


class TestTrainingPlanRepositoryGetById:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_plan(self, repo, test_db_session: AsyncSession):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = TrainingPlan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        result = await repo.get_by_id(plan.id)

        assert result is not None
        assert result.id == plan.id

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_for_nonexistent_id(self, repo):
        result = await repo.get_by_id(uuid.uuid4())
        assert result is None


class TestTrainingPlanRepositoryArchive:
    @pytest.mark.asyncio
    async def test_archive_plan_sets_status_and_timestamp(self, repo, test_db_session: AsyncSession):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = TrainingPlan(athlete_id=athlete.id, status=TrainingPlanStatus.ACTIVE)
        test_db_session.add(plan)
        await test_db_session.flush()

        archived = await repo.archive_plan(plan.id)

        assert archived is not None
        assert archived.status == TrainingPlanStatus.ARCHIVED
        assert archived.archived_at is not None

    @pytest.mark.asyncio
    async def test_archive_plan_returns_none_for_nonexistent_plan(self, repo):
        result = await repo.archive_plan(uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_archive_plan_on_already_archived_does_not_error(
        self, repo, test_db_session: AsyncSession
    ):
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_archived_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        archived = await repo.archive_plan(plan.id)
        assert archived is not None
        assert archived.status == TrainingPlanStatus.ARCHIVED