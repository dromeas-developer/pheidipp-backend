"""Integration tests for FirstMessageAgent — real DB, mocked LLM proxy.

Covers the agent's interaction with the real PostgreSQL test database
while stubbing the external LLM proxy at the AsyncOpenAI chat.completions
boundary. The agent's internal orchestration, repository calls, and
GenerationEvent writing run real per the mocking-contract rule that
only the external boundary is mocked.

Each test class monkeypatches ``FirstMessageAgent._build_llm_client``
to return an object whose ``chat.completions.create`` is an
``AsyncMock`` returning a configurable content string — so we can
exercise the success path, the timeout path, and the empty-response
path without hitting the network.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.first_message_agent import (
    FirstMessageAgent,
    FirstMessageAlreadyExistsError,
    LLMServiceUnavailableError,
)
from app.core.prompt_registry import PromptRegistry
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    DataTier,
    GoalEventType,
    GoalType,
    GpsSource,
    HrSource,
    MessageType,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    SportBackground,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
    WeeklyPlanStatus,
)
from app.models.generation_event import GenerationEvent
from app.models.system_event import SystemEvent, SystemEventOutbox
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from app.repositories.athlete_preferences_repository import (
    AthletePreferencesRepository,
)
from app.repositories.athlete_profile_repository import (
    AthleteProfileRepository,
)
from app.repositories.coaching_message_repository import (
    CoachingMessageRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.context_budget_service import ContextBudgetService


def _four_paragraph_content() -> str:
    return (
        "Welcome to your training journey. We have a marathon block "
        "ahead and we will build the aerobic base together.\n\n"
        "What was found: your profile indicates a triathlon background "
        "and a structural risk flag — we will be careful with load.\n\n"
        "The first block starts with easy aerobic work and short "
        "tempo touches so you can find rhythm without overload.\n\n"
        "Expect three to five runs a week; listen to your body and "
        "tell me when something feels off."
    )


def _llm_client_returning(content: str) -> MagicMock:
    """Build an AsyncOpenAI-shaped stub that returns *content*."""
    client = MagicMock()

    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.total_tokens = 123

    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def _llm_client_raising(exc: BaseException) -> MagicMock:
    """Build an AsyncOpenAI-shaped stub that raises *exc*."""
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=exc)
    return client


async def _build_full_setup(
    db_session: AsyncSession,
    *,
    data_tier: DataTier = DataTier.TIER_3,
    sport_background: SportBackground = SportBackground.TRIATHLON,
    structural_risk_flag: bool = True,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Set up an athlete + goal + plan + twin + preferences.

    Returns (athlete_id, twin_state_id). Mirrors the post-onboarding
    state so FirstMessageAgent preconditions are met.
    """
    from app.models.athlete import Athlete

    athlete_id = uuid.uuid4()
    athlete = Athlete(
        id=athlete_id,
        email=f"test-{athlete_id}@example.com",
        onboarding_complete=True,
    )
    db_session.add(athlete)

    goal = TrainingGoal(
        athlete_id=athlete_id,
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
        athlete_id=athlete_id,
        training_goal_id=goal.id,
        data_tier=data_tier,
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
        phases_summary=[
            {
                "label": "aerobic_base",
                "start_date": (date.today() + timedelta(days=1)).isoformat(),
                "end_date": (date.today() + timedelta(weeks=8)).isoformat(),
                "weeks": 8,
                "primary_focus": "build aerobic base",
                "weekly_session_count": 4,
            }
        ],
        weekly_distributions=[
            {
                "week_number": 1,
                "session_types": ["easy_run", "easy_run", "threshold", "long_run"],
                "primary_focus": "easy aerobic",
            },
            {
                "week_number": 2,
                "session_types": ["easy_run", "threshold", "easy_run", "long_run"],
                "primary_focus": "build threshold",
            },
        ],
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

    from app.models.athlete_preferences import AthletePreferences

    prefs = AthletePreferences(
        athlete_id=athlete_id,
        sport_background=sport_background,
        years_structured_training=3,
        training_time_of_day="morning",
        weekly_schedule={
            day: {
                "available": True,
                "max_hours": 1.5,
                "long_workout": False,
                "doubles_eligible": False,
            }
            for day in [
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ]
        },
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.NONE,
        primary_training_platform=PrimaryTrainingPlatform.GARMIN_CONNECT,
    )
    db_session.add(prefs)

    await db_session.commit()
    return athlete_id, twin.id


async def _build_first_message_agent(
    db_session: AsyncSession,
) -> FirstMessageAgent:
    """Build a fully-wired FirstMessageAgent with the real repositories."""
    twin_states = TwinStateRepository(db_session)
    return FirstMessageAgent(
        session=db_session,
        coaching_messages=CoachingMessageRepository(db_session),
        generation_events=GenerationEventRepository(db_session),
        context_budget=ContextBudgetService(
            twin_states=twin_states,
            training_goals=TrainingGoalRepository(db_session),
            plans=TrainingPlanRepository(db_session),
            profiles=AthleteProfileRepository(db_session),
            preferences=AthletePreferencesRepository(db_session),
        ),
        prompt_registry=PromptRegistry(),
        training_goals=TrainingGoalRepository(db_session),
        plans=TrainingPlanRepository(db_session),
        twin_states=twin_states,
    )


class TestFirstMessageSuccess:
    async def test_first_message_generated_successfully(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, twin_id = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        result = await agent.generate(athlete_id)

        assert result.message_type == "first_message"
        assert len(result.content) > 0
        assert result.prompt_version == "v1"
        assert result.twin_state_id == twin_id

    async def test_coaching_message_row_persisted(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)

        stmt = select(CoachingMessage).where(
            CoachingMessage.athlete_id == athlete_id,
            CoachingMessage.message_type == MessageType.FIRST_MESSAGE,
        )
        rows = list((await db_session.execute(stmt)).scalars().all())
        assert len(rows) == 1
        assert rows[0].content == _four_paragraph_content()

    async def test_generation_event_written_with_success_true(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is True
        assert events[0].agent_name == "FirstMessageAgent"
        assert events[0].failure_reason is None

    async def test_coaching_message_generated_event_in_outbox(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)

        stmt = select(SystemEvent).where(
            SystemEvent.event_type == "coaching_message_generated",
            SystemEvent.athlete_id == athlete_id,
        )
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].payload["message_type"] == "first_message"
        assert "message_id" in events[0].payload
        assert "generation_event_id" in events[0].payload

        stmt_outbox = select(SystemEventOutbox).where(
            SystemEventOutbox.event_id == events[0].event_id,
        )
        outbox_rows = list((await db_session.execute(stmt_outbox)).scalars().all())
        assert len(outbox_rows) == 1
        assert outbox_rows[0].publication_status == "pending"


class TestFirstMessageIdempotency:
    async def test_second_call_raises_first_message_already_exists_error_without_calling_llm(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        client = _llm_client_returning(_four_paragraph_content())
        monkeypatch.setattr(agent, "_build_llm_client", lambda: client)

        await agent.generate(athlete_id)
        call_count_after_first = client.chat.completions.create.call_count

        try:
            await agent.generate(athlete_id)
        except FirstMessageAlreadyExistsError as exc:
            assert exc.existing_message_id is not None
        else:
            raise AssertionError("FirstMessageAlreadyExistsError not raised")

        assert client.chat.completions.create.call_count == call_count_after_first, (
            "LLM must not be called on second first-message attempt"
        )

    async def test_second_call_does_not_create_new_generation_event(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events_after_first = list((await db_session.execute(stmt)).scalars().all())
        assert len(events_after_first) == 1

        try:
            await agent.generate(athlete_id)
        except FirstMessageAlreadyExistsError:
            pass

        events_after_second = list((await db_session.execute(stmt)).scalars().all())
        assert len(events_after_second) == 1, (
            "Second first-message attempt must not write a new GenerationEvent"
        )

    async def test_get_existing_first_message_returns_persisted_row(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)
        first_msg = (
            await agent._coaching_messages.get_existing_first_message(athlete_id)
        )
        assert first_msg is not None
        assert first_msg.message_type == MessageType.FIRST_MESSAGE


class TestFirstMessageLLMFailure:
    async def test_timeout_writes_generation_event_with_success_false(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_raising(APITimeoutError(request=MagicMock())),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "timeout"
        assert events[0].agent_name == "FirstMessageAgent"

    async def test_api_connection_error_writes_generation_event_failure(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_raising(APIConnectionError(request=MagicMock())),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "proxy_unavailable"

    async def test_api_status_error_429_writes_failure_reason_rate_limit(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.message = "rate limited"

        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_raising(
                APIStatusError(
                    "rate limited",
                    response=rate_limit_response,
                    body=None,
                )
            ),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert events[0].failure_reason == "rate_limit"

    async def test_empty_llm_response_writes_generation_event_failure(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        client = MagicMock()
        response = MagicMock()
        response.choices = [MagicMock()]
        response.choices[0].message.content = ""
        response.usage = MagicMock()
        response.usage.total_tokens = 0
        client.chat.completions.create = AsyncMock(return_value=response)
        monkeypatch.setattr(agent, "_build_llm_client", lambda: client)

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "invalid_output_format"

        stmt_msgs = select(CoachingMessage).where(
            CoachingMessage.athlete_id == athlete_id,
        )
        msgs = list((await db_session.execute(stmt_msgs)).scalars().all())
        assert len(msgs) == 0, "No CoachingMessage must be created on failure"

    async def test_three_paragraph_response_writes_failure_invalid_output(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        three_para = "Para one.\n\nPara two.\n\nPara three."
        monkeypatch.setattr(
            agent,
            "_build_llm_client",
            lambda: _llm_client_returning(three_para),
        )

        with pytest.raises(LLMServiceUnavailableError):
            await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "invalid_output_format"

        stmt_msgs = select(CoachingMessage).where(
            CoachingMessage.athlete_id == athlete_id,
        )
        msgs = list((await db_session.execute(stmt_msgs)).scalars().all())
        assert len(msgs) == 0

    async def test_no_silent_llm_failures(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        client = _llm_client_returning(_four_paragraph_content())
        monkeypatch.setattr(agent, "_build_llm_client", lambda: client)

        await agent.generate(athlete_id)

        stmt = select(GenerationEvent).where(GenerationEvent.athlete_id == athlete_id)
        events = list((await db_session.execute(stmt)).scalars().all())
        assert len(events) == 1, "Every LLM call must produce exactly one GenerationEvent"


class TestFirstMessageContentShape:
    async def test_message_content_has_exactly_four_paragraphs_after_persist(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(db_session)
        agent = await _build_first_message_agent(db_session)

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)

        stmt = select(CoachingMessage).where(
            CoachingMessage.athlete_id == athlete_id,
            CoachingMessage.message_type == MessageType.FIRST_MESSAGE,
        )
        msg = (await db_session.execute(stmt)).scalar_one()
        paragraphs = [p.strip() for p in msg.content.split("\n\n") if p.strip()]
        assert len(paragraphs) == 4


class TestFirstMessageReferencesAthleteContext:
    async def test_message_persists_sport_background_through_prompt_assembly(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_id, _ = await _build_full_setup(
            db_session,
            sport_background=SportBackground.TRIATHLON,
        )
        agent = await _build_first_message_agent(db_session)

        context_dict: dict[str, Any] = {}

        original_build = agent._context_budget.build_first_message_context

        async def _capture(athlete_id_arg: uuid.UUID) -> Any:
            ctx = await original_build(athlete_id_arg)
            context_dict["profile_summary"] = (
                ctx.profile_summary.sport_background.value
                if ctx.profile_summary
                else None
            )
            context_dict["computed_observations"] = ctx.computed_observations
            return ctx

        monkeypatch.setattr(
            agent._context_budget, "build_first_message_context", _capture
        )

        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        await agent.generate(athlete_id)

        assert (
            context_dict["profile_summary"]
            == SportBackground.TRIATHLON.value
        )
        assert context_dict["computed_observations"]["structural_risk_flag"] is True
        assert (
            context_dict["computed_observations"]["structural_risk_reason"]
            == "non-running primary sport background"
        )

    async def test_two_athletes_with_different_backgrounds_produce_different_contexts(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        athlete_a, _ = await _build_full_setup(
            db_session,
            sport_background=SportBackground.RUNNING_PRIMARY,
            structural_risk_flag=False,
        )
        monkeypatch.undo()
        athlete_b, _ = await _build_full_setup(
            db_session,
            sport_background=SportBackground.TRIATHLON,
            structural_risk_flag=True,
        )

        agent_a = await _build_first_message_agent(db_session)
        agent_b = await _build_first_message_agent(db_session)

        ctx_a = await agent_a._context_budget.build_first_message_context(athlete_a)
        ctx_b = await agent_b._context_budget.build_first_message_context(athlete_b)

        assert ctx_a.profile_summary is not None
        assert ctx_b.profile_summary is not None
        assert (
            ctx_a.profile_summary.sport_background
            != ctx_b.profile_summary.sport_background
        )
        assert ctx_a.computed_observations is not None
        assert ctx_b.computed_observations is not None
        assert (
            ctx_a.computed_observations["structural_risk_flag"]
            != ctx_b.computed_observations["structural_risk_flag"]
        )


class TestFirstMessagePreconditionGates:
    async def test_no_twin_state_raises_unavailable(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.models.athlete import Athlete

        athlete = Athlete(email=f"no-twin-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.commit()
        await db_session.refresh(athlete)

        agent = await _build_first_message_agent(db_session)
        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        with pytest.raises(LLMServiceUnavailableError, match="twin state"):
            await agent.generate(athlete.id)

    async def test_no_active_goal_raises_unavailable(
        self, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.models.athlete import Athlete

        athlete = Athlete(email=f"no-goal-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.commit()
        await db_session.refresh(athlete)

        # TwinState is the precondition gate for active_goal; insert one
        # with a non-active goal so the agent reaches the active-goal gate.
        completed_goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
            goal_event_type=GoalEventType.MARATHON,
            goal_event_date=date.today() + timedelta(weeks=20),
            goal_event_name="Completed goal",
            weekly_volume_hours=5.0,
            weekly_volume_km=30.0,
            fitness_level=3,
            status=TrainingGoalStatus.COMPLETED,
        )
        db_session.add(completed_goal)
        await db_session.flush()

        twin_for_completed = TwinState(
            athlete_id=athlete.id,
            training_goal_id=completed_goal.id,
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.LOW,
            trigger=TwinTrigger.QUESTIONNAIRE,
            model_version="v1-questionnaire-bootstrap",
            fitness=0.0,
            fatigue=0.0,
            form=0.0,
            readiness_level=RecoveryModifierLevel.GREEN,
        )
        db_session.add(twin_for_completed)
        await db_session.commit()

        agent = await _build_first_message_agent(db_session)
        monkeypatch.setattr(
            agent, "_build_llm_client", lambda: _llm_client_returning(_four_paragraph_content())
        )

        with pytest.raises(LLMServiceUnavailableError, match="active training goal"):
            await agent.generate(athlete.id)