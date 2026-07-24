"""Integration tests for the ``generate_first_message`` procrastinate worker task.

The Phase-2.7 Batch 3 plan creates a ``generate_first_message`` worker
task (Step 3) that:

1. Opens its own ``AsyncSessionLocal``.
2. Constructs ``FirstMessageAgent`` and calls ``generate(athlete_id=...)``.
3. Catches ``FirstMessageAlreadyExistsError`` and returns idempotent
   success — no second LLM call, no duplicate message.
4. Re-raises ``LLMServiceUnavailableError`` so procrastinate applies
   the retry policy. The agent's failure ``GenerationEvent`` is
   rolled back with the worker's session.

These tests invoke the task function directly — the procrastinate
wrapper is not involved. ``AsyncSessionLocal`` is monkey-patched to
the test's ``test_session_local`` so the task's session shares the
test engine and event loop, mirroring the
``test_outbox_publisher_task_integration.py`` pattern.

The LLM client is mocked at the ``FirstMessageAgent._build_llm_client``
boundary — the existing pattern in ``test_first_message_agent.py``.

Reference plan: ``docs/implementation/phase-2/phase-2-7/batch-3-event-flow-plan-router-fix.md``
Step 3.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIConnectionError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.worker.app as worker_module
from app.agents.first_message_agent import (
    FirstMessageAgent,
    LLMServiceUnavailableError,
)
from app.models.athlete import Athlete
from app.models.athlete_physiology import AthletePhysiology
from app.models.athlete_preferences import AthletePreferences
from app.models.athlete_profile import AthleteProfile
from app.models.coaching_message import CoachingMessage
from app.models.enums import (
    DataTier,
    GpsSource,
    GoalEventType,
    GoalType,
    HrSource,
    MessageType,
    PowerSource,
    PrimaryTrainingPlatform,
    RecoveryModifierLevel,
    Sex,
    SportBackground,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.athlete_fitness import AthleteFitness
from app.models.system_event import SystemEvent
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.worker.app import generate_first_message


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


_FOUR_PARA_CONTENT = (
    "Welcome to your coaching journey.\n\n"
    "I see you have a running background with limited history on record.\n\n"
    "Your plan is structured in two phases over 8 weeks.\n\n"
    "The first block focuses on building your aerobic base."
)


def _build_mock_llm_response(content: str) -> MagicMock:
    """Build a mock OpenAI ChatCompletion response with the given content."""
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage = MagicMock()
    response.usage.completion_tokens = 100
    return response


def _build_mock_llm_client(content: str = _FOUR_PARA_CONTENT) -> AsyncMock:
    client = AsyncMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = AsyncMock(
        return_value=_build_mock_llm_response(content)
    )
    return client


async def _seed_onboarded_athlete_with_plan(
    db_session: AsyncSession,
) -> tuple[Athlete, TwinState, TrainingPlan]:
    """Insert the minimum state required for FirstMessageAgent.generate()
    to succeed — athlete + twin state + active training goal +
    active training plan. No first message yet."""
    athlete = Athlete(email=f"first-msg-{uuid.uuid4()}@example.com")
    db_session.add(athlete)
    await db_session.flush()

    profile = AthleteProfile(
        athlete_id=athlete.id,
        timezone="Europe/Lisbon",
        training_window=None,
        height_cm=180.0,
        date_of_birth=date(1990, 1, 1),
        sex=Sex.NOT_SPECIFIED,
        structural_risk_flag=False,
    )
    db_session.add(profile)

    preferences = AthletePreferences(
        athlete_id=athlete.id,
        sport_background=SportBackground.RUNNING_PRIMARY,
        years_structured_training=3,
        training_time_of_day="morning",
        weekly_schedule={},
        gps_source=GpsSource.GARMIN_WATCH,
        hr_source=HrSource.CHEST_STRAP_RR,
        power_source=PowerSource.NONE,
        primary_training_platform=PrimaryTrainingPlatform.MANUAL,
    )
    db_session.add(preferences)

    goal = TrainingGoal(
        athlete_id=athlete.id,
        goal_type=GoalType.RACE_EVENT,
        goal_event_type=GoalEventType.HALF_MARATHON,
        goal_event_name="Test Half Marathon",
        goal_event_date=date.today() + timedelta(days=120),
        weekly_volume_hours=6.0,
        weekly_volume_km=40.0,
        fitness_level=3,
        status=TrainingGoalStatus.ACTIVE,
    )
    db_session.add(goal)
    await db_session.flush()

    physiology = AthletePhysiology(
        athlete_id=athlete.id,
        max_hr={"value": 184.0, "dominant_source": "questionnaire_estimate"},
        lt1={"hr": {"value": 138.0, "dominant_source": "questionnaire_estimate"}},
        lt2={"hr": {"value": 161.0, "dominant_source": "questionnaire_estimate"}},
    )
    db_session.add(physiology)

    fitness = AthleteFitness(
        athlete_id=athlete.id,
        aggregate={"fitness": 0.0, "fatigue": 0.0, "form": 0.0},
        time_constants={
            "source": "population_default",
            "aerobic": {"fitness_tau_days": 42, "fatigue_tau_days": 7},
            "neuromuscular": {"fitness_tau_days": 7, "fatigue_tau_days": 3},
            "structural": {"fitness_tau_days": 56, "fatigue_tau_days": 14},
        },
    )
    db_session.add(fitness)

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

    return athlete, twin, plan


async def _run_generate_first_message_task(
    test_session_local: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    athlete_id: uuid.UUID,
) -> dict[str, Any]:
    monkeypatch.setattr(worker_module, "AsyncSessionLocal", test_session_local)
    return await generate_first_message(athlete_id=str(athlete_id))


# ---------------------------------------------------------------------------
# generate_first_message task body.
# ---------------------------------------------------------------------------


class TestGenerateFirstMessageTaskCreatesCoachingMessage:
    """The task creates a CoachingMessage with message_type=first_message
    and writes a coaching_message_generated outbox row."""

    async def test_creates_first_message(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, _twin, _plan = await _seed_onboarded_athlete_with_plan(db_session)
        await db_session.commit()

        with patch.object(
            FirstMessageAgent, "_build_llm_client", return_value=_build_mock_llm_client()
        ):
            result = await _run_generate_first_message_task(
                test_session_local, monkeypatch, athlete_id=athlete.id
            )

        assert result["athlete_id"] == str(athlete.id)
        assert result["coaching_message_id"] is not None
        assert result["already_existed"] is False

        messages = (
            await db_session.execute(
                select(CoachingMessage).where(
                    CoachingMessage.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(messages) == 1
        assert messages[0].message_type is MessageType.FIRST_MESSAGE

    async def test_writes_coaching_message_generated_outbox_row(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, _twin, _plan = await _seed_onboarded_athlete_with_plan(db_session)
        await db_session.commit()

        with patch.object(
            FirstMessageAgent, "_build_llm_client", return_value=_build_mock_llm_client()
        ):
            await _run_generate_first_message_task(
                test_session_local, monkeypatch, athlete_id=athlete.id
            )

        events = (
            await db_session.execute(
                select(SystemEvent)
                .where(SystemEvent.athlete_id == athlete.id)
                .where(SystemEvent.event_type == "coaching_message_generated")
            )
        ).scalars().all()
        assert len(events) == 1


class TestGenerateFirstMessageTaskIsIdempotent:
    """Running the task twice for the same athlete creates the
    message on the first run and returns success on the second
    run without creating a duplicate — the agent's
    ``get_existing_first_message`` check returns the existing
    message and raises ``FirstMessageAlreadyExistsError``, which
    the worker catches and translates to idempotent success."""

    async def test_second_run_returns_already_existed(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, _twin, _plan = await _seed_onboarded_athlete_with_plan(db_session)
        await db_session.commit()

        with patch.object(
            FirstMessageAgent, "_build_llm_client", return_value=_build_mock_llm_client()
        ):
            first = await _run_generate_first_message_task(
                test_session_local, monkeypatch, athlete_id=athlete.id
            )
            second = await _run_generate_first_message_task(
                test_session_local, monkeypatch, athlete_id=athlete.id
            )

        assert first["already_existed"] is False
        assert second["already_existed"] is True
        assert second["coaching_message_id"] is None

        messages = (
            await db_session.execute(
                select(CoachingMessage).where(
                    CoachingMessage.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(messages) == 1


class TestGenerateFirstMessageTaskHandlesAlreadyExistsError:
    """When the agent raises ``FirstMessageAlreadyExistsError`` (a
    pre-existing first message is found), the worker task returns
    idempotent success — no error, no duplicate message, no LLM
    call."""

    async def test_existing_first_message_returns_idempotent_success(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, twin, _plan = await _seed_onboarded_athlete_with_plan(db_session)
        existing = CoachingMessage(
            athlete_id=athlete.id,
            twin_state_id=twin.id,
            message_type=MessageType.FIRST_MESSAGE,
            content="Already generated.",
            prompt_version="v1",
        )
        db_session.add(existing)
        await db_session.commit()

        with patch.object(
            FirstMessageAgent, "_build_llm_client", return_value=_build_mock_llm_client()
        ) as mock_build:
            result = await _run_generate_first_message_task(
                test_session_local, monkeypatch, athlete_id=athlete.id
            )

        assert result["already_existed"] is True
        assert result["coaching_message_id"] is None
        mock_build.assert_not_called()

        messages = (
            await db_session.execute(
                select(CoachingMessage).where(
                    CoachingMessage.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(messages) == 1


class TestGenerateFirstMessageTaskRetriesOnLLMFailure:
    """When the LLM proxy is unavailable, the agent writes a
    ``GenerationEvent`` with ``success=false`` and raises
    ``LLMServiceUnavailableError``. The worker task rolls back its
    session — including the failure ``GenerationEvent`` — and
    re-raises so procrastinate applies its retry policy."""

    async def test_llm_failure_propagates_for_retry(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete, _twin, _plan = await _seed_onboarded_athlete_with_plan(db_session)
        await db_session.commit()

        failing_client = AsyncMock()
        failing_client.chat = MagicMock()
        failing_client.chat.completions = MagicMock()
        failing_client.chat.completions.create = AsyncMock(
            side_effect=APIConnectionError(request=MagicMock())
        )

        with patch.object(
            FirstMessageAgent, "_build_llm_client", return_value=failing_client
        ):
            with pytest.raises(LLMServiceUnavailableError):
                await _run_generate_first_message_task(
                    test_session_local, monkeypatch, athlete_id=athlete.id
                )

        messages = (
            await db_session.execute(
                select(CoachingMessage).where(
                    CoachingMessage.athlete_id == athlete.id
                )
            )
        ).scalars().all()
        assert len(messages) == 0
