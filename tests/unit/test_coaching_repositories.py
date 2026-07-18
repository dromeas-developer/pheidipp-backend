"""Unit tests for repository append-only invariants.

Verifies that CoachingMessageRepository and GenerationEventRepository
expose only insert() and no update()/delete() methods.

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching_message import CoachingMessage
from app.models.enums import MessageType
from app.models.generation_event import GenerationEvent
from app.models.twin_state import TwinState
from app.models.training_goal import TrainingGoal
from app.models.enums import (
    DataTier,
    GoalType,
    RecoveryModifierLevel,
    TrainingGoalStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.athlete import Athlete
from app.repositories.coaching_message_repository import CoachingMessageRepository
from app.repositories.generation_event_repository import GenerationEventRepository


# ---------------------------------------------------------------------------
# CoachingMessageRepository — append-only contract.
# ---------------------------------------------------------------------------


class TestCoachingMessageRepositoryAppendOnly:
    """The repository contract enforces append-only: no update() or
    delete() methods are exposed."""

    def test_no_update_method(self) -> None:
        """CoachingMessageRepository must NOT expose update()."""
        public_methods = [
            m for m in dir(CoachingMessageRepository)
            if not m.startswith("_")
        ]
        assert "update" not in public_methods
        assert "update_" not in " ".join(public_methods)

    def test_no_delete_method(self) -> None:
        """CoachingMessageRepository must NOT expose delete()."""
        [
            m for m in dir(CoachingMessageRepository)
            if not m.startswith("_")
        ]
        # Allow 'delete' if it was defined — check it's not in spec
        repo = CoachingMessageRepository.__dict__
        assert "delete" not in repo
        assert "delete_" not in str(repo)

    @pytest.mark.asyncio
    async def test_insert_returns_message(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"repo-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
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

        repo = CoachingMessageRepository(session=db_session)
        message = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Test first message content",
            prompt_version="v1",
        )
        result = await repo.insert(message)
        await db_session.flush()

        assert result.id is not None
        assert result.content == "Test first message content"

    @pytest.mark.asyncio
    async def test_get_existing_first_message_returns_null_when_none(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"get-null-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()

        repo = CoachingMessageRepository(session=db_session)
        result = await repo.get_existing_first_message(athlete.id)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_existing_first_message_returns_message(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"get-msg-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
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

        repo = CoachingMessageRepository(session=db_session)
        message = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Existing message",
            prompt_version="v1",
        )
        await repo.insert(message)
        await db_session.flush()

        result = await repo.get_existing_first_message(athlete.id)
        assert result is not None
        assert result.content == "Existing message"

    @pytest.mark.asyncio
    async def test_get_by_athlete_id_ordered_by_generated_at_desc(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"list-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()
        goal = TrainingGoal(
            athlete_id=athlete.id,
            goal_type=GoalType.RACE_EVENT,
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

        repo = CoachingMessageRepository(session=db_session)
        msg1 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.WELLNESS_ALERT,
            content="First message",
            prompt_version="v1",
        )
        msg2 = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Second message",
            prompt_version="v1",
        )
        await repo.insert(msg1)
        await db_session.flush()
        await repo.insert(msg2)
        await db_session.flush()

        messages = await repo.get_by_athlete_id(athlete.id)
        assert len(messages) == 2
        # Newest first (msg2 was inserted last)
        assert messages[0].content == "Second message"
        assert messages[1].content == "First message"


# ---------------------------------------------------------------------------
# GenerationEventRepository — append-only contract.
# ---------------------------------------------------------------------------


class TestGenerationEventRepositoryAppendOnly:
    """The repository contract enforces append-only: no update() or
    delete() methods are exposed."""

    def test_no_update_method(self) -> None:
        """GenerationEventRepository must NOT expose update()."""
        repo = GenerationEventRepository.__dict__
        assert "update" not in repo
        assert "update_" not in str(repo)

    def test_no_delete_method(self) -> None:
        """GenerationEventRepository must NOT expose delete()."""
        repo = GenerationEventRepository.__dict__
        assert "delete" not in repo
        assert "delete_" not in str(repo)

    @pytest.mark.asyncio
    async def test_insert_returns_event(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"gen-ev-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()

        repo = GenerationEventRepository(session=db_session)
        event = GenerationEvent(
            athlete_id=athlete.id,
            agent_name="FirstMessageAgent",
            prompt_version="v1",
            trigger_context="manual_api_call",
            input_token_count=500,
            output_token_count=150,
            latency_ms=1000,
            success=True,
            failure_reason=None,
        )
        result = await repo.insert(event)
        await db_session.flush()

        assert result.id is not None
        assert result.agent_name == "FirstMessageAgent"
        assert result.success is True

    @pytest.mark.asyncio
    async def test_insert_failure_event_has_failure_reason(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"gen-ev-err-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()

        repo = GenerationEventRepository(session=db_session)
        event = GenerationEvent(
            athlete_id=athlete.id,
            agent_name="FirstMessageAgent",
            prompt_version="v1",
            trigger_context="manual_api_call",
            input_token_count=500,
            output_token_count=0,
            latency_ms=5000,
            success=False,
            failure_reason="timeout",
        )
        result = await repo.insert(event)
        await db_session.flush()

        assert result.success is False
        assert result.failure_reason == "timeout"

    @pytest.mark.asyncio
    async def test_insert_records_input_and_output_token_counts(
        self, db_session: AsyncSession
    ) -> None:
        athlete = Athlete(email=f"gen-ev-tokens-{uuid.uuid4()}@example.com")
        db_session.add(athlete)
        await db_session.flush()

        repo = GenerationEventRepository(session=db_session)
        event = GenerationEvent(
            athlete_id=athlete.id,
            agent_name="FirstMessageAgent",
            prompt_version="v1",
            trigger_context="manual_api_call",
            input_token_count=1234,
            output_token_count=567,
            latency_ms=2000,
            success=True,
            failure_reason=None,
        )
        result = await repo.insert(event)
        await db_session.flush()

        assert result.input_token_count == 1234
        assert result.output_token_count == 567