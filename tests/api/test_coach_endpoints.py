"""API tests for coach endpoints — real DB, mocked LLM proxy.

Covers the GET /athletes/{athlete_id}/coach/messages endpoint (ordering
by generated_at DESC, pagination via limit and offset) and the
POST /athletes/{athlete_id}/coach/first-message endpoint idempotency
via the HTTP layer (mapping FirstMessageAlreadyExistsError → 409).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.first_message_agent import FirstMessageAlreadyExistsError
from app.core.security.token_service import TokenService
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    DataTier,
    GoalEventType,
    GoalType,
    MessageType,
    RecoveryModifierLevel,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
    WeeklyPlanStatus,
)
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan


async def _issue_token(athlete_id: uuid.UUID) -> str:
    svc = TokenService()
    token, _ = svc.issue_access_token(athlete_id)
    return token


async def _auth_header(athlete_id: uuid.UUID) -> dict[str, str]:
    return {"Authorization": f"Bearer {await _issue_token(athlete_id)}"}


def _four_paragraph_content() -> str:
    return (
        "Welcome to your training journey.\n\n"
        "What was found: triathlon background with structural risk.\n\n"
        "The first block builds aerobic base with easy runs.\n\n"
        "Listen to your body and tell me when something feels off."
    )


async def _seed_athlete_with_first_message(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create an athlete, twin, plan and a single first_message."""
    from app.models.athlete import Athlete

    athlete = Athlete(
        email=f"coach-{uuid.uuid4()}@example.com",
        onboarding_complete=True,
    )
    db_session.add(athlete)
    await db_session.flush()

    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=GoalEventType.MARATHON,
        goal_event_date=date.today() + timedelta(weeks=20),
        goal_event_name="Berlin Marathon",
        weekly_volume_hours=8.0,
        weekly_volume_km=50.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    twin = TwinState(
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        data_tier=DataTier.TIER_3,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1-questionnaire-bootstrap",
        fitness=0.0,
        fatigue=0.0,
        form=0.0,
        readiness_level=RecoveryModifierLevel.GREEN,
    )
    db_session.add(twin)
    await db_session.flush()

    plan = TrainingPlan(
        training_goal_id=goal.id,
        status=TrainingPlanStatus.ACTIVE,
        twin_state_id=twin.id,
    )
    db_session.add(plan)
    await db_session.flush()

    wp = WeeklyPlan(
        training_plan_id=plan.id,
        week_number=1,
        adjusted_intent={},
        status=WeeklyPlanStatus.ACTIVE,
        week_starts_at=date.today(),
        week_ends_at=date.today() + timedelta(days=6),
    )
    db_session.add(wp)
    await db_session.commit()
    await db_session.refresh(athlete)
    return athlete.id, twin.id


class TestGetCoachMessages:
    async def test_messages_ordered_by_generated_at_desc(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        athlete_id, twin_id = await _seed_athlete_with_first_message(db_session)

        # Use MessageType.WELLNESS_ALERT (not FIRST_MESSAGE) so multiple
        # rows per athlete don't violate the partial unique index
        # ``uq_coaching_messages_athlete_first_message``.
        for hours_ago in (3, 2, 1):
            msg = CoachingMessage(
                athlete_id=athlete_id,
                twin_state_id=twin_id,
                message_type=MessageType.WELLNESS_ALERT,
                content=f"Message {hours_ago}h ago",
                prompt_version="v1",
                generated_at=datetime.now(timezone.utc) - timedelta(hours=hours_ago),
            )
            db_session.add(msg)
        await db_session.commit()

        response = await client.get(
            f"/athletes/{athlete_id}/coach/messages",
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 3

        generated_at_list = [
            m["generated_at"] for m in data["messages"]
        ]
        assert generated_at_list == sorted(generated_at_list, reverse=True)

    async def test_pagination_with_limit_and_offset(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        athlete_id, twin_id = await _seed_athlete_with_first_message(db_session)

        # Use MessageType.WELLNESS_ALERT (not FIRST_MESSAGE) so multiple
        # rows per athlete don't violate the partial unique index
        # ``uq_coaching_messages_athlete_first_message``.
        for i in range(10):
            msg = CoachingMessage(
                athlete_id=athlete_id,
                twin_state_id=twin_id,
                message_type=MessageType.WELLNESS_ALERT,
                content=f"Message {i}",
                prompt_version="v1",
                generated_at=datetime.now(timezone.utc) - timedelta(minutes=i),
            )
            db_session.add(msg)
        await db_session.commit()

        response = await client.get(
            f"/athletes/{athlete_id}/coach/messages",
            params={"limit": 5, "offset": 2},
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["messages"]) == 5
        assert data["total"] == 10

    async def test_message_type_filter_returns_only_that_type(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        athlete_id, twin_id = await _seed_athlete_with_first_message(db_session)

        # Filter test uses POST_WORKOUT + WELLNESS_ALERT (not FIRST_MESSAGE)
        # so multiple rows per athlete do not violate
        # ``uq_coaching_messages_athlete_first_message``. POST_WORKOUT
        # without ``activity_id`` is exempt from its partial unique index.
        for i in range(3):
            db_session.add(
                CoachingMessage(
                    athlete_id=athlete_id,
                    twin_state_id=twin_id,
                    message_type=MessageType.POST_WORKOUT,
                    content=f"post {i}",
                    prompt_version="v1",
                )
            )
        for i in range(2):
            db_session.add(
                CoachingMessage(
                    athlete_id=athlete_id,
                    twin_state_id=twin_id,
                    message_type=MessageType.WELLNESS_ALERT,
                    content=f"wellness {i}",
                    prompt_version="v1",
                )
            )
        await db_session.commit()

        response = await client.get(
            f"/athletes/{athlete_id}/coach/messages",
            params={"message_type": "post_workout"},
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert all(
            m["message_type"] == "post_workout" for m in data["messages"]
        )

    async def test_empty_messages_returns_empty_list_with_zero_total(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        from app.models.athlete import Athlete

        athlete = Athlete(email=f"empty-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.commit()
        await db_session.refresh(athlete)

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages",
            headers=await _auth_header(athlete.id),
        )

        assert response.status_code == 200
        data = response.json()
        assert data["messages"] == []
        assert data["total"] == 0

    async def test_cross_athlete_request_returns_403(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        athlete_id, _ = await _seed_athlete_with_first_message(db_session)

        other_id = uuid.uuid4()
        response = await client.get(
            f"/athletes/{other_id}/coach/messages",
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 403


class TestPostFirstMessageEndpoint:
    async def test_first_post_returns_201(
        self, db_session: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _seed_athlete_with_first_message(db_session)

        from app.agents.first_message_agent import FirstMessageAgent

        async def _fake_generate(self: Any, athlete_id_arg: uuid.UUID) -> Any:
            from app.schemas.coaching import CoachingMessageResponse

            stmt = __import__("sqlalchemy").select(TwinState).where(
                TwinState.athlete_id == athlete_id_arg
            )
            twin = (
                await db_session.execute(stmt)
            ).scalars().first()

            return CoachingMessageResponse(
                id=uuid.uuid4(),
                message_type="first_message",
                content=_four_paragraph_content(),
                generated_at=datetime.now(timezone.utc),
                prompt_version="v1",
                twin_state_id=twin.id if twin else uuid.uuid4(),
            )

        monkeypatch.setattr(FirstMessageAgent, "generate", _fake_generate)

        response = await client.post(
            f"/athletes/{athlete_id}/coach/first-message",
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 201
        data = response.json()
        assert data["message_type"] == "first_message"

    async def test_second_post_returns_409(
        self, db_session: AsyncSession, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, twin_id = await _seed_athlete_with_first_message(db_session)

        existing = CoachingMessage(
            athlete_id=athlete_id,
            twin_state_id=twin_id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Existing first message",
            prompt_version="v1",
        )
        db_session.add(existing)
        await db_session.commit()
        await db_session.refresh(existing)

        from app.agents.first_message_agent import FirstMessageAgent

        async def _raise_conflict(self: Any, athlete_id_arg: uuid.UUID) -> Any:
            raise FirstMessageAlreadyExistsError(existing_message_id=existing.id)

        monkeypatch.setattr(FirstMessageAgent, "generate", _raise_conflict)

        response = await client.post(
            f"/athletes/{athlete_id}/coach/first-message",
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 409
        # FastAPI wraps HTTPException(detail={...}) under a top-level
        # ``detail`` key, so the conflict body lives at data["detail"].
        data = response.json()
        assert data["detail"]["existing_message_id"] == str(existing.id)

    async def test_cross_athlete_first_message_returns_403(
        self, db_session: AsyncSession, client: AsyncClient
    ) -> None:
        athlete_id, _ = await _seed_athlete_with_first_message(db_session)
        other_id = uuid.uuid4()

        response = await client.post(
            f"/athletes/{other_id}/coach/first-message",
            headers=await _auth_header(athlete_id),
        )

        assert response.status_code == 403