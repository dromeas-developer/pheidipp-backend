"""Unit tests for PlannedSessionRepository."""

import uuid
from datetime import date

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.planned_session import PlannedSession
from app.models.training_plan import TrainingPlan
from app.models.athlete import Athlete
from app.models.enums import SessionType, PhysiologicalIntent, TrainingPhase, AthleteStatus
from app.repositories.planned_session_repository import PlannedSessionRepository
from tests.factories import make_planned_session, make_planned_session_batch


@pytest.fixture
def repo(test_db_session: AsyncSession) -> PlannedSessionRepository:
    return PlannedSessionRepository(test_db_session)


class TestPlannedSessionRepositoryCreate:
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

        plan = TrainingPlan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        session = await repo.create(
            training_plan_id=plan.id,
            scheduled_date=date(2024, 1, 15),
            session_type=SessionType.EASY_RUN,
            dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            week_number=1,
            phase=TrainingPhase.BASE,
        )

        assert session.id is not None
        assert session.training_plan_id == plan.id
        assert session.session_type == SessionType.EASY_RUN


class TestPlannedSessionRepositoryListByPlan:
    @pytest.mark.asyncio
    async def test_list_by_plan_returns_sessions_ordered_by_date(
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

        plan = TrainingPlan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        sessions_data = [
            {
                "training_plan_id": plan.id,
                "scheduled_date": date(2024, 1, 20),
                "session_type": SessionType.LONG_RUN,
                "dominant_physiological_intent": PhysiologicalIntent.HIGH_AEROBIC,
                "week_number": 3,
                "phase": TrainingPhase.BASE,
            },
            {
                "training_plan_id": plan.id,
                "scheduled_date": date(2024, 1, 15),
                "session_type": SessionType.EASY_RUN,
                "dominant_physiological_intent": PhysiologicalIntent.LOW_AEROBIC,
                "week_number": 2,
                "phase": TrainingPhase.BASE,
            },
        ]
        sessions = [PlannedSession(**d) for d in sessions_data]
        for s in sessions:
            test_db_session.add(s)
        await test_db_session.flush()

        result = await repo.list_by_plan(plan.id)

        assert len(result) == 2
        assert result[0].scheduled_date == date(2024, 1, 15)
        assert result[1].scheduled_date == date(2024, 1, 20)

    @pytest.mark.asyncio
    async def test_list_by_plan_returns_empty_list_when_no_sessions(self, repo):
        result = await repo.list_by_plan(uuid.uuid4())
        assert result == []


class TestPlannedSessionRepositoryBulkCreate:
    @pytest.mark.asyncio
    async def test_bulk_create_creates_multiple_sessions(self, repo, test_db_session: AsyncSession):
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

        sessions_data = [
            {
                "training_plan_id": plan.id,
                "scheduled_date": date(2024, 1, 15),
                "session_type": SessionType.EASY_RUN,
                "dominant_physiological_intent": PhysiologicalIntent.LOW_AEROBIC,
                "week_number": 1,
                "phase": TrainingPhase.BASE,
            },
            {
                "training_plan_id": plan.id,
                "scheduled_date": date(2024, 1, 17),
                "session_type": SessionType.THRESHOLD,
                "dominant_physiological_intent": PhysiologicalIntent.THRESHOLD,
                "week_number": 1,
                "phase": TrainingPhase.BASE,
            },
        ]

        result = await repo.bulk_create(sessions_data)
        await test_db_session.flush()

        assert len(result) == 2
        for session in result:
            assert session.id is not None

    @pytest.mark.asyncio
    async def test_bulk_create_with_empty_list_returns_empty_list(self, repo):
        result = await repo.bulk_create([])
        assert result == []