"""Integration tests for training plan API endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import (
    make_training_plan,
    make_planned_session,
)


class TestGetActiveTrainingPlan:
    @pytest.mark.asyncio
    async def test_get_active_returns_404_when_no_plan_exists(
        self, client: AsyncClient, registered_athlete: dict
    ):
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]
        response = await client.get(f"/athletes/{athlete_id}/training-plans/active", headers=headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_active_returns_200_with_plan_when_active_plan_exists(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/active", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "training_plan" in data
        assert data["training_plan"]["athlete_id"] == str(athlete_id)

    @pytest.mark.asyncio
    async def test_get_active_response_includes_training_plan_and_sessions(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        session = make_planned_session(training_plan_id=plan.id)
        test_db_session.add(session)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/active", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "training_plan" in data
        assert "planned_sessions" in data
        assert len(data["planned_sessions"]) >= 1


class TestGetTrainingPlanById:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_404_when_plan_not_found(
        self, client: AsyncClient, registered_athlete: dict
    ):
        athlete_id = registered_athlete["athlete_id"]
        headers = registered_athlete["headers"]
        fake_id = uuid.uuid4()
        response = await client.get(f"/athletes/{athlete_id}/training-plans/{fake_id}", headers=headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_by_id_returns_403_when_plan_belongs_to_different_athlete(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]

        # Register a different athlete for cross-athlete testing
        email_b = f"cross_{uuid.uuid4().hex[:8]}@example.com"
        resp_b = await client.post("/auth/register", json={"email": email_b, "password": "secure-test-password-123"})
        assert resp_b.status_code == 201
        other_data = resp_b.json()
        other_id = uuid.UUID(other_data["athlete_id"])

        plan = make_training_plan(athlete_id=other_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        # Try to access as registered_athlete
        response = await client.get(
            f"/athletes/{athlete_id}/training-plans/{plan.id}", headers=headers
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_by_id_returns_200_for_correct_athlete(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]
        plan = make_training_plan(athlete_id=athlete_id)
        test_db_session.add(plan)
        await test_db_session.commit()

        response = await client.get(f"/athletes/{athlete_id}/training-plans/{plan.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["training_plan"]["id"] == str(plan.id)

    @pytest.mark.asyncio
    async def test_get_by_id_returns_sessions_ordered_by_date(
        self, client: AsyncClient, registered_athlete: dict, test_db_session: AsyncSession
    ):
        athlete_id = uuid.UUID(registered_athlete["athlete_id"])
        headers = registered_athlete["headers"]
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

        response = await client.get(f"/athletes/{athlete_id}/training-plans/{plan.id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        sorted_sessions = sorted(
            data["planned_sessions"], key=lambda s: s["scheduled_date"]
        )
        assert data["planned_sessions"] == sorted_sessions
