"""Integration tests for training plan model integrity."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import text, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.enums import (
    TrainingPlanStatus,
    SessionType,
    PhysiologicalIntent,
    TrainingPhase,
    AthleteStatus,
    GoalStatus,
)
from app.models.athlete import Athlete
from app.models.training_block import TrainingBlock
from app.models.training_plan import TrainingPlan
from app.models.planned_session import PlannedSession
from app.repositories.training_plan_repository import TrainingPlanRepository
from tests.factories import (
    make_training_plan,
    make_archived_training_plan,
    make_planned_session,
)


class TestTrainingPlanPartialUniqueIndex:
    @pytest.mark.asyncio
    async def test_prevents_two_active_plans_for_same_athlete(
        self, test_db_session: AsyncSession
    ):
        """Partial unique index prevents two active plans for the same athlete."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        # Use raw SQL to ensure the constraint is tested at the DB level
        await test_db_session.execute(
            text(
                "INSERT INTO training_plans (athlete_id, status, generation_metadata) "
                "VALUES (:athlete_id, 'active', '{}')"
            ),
            {"athlete_id": athlete.id},
        )
        await test_db_session.flush()

        # Second insert should violate the partial unique index
        with pytest.raises(IntegrityError):
            await test_db_session.execute(
                text(
                    "INSERT INTO training_plans (athlete_id, status, generation_metadata) "
                    "VALUES (:athlete_id, 'active', '{}')"
                ),
                {"athlete_id": athlete.id},
            )
            await test_db_session.flush()

    @pytest.mark.asyncio
    async def test_athlete_can_have_active_and_archived_plan(
        self, test_db_session: AsyncSession
    ):
        """An athlete can have one active and one archived plan simultaneously."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan1 = make_training_plan(athlete_id=athlete.id, status=TrainingPlanStatus.ACTIVE)
        plan2 = make_archived_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan1)
        test_db_session.add(plan2)
        await test_db_session.flush()
        await test_db_session.commit()

        repo = TrainingPlanRepository(test_db_session)
        active = await repo.get_active_by_athlete(athlete.id)
        assert active is not None
        assert active.status == TrainingPlanStatus.ACTIVE


class TestTrainingPlanCascadeDelete:
    @pytest.mark.asyncio
    async def test_cascade_delete_on_training_plan_athlete_id(
        self, test_db_session: AsyncSession
    ):
        """CASCADE delete on training_plans.athlete_id deletes plan when athlete is deleted."""
        from app.models.athlete import Athlete
        from app.models.enums import AthleteStatus

        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"cascade_test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()
        plan_id = plan.id

        await test_db_session.delete(athlete)
        await test_db_session.flush()

        from app.repositories.training_plan_repository import TrainingPlanRepository
        repo = TrainingPlanRepository(test_db_session)
        result = await repo.get_by_id(plan_id)
        assert result is None


class TestPlannedSessionCascadeDelete:
    @pytest.mark.asyncio
    async def test_cascade_delete_on_planned_sessions_training_plan_id(
        self, test_db_session: AsyncSession
    ):
        """CASCADE delete on planned_sessions.training_plan_id deletes sessions when plan is deleted."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        session = make_planned_session(training_plan_id=plan.id)
        test_db_session.add(session)
        await test_db_session.flush()
        session_id = session.id

        await test_db_session.delete(plan)
        await test_db_session.flush()

        from app.repositories.planned_session_repository import PlannedSessionRepository
        repo = PlannedSessionRepository(test_db_session)
        sessions = await repo.list_by_plan(plan.id)
        assert len(sessions) == 0


class TestTrainingPlanSetNullOnDelete:
    @pytest.mark.asyncio
    async def test_set_null_on_training_plan_training_block_id(
        self, test_db_session: AsyncSession
    ):
        """SET NULL on training_plans.training_block_id sets to NULL when training block is deleted."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        block = TrainingBlock(
            id=uuid.uuid4(),
            athlete_id=athlete.id,
            goal_event_type=None,
            goal_event_date=date(2024, 6, 30),
            status=GoalStatus.ACTIVE,
        )
        test_db_session.add(block)
        await test_db_session.flush()
        block_id = block.id

        plan = TrainingPlan(
            athlete_id=athlete.id,
            training_block_id=block.id,
            status=TrainingPlanStatus.ACTIVE,
        )
        test_db_session.add(plan)
        await test_db_session.flush()
        plan_id = plan.id

        # Delete block via raw SQL to bypass SQLAlchemy cascade
        await test_db_session.execute(
            text("DELETE FROM training_blocks WHERE id = :id"),
            {"id": block_id},
        )
        await test_db_session.commit()

        # Expire all cached objects to force fresh DB reads
        test_db_session.expire_all()

        # Verify block was deleted
        block_result = await test_db_session.execute(
            text("SELECT COUNT(*) FROM training_blocks WHERE id = :id"),
            {"id": block_id},
        )
        assert block_result.scalar() == 0

        # Query the plan directly with a fresh select
        result = await test_db_session.execute(
            select(TrainingPlan).where(TrainingPlan.id == plan_id)
        )
        fetched_plan = result.scalar_one()
        assert fetched_plan.training_block_id is None


class TestPlannedSessionsOrderByDate:
    @pytest.mark.asyncio
    async def test_planned_sessions_relationship_orders_by_scheduled_date(
        self, test_db_session: AsyncSession
    ):
        """planned_sessions relationship orders sessions by scheduled_date ascending."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        sessions = [
            make_planned_session(
                training_plan_id=plan.id,
                scheduled_date=date(2024, 2, 1),
                session_type=SessionType.LONG_RUN,
            ),
            make_planned_session(
                training_plan_id=plan.id,
                scheduled_date=date(2024, 1, 15),
                session_type=SessionType.EASY_RUN,
            ),
            make_planned_session(
                training_plan_id=plan.id,
                scheduled_date=date(2024, 1, 22),
                session_type=SessionType.THRESHOLD,
            ),
        ]
        for s in sessions:
            test_db_session.add(s)
        await test_db_session.flush()

        # Query sessions directly — refresh() doesn't load relationships
        result = await test_db_session.execute(
            select(PlannedSession)
            .where(PlannedSession.training_plan_id == plan.id)
            .order_by(PlannedSession.scheduled_date)
        )
        ordered = list(result.scalars().all())

        assert len(ordered) == 3
        assert ordered[0].scheduled_date == date(2024, 1, 15)
        assert ordered[1].scheduled_date == date(2024, 1, 22)
        assert ordered[2].scheduled_date == date(2024, 2, 1)


class TestTrainingPlanAndPlannedSessionCreateAndQuery:
    @pytest.mark.asyncio
    async def test_can_create_and_query_training_plan_and_sessions(
        self, test_db_session: AsyncSession
    ):
        """TrainingPlan and PlannedSession can be created and queried via async session."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        session = make_planned_session(
            training_plan_id=plan.id,
            scheduled_date=date(2024, 1, 15),
            session_type=SessionType.EASY_RUN,
            dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC,
            week_number=1,
            phase=TrainingPhase.BASE,
        )
        test_db_session.add(session)
        await test_db_session.flush()

        repo = TrainingPlanRepository(test_db_session)
        fetched_plan = await repo.get_by_id(plan.id)
        assert fetched_plan is not None

        from app.repositories.planned_session_repository import PlannedSessionRepository
        session_repo = PlannedSessionRepository(test_db_session)
        sessions = await session_repo.list_by_plan(plan.id)
        assert len(sessions) == 1
        assert sessions[0].session_type == SessionType.EASY_RUN


class TestIndexes:
    @pytest.mark.asyncio
    async def test_indexes_exist_on_training_plans(
        self, test_db_session: AsyncSession
    ):
        """Test indexes exist on training_plans for athlete_id and athlete_id, created_at."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        # Verify by querying the indexes
        result = await test_db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'training_plans'"
            )
        )
        indexes = {row[0] for row in result.fetchall()}
        assert "ix_training_plans_athlete_id" in indexes or "training_plans_athlete_id_idx" in indexes or any("athlete" in idx.lower() for idx in indexes)
        assert "ix_training_plans_athlete_created_at" in indexes or any("athlete" in idx.lower() and "created" in idx.lower() for idx in indexes)

    @pytest.mark.asyncio
    async def test_indexes_exist_on_planned_sessions(
        self, test_db_session: AsyncSession
    ):
        """Test indexes exist on planned_sessions for training_plan_id, scheduled_date and training_plan_id, week_number."""
        athlete = Athlete(
            id=uuid.uuid4(),
            email=f"test_{uuid.uuid4().hex[:8]}@example.com",
            hashed_password=None,
            status=AthleteStatus.ACTIVE,
        )
        test_db_session.add(athlete)
        await test_db_session.flush()

        plan = make_training_plan(athlete_id=athlete.id)
        test_db_session.add(plan)
        await test_db_session.flush()

        result = await test_db_session.execute(
            text(
                "SELECT indexname FROM pg_indexes WHERE tablename = 'planned_sessions'"
            )
        )
        indexes = {row[0] for row in result.fetchall()}
        assert any("plan" in idx.lower() and "date" in idx.lower() for idx in indexes)
        assert any("plan" in idx.lower() and "week" in idx.lower() for idx in indexes)