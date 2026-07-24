"""API tests for the coach message endpoints with the async-generation flow.

The Phase-2.7 Batch 3 plan introduces a ``generate_first_message``
procrastinate worker task that runs after the ``generate_plan`` task
completes. The ``POST /coach/first-message`` endpoint remains as a
manual retry:

* If the async task already created the message → 409 with the
  existing message ID (no second LLM call).
* If the async task has not run → 201 with a new message (the
  endpoint is the fallback).

These tests exercise the contract end-to-end through the public HTTP
surface, with the agent mocked at the API layer (the same pattern as
the existing ``tests/integration/test_coach_endpoints.py``).

Reference plan: ``docs/implementation/phase-2/phase-2-7/batch-3-event-flow-plan-router-fix.md``
Scenarios 16–18.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.first_message_agent import (
    FirstMessageAlreadyExistsError,
)
from app.core.security.token_service import TokenService
from app.models.athlete import Athlete
from app.models.athlete_auth import AthleteAuth
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    AuthProvider,
    DataTier,
    GoalEventType,
    GoalType,
    MessageType,
    RecoveryModifierLevel,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState


_FOUR_PARA_CONTENT = (
    "Welcome to your coaching journey.\n\n"
    "I see you have a running background with limited history on record.\n\n"
    "Your plan is structured in two phases over 8 weeks.\n\n"
    "The first block focuses on building your aerobic base."
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _create_athlete_with_onboarding(
    db_session: AsyncSession,
    email: str | None = None,
) -> tuple[Athlete, TrainingGoal, TwinState, TrainingPlan]:
    """Create a fully-onboarded athlete (auth + goal + twin_state + plan)
    so the manual /coach/first-message endpoint has the preconditions
    it needs. Mirrors the helper in tests/integration/test_coach_endpoints.py.
    """
    if email is None:
        email = f"coach-async-{uuid.uuid4()}@example.com"
    athlete = Athlete(email=email)
    db_session.add(athlete)
    await db_session.flush()

    auth = AthleteAuth(
        athlete_id=athlete.id,
        provider=AuthProvider.EMAIL,
        is_primary=True,
    )
    db_session.add(auth)

    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=GoalEventType.FIVE_K,
        goal_event_date=date(2026, 9, 1),
        goal_description="Run a 5K race",
        weekly_volume_hours=5.0,
        weekly_volume_km=30.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    twin = TwinState(
        athlete_id=athlete.id,
        training_goal_id=goal.id,
        data_tier=DataTier.TIER_5,
        confidence_level=TwinConfidenceLevel.LOW,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1.0",
        fitness=0.0,
        fatigue=0.0,
        form=0.0,
        readiness_level=RecoveryModifierLevel.GREEN,
        metric_confidence={},
    )
    db_session.add(twin)
    await db_session.flush()

    plan = TrainingPlan(
        training_goal_id=goal.id,
        twin_state_id=twin.id,
        status=TrainingPlanStatus.ACTIVE,
        phases_summary=[],
        phase_definitions=[],
        weekly_distributions=[],
        checkpoint_schedule=[],
    )
    db_session.add(plan)
    await db_session.flush()

    return athlete, goal, twin, plan


def _auth_header(athlete_id: uuid.UUID, token_service: TokenService) -> dict[str, str]:
    token, _exp = token_service.issue_access_token(
        athlete_id=athlete_id,
        auth_provider=AuthProvider.EMAIL,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Scenario 16: GET /coach/messages after async generation.
# ---------------------------------------------------------------------------


class TestGetCoachMessagesAfterAsyncGeneration:
    """After the async ``generate_first_message`` task has created a
    message, ``GET /coach/messages`` returns it with
    ``message_type=first_message``."""

    async def test_get_messages_returns_first_message(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        first_message = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content=_FOUR_PARA_CONTENT,
            prompt_version="v1",
        )
        db_session.add(first_message)
        await db_session.flush()

        response = await client.get(
            f"/api/v1/athletes/{athlete.id}/coach/messages",
            headers=_auth_header(athlete.id, token_service),
        )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert len(body["messages"]) == 1
        assert body["messages"][0]["message_type"] == "first_message"


# ---------------------------------------------------------------------------
# Scenario 17: POST /coach/first-message returns 409 if async already ran.
# ---------------------------------------------------------------------------


class TestManualFirstMessageReturns409IfAsyncAlreadyRan:
    """If the async ``generate_first_message`` task already created
    the message, ``POST /coach/first-message`` returns 409 with the
    existing message ID — no second LLM call."""

    async def test_409_with_existing_message_id(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)

        existing = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Async-generated first message",
            prompt_version="v1",
        )
        db_session.add(existing)
        await db_session.flush()

        with patch("app.api.v1.coach.FirstMessageAgent") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.side_effect = FirstMessageAlreadyExistsError(
                existing.id
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/api/v1/athletes/{athlete.id}/coach/first-message",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 409, response.text
        detail = response.json()["detail"]
        assert detail["existing_message_id"] == str(existing.id)
        assert detail["message_type"] == "first_message"
        mock_instance.generate.assert_awaited_once()


# ---------------------------------------------------------------------------
# Scenario 18: POST /coach/first-message returns 201 if async has not run.
# ---------------------------------------------------------------------------


class TestManualFirstMessageReturns201IfAsyncHasNotRun:
    """When the async task has not run, ``POST /coach/first-message``
    returns 201 with a new ``CoachingMessage`` — the manual endpoint
    is the fallback."""

    async def test_201_with_new_message(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        expected_id = uuid.uuid4()
        with patch("app.api.v1.coach.FirstMessageAgent") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.return_value = MagicMock(
                id=expected_id,
                message_type="first_message",
                content=_FOUR_PARA_CONTENT,
                generated_at=datetime.now(timezone.utc),
                prompt_version="v1",
                twin_state_id=twin.id,
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/api/v1/athletes/{athlete.id}/coach/first-message",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 201, response.text
        body = response.json()
        assert body["id"] == str(expected_id)
        assert body["message_type"] == "first_message"
        mock_instance.generate.assert_awaited_once()
