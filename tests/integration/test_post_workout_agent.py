"""Integration tests for PostWorkoutAgent — real DB, mocked LLM proxy.

Covers the agent's interaction with the real PostgreSQL test database
while stubbing the external LLM proxy at the AsyncOpenAI boundary. The
agent's internal orchestration, repository calls, GenerationEvent writing,
and event publishing run real per the mocking-contract rule that only
the external boundary is mocked.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents import post_workout_agent as pwa_module
from app.agents.post_workout_agent import (
    PostWorkoutAgent,
    PostWorkoutLLMUnavailableError,
)
from app.models.activity import Activity
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    ActivitySource,
    MessageType,
    SportType,
)
from app.models.generation_event import GenerationEvent
from app.models.system_event import SystemEvent
from app.repositories.coaching_message_repository import (
    CoachingMessageRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.activity_repository import ActivityRepository
from app.repositories.planned_session_repository import (
    PlannedSessionRepository,
)
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.compliance_service import ComplianceService
from app.core.prompt_registry import get_default_prompt_registry
from tests.utils.factories import (
    make_athlete_with_profile,
    make_athlete_preferences,
    make_training_goal,
    make_twin_state,
)


THREE_PARAGRAPH_CONTENT = (
    "You held a steady aerobic effort across the session, with HR sitting "
    "in zone 3 most of the time. The aerobic load from this run is logged "
    "at 80 units and your fitness continues to track the recent block.\n\n"
    "Today's effort aligns with the threshold session on the plan. The "
    "actual HR drifted below zone 4 which suggests the prescribed intensity "
    "ran slightly under-executed versus the planned intent.\n\n"
    "For tomorrow, a recovery shakeout would consolidate the week. The "
    "calendar shows the long run on Saturday so keep this session light "
    "and let the legs come back fully."
)


def _llm_client_returning(content: str) -> MagicMock:
    client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.total_tokens = 123
    client.chat.completions.create = AsyncMock(return_value=response)
    return client


def _llm_client_raising(exc: BaseException) -> MagicMock:
    client = MagicMock()
    client.chat.completions.create = AsyncMock(side_effect=exc)
    return client


def _llm_client_factory(
    make_client: Callable[[], MagicMock],
) -> Callable[..., MagicMock]:
    """Return an AsyncOpenAI-compatible factory that ignores constructor kwargs."""

    def _factory(**_kwargs: object) -> MagicMock:
        return make_client()

    return _factory


async def _build_full_setup(
    db_session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID, Activity]:
    athlete, _ = await make_athlete_with_profile(db_session)
    await make_athlete_preferences(db_session, athlete_id=athlete.id)
    goal = await make_training_goal(db_session, athlete_id=athlete.id)
    await make_twin_state(
        db_session,
        athlete_id=athlete.id,
        training_goal_id=goal.id,
    )

    activity = Activity(
        athlete_id=athlete.id,
        source=ActivitySource.MANUAL_UPLOAD,
        external_id="pw-test-1",
        activity_date=date(2026, 1, 1),
        start_time=datetime(2026, 1, 1, 8, 0, 0, tzinfo=timezone.utc),
        duration_seconds=3600,
        sport_type=SportType.RUNNING,
        has_hr=True,
        has_gps=True,
        quality_flags={},
        fit_file_key="athlete/2026-01-01/test.fit",
        aerobic_load=80.0,
    )
    db_session.add(activity)
    await db_session.commit()
    await db_session.refresh(activity)
    return athlete.id, activity.id, activity


def _build_agent(db_session: AsyncSession) -> PostWorkoutAgent:
    return PostWorkoutAgent(
        session=db_session,
        coaching_messages=CoachingMessageRepository(db_session),
        generation_events=GenerationEventRepository(db_session),
        activities=ActivityRepository(db_session),
        planned_sessions=PlannedSessionRepository(db_session),
        twin_states=TwinStateRepository(db_session),
        prompt_registry=get_default_prompt_registry(),
        compliance_service=ComplianceService(),
    )


class TestPostWorkoutSuccess:
    async def test_post_workout_message_generated(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(THREE_PARAGRAPH_CONTENT)
            ),
        )

        message = await agent.generate(
            athlete_id=athlete_id, activity_id=activity_id
        )

        assert message.message_type == MessageType.POST_WORKOUT
        assert message.activity_id == activity_id
        assert message.twin_state_id is not None
        assert message.content == THREE_PARAGRAPH_CONTENT

    async def test_coaching_message_persisted(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(THREE_PARAGRAPH_CONTENT)
            ),
        )

        message = await agent.generate(
            athlete_id=athlete_id, activity_id=activity_id
        )
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingMessage).where(CoachingMessage.id == message.id)
        )
        persisted = result.scalar_one()
        assert persisted.athlete_id == athlete_id
        assert persisted.activity_id == activity_id

    async def test_generation_event_written_with_success_true(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(THREE_PARAGRAPH_CONTENT)
            ),
        )

        await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()

        result = await db_session.execute(
            select(GenerationEvent).where(
                GenerationEvent.athlete_id == athlete_id
            )
        )
        events = list(result.scalars())
        assert len(events) == 1
        assert events[0].success is True
        assert events[0].agent_name == "PostWorkoutAgent"

    async def test_coaching_message_generated_event_in_outbox(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(THREE_PARAGRAPH_CONTENT)
            ),
        )

        await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()

        result = await db_session.execute(
            select(SystemEvent).where(SystemEvent.athlete_id == athlete_id)
        )
        events = list(result.scalars())
        event_types = {e.event_type for e in events}
        assert "coaching_message_generated" in event_types


class TestPostWorkoutIdempotency:
    async def test_second_call_returns_existing(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        mock_client = _llm_client_returning(THREE_PARAGRAPH_CONTENT)
        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(lambda: mock_client),
        )

        first = await agent.generate(
            athlete_id=athlete_id, activity_id=activity_id
        )
        await db_session.commit()

        second = await agent.generate(
            athlete_id=athlete_id, activity_id=activity_id
        )

        assert first.id == second.id
        assert mock_client.chat.completions.create.await_count == 1

    async def test_second_call_does_not_create_new_generation_event(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(THREE_PARAGRAPH_CONTENT)
            ),
        )

        await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()
        await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()

        result = await db_session.execute(
            select(GenerationEvent).where(
                GenerationEvent.athlete_id == athlete_id
            )
        )
        events = list(result.scalars())
        assert len(events) == 1


class TestPostWorkoutParagraphStructure:
    async def test_three_paragraphs_accepted(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(THREE_PARAGRAPH_CONTENT)
            ),
        )

        message = await agent.generate(
            athlete_id=athlete_id, activity_id=activity_id
        )

        paragraph_count = len([p for p in message.content.split("\n\n") if p.strip()])
        assert paragraph_count == 3

    async def test_wrong_paragraph_count_writes_failure_event(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        two_paragraphs = "First paragraph.\n\nSecond paragraph."
        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_returning(two_paragraphs)
            ),
        )

        with pytest.raises(PostWorkoutLLMUnavailableError):
            await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()

        result = await db_session.execute(
            select(GenerationEvent).where(
                GenerationEvent.athlete_id == athlete_id
            )
        )
        events = list(result.scalars())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "invalid_output_format"

        result = await db_session.execute(
            select(CoachingMessage).where(
                CoachingMessage.athlete_id == athlete_id
            )
        )
        assert list(result.scalars()) == []


class TestPostWorkoutLlmFailure:
    async def test_llm_failure_writes_failure_event(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from openai import APITimeoutError

        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_raising(
                    APITimeoutError(request=MagicMock())
                )
            ),
        )

        with pytest.raises(PostWorkoutLLMUnavailableError):
            await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()

        result = await db_session.execute(
            select(GenerationEvent).where(
                GenerationEvent.athlete_id == athlete_id
            )
        )
        events = list(result.scalars())
        assert len(events) == 1
        assert events[0].success is False
        assert events[0].failure_reason == "timeout"

    async def test_llm_failure_creates_no_coaching_message(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from openai import APIConnectionError

        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        monkeypatch.setattr(
            pwa_module,
            "AsyncOpenAI",
            _llm_client_factory(
                lambda: _llm_client_raising(
                    APIConnectionError(request=MagicMock())
                )
            ),
        )

        with pytest.raises(PostWorkoutLLMUnavailableError):
            await agent.generate(athlete_id=athlete_id, activity_id=activity_id)
        await db_session.commit()

        result = await db_session.execute(
            select(CoachingMessage).where(
                CoachingMessage.athlete_id == athlete_id
            )
        )
        assert list(result.scalars()) == []


class TestPostWorkoutProxyRouting:
    async def test_routes_through_litellm_proxy(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete_id, activity_id, _ = await _build_full_setup(db_session)
        agent = _build_agent(db_session)

        captured_kwargs: dict[str, Any] = {}

        def _capture(**kwargs: Any) -> MagicMock:
            captured_kwargs.update(kwargs)
            return _llm_client_returning(THREE_PARAGRAPH_CONTENT)

        monkeypatch.setattr(pwa_module, "AsyncOpenAI", _capture)

        await agent.generate(athlete_id=athlete_id, activity_id=activity_id)

        from app.config import settings

        assert captured_kwargs["base_url"] == settings.LITELLM_BASE_URL
