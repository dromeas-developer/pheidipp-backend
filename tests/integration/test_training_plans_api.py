"""Integration tests for training plan API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import TrainingPlanStatus
from app.models.training_plan import TrainingPlan
from app.repositories.training_plan_repository import TrainingPlanRepository
from tests.factories import (
    make_athlete,
    make_training_plan,
    make_planned_session,
)


class TestGetActiveTrainingPlan:
    @pytest.mark.asyncio
    async def test_get_active_returns_404_when_no_plan_exists(
        self, client: AsyncClient, test_athlete
    ):
        athlete_id = test_athlete.id
        response = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_active_returns_200_with_plan_when_active_plan_exists(
        self, client: AsyncClient, test_athlete, test_db_session: AsyncSession
    ):
        athlete_id = test_athlete.id
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert response.status_code == 200
        data = response.json()
        assert "training_plan" in data
        assert data["training_plan"]["athlete_id"] == str(athlete_id)

    @pytest.mark.asyncio
    async def test_get_active_response_includes_training_plan_and_sessions(
        self, client: AsyncClient, test_athlete, test_db_session: AsyncSession
    ):
        athlete_id = test_athlete.id
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        session = make_planned_session(training_plan_id=plan.id)
        test_db_session.add(session)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/active")
        assert response.status_code == 200
        data = response.json()
        assert "training_plan" in data
        assert "planned_sessions" in data
        assert len(data["planned_sessions"]) >= 1


class TestGetTrainingPlanById:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_404_when_plan_not_found(
        self, client: AsyncClient, test_athlete
    ):
        athlete_id = test_athlete.id
        fake_id = uuid.uuid4()
        response = await client.get(f"/athletes/{athlete_id}/training-plans/{fake_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_by_id_returns_403_when_plan_belongs_to_different_athlete(
        self, client: AsyncClient, test_athlete, test_db_session: AsyncSession
    ):
        # Create plan for a different athlete
        other_athlete = make_athlete()
        test_db_session.add(other_athlete)
        await test_db_session.commit()

        plan = make_training_plan(athlete_id=other_athlete.id)
        test_db_session.add(plan)
        await test_db_session.commit()

        # Try to access as test_athlete
        response = await client.get(
            f"/athletes/{test_athlete.id}/training-plans/{plan.id}"
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_by_id_returns_200_for_correct_athlete(
        self, client: AsyncClient, test_athlete, test_db_session: AsyncSession
    ):
        athlete_id = test_athlete.id
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/{plan.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["training_plan"]["id"] == str(plan.id)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_sessions_ordered_by_date(
        self, client: AsyncClient, test_athlete, test_db_session: AsyncSession
    ):
        athlete_id = test_athlete.id
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        from datetime import date
        from app.models.enums import SessionType, PhysiologicalIntent, TrainingPhase

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
        ]
        for s in sessions:
            test_db_session.add(s)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/{plan.id}")
        assert response.status_code == 200
        data = response.json()
        sorted_sessions = sorted(
            data["planned_sessions"], key=lambda s: s["scheduled_date"]
        )
        assert data["planned_sessions"] == sorted_sessions