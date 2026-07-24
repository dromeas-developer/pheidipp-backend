"""Integration tests for the coach message API endpoints.

Tests the full HTTP surface for Phase-1.5a:
- POST /athletes/{athlete_id}/coach/first-message
- GET /athletes/{athlete_id}/coach/messages

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
from app.repositories.coaching_message_repository import CoachingMessageRepository
from app.repositories.generation_event_repository import GenerationEventRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.context_budget_service import ContextBudgetService
from app.agents.first_message_agent import FirstMessageAgent
from app.core.prompt_registry import PromptRegistry


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


async def _create_athlete_with_onboarding(
    db_session: AsyncSession, email: str | None = None
) -> tuple[Athlete, TrainingGoal, TwinState, TrainingPlan]:
    """Create a fully-onboarded athlete (auth + goal + twin_state + plan)."""
    if email is None:
        email = f"onboarded-{uuid.uuid4()}@example.com"
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
    """Return a valid Bearer JWT for the athlete."""
    token, _exp = token_service.issue_access_token(
        athlete_id=athlete_id,
        auth_provider=AuthProvider.EMAIL,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# POST /athletes/{id}/coach/first-message
# ---------------------------------------------------------------------------


class TestPostFirstMessage:
    """Tests for the first message generation endpoint."""

    @pytest.mark.asyncio
    async def test_201_on_successful_generation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        four_para_content = (
            "Welcome to your coaching journey.\n\n"
            "I see you have a running background with limited history on record.\n\n"
            "Your plan is structured in two phases over 8 weeks.\n\n"
            "The first block focuses on building your aerobic base."
        )

        with patch("app.api.v1.coach.FirstMessageAgent") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.return_value = MagicMock(
                id=uuid.uuid4(),
                message_type="first_message",
                content=four_para_content,
                generated_at=datetime.now(timezone.utc),
                prompt_version="v1",
                twin_state_id=twin.id,
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/athletes/{athlete.id}/coach/first-message",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 201
        data = response.json()
        assert data["message_type"] == "first_message"
        assert "id" in data
        assert "content" in data

    @pytest.mark.asyncio
    async def test_409_on_duplicate_call(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        existing_message = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Already generated first message",
            prompt_version="v1",
        )
        db_session.add(existing_message)
        await db_session.flush()

        from app.agents.first_message_agent import FirstMessageAlreadyExistsError

        with patch("app.api.v1.coach.FirstMessageAgent") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.side_effect = FirstMessageAlreadyExistsError(
                existing_message.id
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/athletes/{athlete.id}/coach/first-message",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 409
        data = response.json()
        assert "existing_message_id" in data["detail"]
        assert data["detail"]["message_type"] == "first_message"

    @pytest.mark.asyncio
    async def test_503_on_llm_failure(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        from app.agents.first_message_agent import LLMServiceUnavailableError

        with patch("app.api.v1.coach.FirstMessageAgent") as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.side_effect = LLMServiceUnavailableError(
                "LLM call failed"
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/athletes/{athlete.id}/coach/first-message",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        response = await client.post(
            f"/athletes/{athlete.id}/coach/first-message",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_403_accessing_different_athlete(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete1, *_ = await _create_athlete_with_onboarding(
            db_session, f"athlete1-{uuid.uuid4()}@example.com"
        )
        athlete2, *_ = await _create_athlete_with_onboarding(
            db_session, f"athlete2-{uuid.uuid4()}@example.com"
        )
        await db_session.flush()

        # athlete1 tries to generate for athlete2
        response = await client.post(
            f"/athletes/{athlete2.id}/coach/first-message",
            headers=_auth_header(athlete1.id, token_service),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# GET /athletes/{id}/coach/messages
# ---------------------------------------------------------------------------


class TestGetCoachMessages:
    """Tests for the messages list endpoint."""

    @pytest.mark.asyncio
    async def test_200_with_message_list(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        # Create some messages
        msg1 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="First message content",
            prompt_version="v1",
        )
        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.WELLNESS_ALERT,
            content="Wellness check-in",
            prompt_version="v1",
        )
        db_session.add_all([msg1, msg2])
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages",
            headers=_auth_header(athlete.id, token_service),
        )

        assert response.status_code == 200
        data = response.json()
        assert "messages" in data
        assert "total" in data
        assert data["total"] == 2
        assert len(data["messages"]) == 2

    @pytest.mark.asyncio
    async def test_messages_ordered_by_generated_at_desc(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        msg1 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="First message",
            prompt_version="v1",
        )
        db_session.add(msg1)
        await db_session.flush()

        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.WELLNESS_ALERT,
            content="Second message",
            prompt_version="v1",
        )
        db_session.add(msg2)
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages",
            headers=_auth_header(athlete.id, token_service),
        )

        data = response.json()
        # Newest first (msg2 was created after msg1)
        messages = data["messages"]
        assert messages[0]["content"] == "Second message"
        assert messages[1]["content"] == "First message"

    @pytest.mark.asyncio
    async def test_filter_by_message_type(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        msg1 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="First message",
            prompt_version="v1",
        )
        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.WELLNESS_ALERT,
            content="Wellness",
            prompt_version="v1",
        )
        db_session.add_all([msg1, msg2])
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages?message_type=first_message",
            headers=_auth_header(athlete.id, token_service),
        )

        data = response.json()
        assert data["total"] == 1
        assert data["messages"][0]["message_type"] == "first_message"

    @pytest.mark.asyncio
    async def test_limit_param(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        for i in range(5):
            msg = CoachingMessage(
                athlete_id=athlete.id,
                twin_state_id=twin.id,
                message_type=MessageType.WELLNESS_ALERT,
                content=f"Message {i}",
                prompt_version="v1",
            )
            db_session.add(msg)
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages?limit=3",
            headers=_auth_header(athlete.id, token_service),
        )

        data = response.json()
        assert data["total"] == 5
        assert len(data["messages"]) == 3

    @pytest.mark.asyncio
    async def test_offset_param(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        for i in range(5):
            msg = CoachingMessage(
                athlete_id=athlete.id,
                twin_state_id=twin.id,
                message_type=MessageType.WELLNESS_ALERT,
                content=f"Message {i}",
                prompt_version="v1",
            )
            db_session.add(msg)
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages?offset=3",
            headers=_auth_header(athlete.id, token_service),
        )

        data = response.json()
        assert data["total"] == 5
        assert len(data["messages"]) == 2  # 5 - 3 offset

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/coach/messages",
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_403_accessing_different_athlete(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete1, *_ = await _create_athlete_with_onboarding(
            db_session, f"athlete1-{uuid.uuid4()}@example.com"
        )
        athlete2, *_ = await _create_athlete_with_onboarding(
            db_session, f"athlete2-{uuid.uuid4()}@example.com"
        )
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete2.id}/coach/messages",
            headers=_auth_header(athlete1.id, token_service),
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Generation event integrity.
# ---------------------------------------------------------------------------


class TestGenerationEventIntegrity:
    """Every CoachingMessage must have a corresponding GenerationEvent."""

    @pytest.mark.asyncio
    async def test_generation_event_written_on_success(
        self,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        four_para_content = (
            "Para one.\n\nPara two.\n\nPara three.\n\nPara four."
        )

        # Build agent with all real dependencies except LLM (patched).
        coaching_messages_repo = CoachingMessageRepository(session=db_session)
        generation_events_repo = GenerationEventRepository(session=db_session)
        twin_states_repo = TwinStateRepository(session=db_session)
        training_goals_repo = TrainingGoalRepository(session=db_session)
        # Configure get_latest to return the twin created by _create_athlete_with_onboarding.
        # Without this, the repo query may not see the unflushed twin due to transaction
        # isolation, causing build_first_message_context to receive a MagicMock instead
        # of a real TwinState and fail on twin_state.form >= 0.
        twin_states_repo.get_latest = AsyncMock(return_value=twin)
        plans_repo = TrainingPlanRepository(session=db_session)
        profiles_repo = AthleteProfileRepository(session=db_session)
        preferences_repo = AthletePreferencesRepository(session=db_session)
        context_budget = ContextBudgetService(
            twin_states=twin_states_repo,
            training_goals=training_goals_repo,
            plans=plans_repo,
            profiles=profiles_repo,
            preferences=preferences_repo,
        )
        prompt_registry = PromptRegistry()

        with patch(
            "app.agents.first_message_agent.FirstMessageAgent._build_llm_client"
        ) as mock_build_llm:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(
                return_value=MagicMock(
                    usage=MagicMock(total_tokens=150),
                    choices=[
                        MagicMock(
                            message=MagicMock(content=four_para_content)
                        )
                    ],
                )
            )
            mock_build_llm.return_value = mock_client

            with patch("app.core.prompt_registry.PromptRegistry.get_prompt") as mock_get_prompt:
                mock_get_prompt.return_value = "You are the coach."

                agent = FirstMessageAgent(
                    session=db_session,
                    coaching_messages=coaching_messages_repo,
                    generation_events=generation_events_repo,
                    context_budget=context_budget,
                    prompt_registry=prompt_registry,
                    training_goals=training_goals_repo,
                    plans=plans_repo,
                    twin_states=twin_states_repo,
                )
                await agent.generate(athlete.id)

        # Check GenerationEvent was written
        gen_repo = GenerationEventRepository(session=db_session)
        events = await gen_repo.get_by_athlete_id(athlete.id)
        assert len(events) == 1
        assert events[0].agent_name == "FirstMessageAgent"
        assert events[0].success is True


# ---------------------------------------------------------------------------
# Voice compliance helpers.
# ---------------------------------------------------------------------------


class TestVoiceComplianceHelpers:
    """Helper assertions for voice compliance checks.

    These are reusable patterns for checking:
    - No bullet points (lines starting with - or *)
    - No headers (lines starting with #)
    - No emojis
    - No generic affirmations
    - No unexplained acronyms
    """

    def _has_bullets(self, content: str) -> bool:
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("-") or stripped.startswith("*"):
                return True
        return False

    def _has_headers(self, content: str) -> bool:
        lines = content.split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                return True
        return False

    def _has_emojis(self, content: str) -> bool:
        for char in content:
            if ord(char) > 127000:  # emoji range
                return True
        return False

    def _has_generic_affirmations(self, content: str) -> bool:
        lower = content.lower()
        affirmations = [
            "great job",
            "awesome",
            "you're making progress",
            "well done",
            "fantastic",
            "brilliant",
        ]
        return any(phrase in lower for phrase in affirmations)

    def test_bullet_detection(self) -> None:
        assert self._has_bullets("Here is a list:\n- item 1\n- item 2")
        assert not self._has_bullets("Normal paragraph text.")

    def test_header_detection(self) -> None:
        assert self._has_headers("# Introduction\nSome text")
        assert not self._has_headers("Normal paragraph text.")

    def test_emoji_detection(self) -> None:
        assert self._has_emojis("Hello 👋 world")
        assert not self._has_emojis("Hello world")

    def test_generic_affirmation_detection(self) -> None:
        assert self._has_generic_affirmations("Great job on your training!")
        assert not self._has_generic_affirmations(
            "Your training load is building well."
        )