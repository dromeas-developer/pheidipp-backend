"""Integration tests for the workout API endpoints.

Tests the full HTTP surface for Phase-1.5b:
- GET /athletes/{athlete_id}/today
- POST /athletes/{athlete_id}/sessions/{session_id}/generate-workout

Reference plan: docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md
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
from app.models.enums import (
    AuthProvider,
    DataTier,
    GoalEventType,
    GoalType,
    PhaseLabel,
    PlannedSessionStatus,
    RecoveryModifierLevel,
    SessionPriority,
    SessionType,
    TrainingGoalStatus,
    TrainingPlanStatus,
    TwinConfidenceLevel,
    TwinTrigger,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.planned_session import PlannedSession
from app.models.training_goal import TrainingGoal
from app.models.training_plan import TrainingPlan
from app.models.twin_state import TwinState
from app.models.weekly_plan import WeeklyPlan
from app.services.workout_generation_errors import (
    LLMServiceUnavailableError,
    WorkoutAlreadyGeneratedError,
)


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


async def _create_athlete_with_onboarding(
    db_session: AsyncSession, email: str | None = None
) -> tuple[Athlete, TrainingGoal, TwinState, TrainingPlan, PlannedSession, WeeklyPlan]:
    """Create a fully-onboarded athlete with a planned session for today."""
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
        data_tier=DataTier.TIER_3,
        confidence_level=TwinConfidenceLevel.MEDIUM,
        trigger=TwinTrigger.QUESTIONNAIRE,
        model_version="v1.0",
        fitness=0.5,
        fatigue=0.3,
        form=0.2,
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

    weekly_plan = WeeklyPlan(
        training_plan_id=plan.id,
        week_number=1,
        status="active",
    )
    db_session.add(weekly_plan)
    await db_session.flush()

    today = datetime.now(timezone.utc).date()
    planned_session = PlannedSession(
        weekly_plan_id=weekly_plan.id,
        training_plan_id=plan.id,
        target_date=today,
        week_number=1,
        phase_label=PhaseLabel.THRESHOLD_BUILD,
        session_type=SessionType.THRESHOLD,
        intent_description="Threshold intervals at race pace",
        approximate_duration_minutes=60,
        status=PlannedSessionStatus.PENDING,
        session_priority=SessionPriority.PRIMARY,
    )
    db_session.add(planned_session)
    await db_session.flush()

    return athlete, goal, twin, plan, planned_session, weekly_plan


def _auth_header(athlete_id: uuid.UUID, token_service: TokenService) -> dict[str, str]:
    """Return a valid Bearer JWT for the athlete."""
    token, _exp = token_service.issue_access_token(
        athlete_id=athlete_id,
        auth_provider=AuthProvider.EMAIL,
    )
    return {"Authorization": f"Bearer {token}"}


def _mock_workout_response(
    planned_session_id: uuid.UUID,
    twin_state_id: uuid.UUID,
    generation_date: date,
) -> tuple[MagicMock, list[MagicMock]]:
    """Create a mock GeneratedWorkout with steps for endpoint mocking."""
    workout_id = uuid.uuid4()
    workout = MagicMock(spec=GeneratedWorkout)
    workout.id = workout_id
    workout.planned_session_id = planned_session_id
    workout.twin_state_id = twin_state_id
    workout.theoretical_targets = {
        "targets": [],
        "description": "Threshold session",
    }
    workout.adjusted_targets = {
        "targets": [],
        "description": "Threshold session",
    }
    workout.recovery_modifier_level = RecoveryModifierLevel.GREEN
    workout.recovery_modifier_reason = None
    workout.generation_date = generation_date
    workout.generated_at = datetime.now(timezone.utc)

    steps = [
        MagicMock(
            id=uuid.uuid4(),
            generated_workout_id=workout_id,
            step_order=1,
            step_type="warmup",
            session_type=SessionType.THRESHOLD,
            physiological_intent="recovery",
            session_purpose="general",
            target={
                "signal_type": "gap",
                "primary": {"min": 360, "max": 390, "unit": "sec_per_km"},
                "fallback": None,
                "description": "Easy pace warmup",
            },
            duration_seconds=600,
            description="Warm up",
        ),
        MagicMock(
            id=uuid.uuid4(),
            generated_workout_id=workout_id,
            step_order=2,
            step_type="work",
            session_type=SessionType.THRESHOLD,
            physiological_intent="threshold",
            session_purpose="general",
            target={
                "signal_type": "gap",
                "primary": {"min": 300, "max": 330, "unit": "sec_per_km"},
                "fallback": None,
                "description": "Threshold pace",
            },
            duration_seconds=1800,
            description="Threshold intervals",
        ),
        MagicMock(
            id=uuid.uuid4(),
            generated_workout_id=workout_id,
            step_order=3,
            step_type="cooldown",
            session_type=SessionType.THRESHOLD,
            physiological_intent="recovery",
            session_purpose="general",
            target={
                "signal_type": "gap",
                "primary": {"min": 360, "max": 390, "unit": "sec_per_km"},
                "fallback": None,
                "description": "Easy pace cooldown",
            },
            duration_seconds=600,
            description="Cool down",
        ),
    ]
    return workout, steps


# ---------------------------------------------------------------------------
# GET /athletes/{id}/today
# ---------------------------------------------------------------------------


class TestGetToday:
    """Tests for the GET /athletes/{id}/today endpoint."""

    @pytest.mark.asyncio
    async def test_200_with_existing_workout(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _, planned_session, _ = (
            await _create_athlete_with_onboarding(db_session)
        )
        await db_session.flush()

        workout, steps = _mock_workout_response(
            planned_session.id,
            twin.id,
            datetime.now(timezone.utc).date(),
        )

        with patch(
            "app.api.v1.workout.WorkoutGenerationAgent"
        ) as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.return_value = workout
            mock_instance.load_steps.return_value = steps
            MockAgent.return_value = mock_instance

            response = await client.get(
                f"/athletes/{athlete.id}/today",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 200
        data = response.json()
        assert "planned_session" in data
        assert "generated_workout" in data
        assert "steps" in data
        assert len(data["steps"]) == 3

    @pytest.mark.asyncio
    async def test_404_when_no_session_for_today(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        # Build an athlete with an active plan but NO planned session for
        # today. The full onboarding helper always creates a session for
        # today, so we inline a minimal chain here that stops at the
        # WeeklyPlan (no PlannedSession attached).
        athlete = Athlete(email=f"no-session-{uuid.uuid4()}@example.com")
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
            data_tier=DataTier.TIER_3,
            confidence_level=TwinConfidenceLevel.MEDIUM,
            trigger=TwinTrigger.QUESTIONNAIRE,
            model_version="v1.0",
            fitness=0.5,
            fatigue=0.3,
            form=0.2,
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

        # No PlannedSession created for today — the endpoint must return 404.
        await db_session.flush()

        response = await client.get(
            f"/athletes/{athlete.id}/today",
            headers=_auth_header(athlete.id, token_service),
        )

        assert response.status_code == 404
        assert "no planned session" in response.json()["detail"].lower()

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

        # athlete1 tries to access athlete2's today view
        response = await client.get(
            f"/athletes/{athlete2.id}/today",
            headers=_auth_header(athlete1.id, token_service),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        response = await client.get(f"/athletes/{athlete.id}/today")
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /athletes/{id}/sessions/{id}/generate-workout
# ---------------------------------------------------------------------------


class TestPostGenerateWorkout:
    """Tests for the POST /athletes/{id}/sessions/{id}/generate-workout endpoint."""

    @pytest.mark.asyncio
    async def test_201_on_successful_generation(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _, planned_session, _ = (
            await _create_athlete_with_onboarding(db_session)
        )
        await db_session.flush()

        workout, steps = _mock_workout_response(
            planned_session.id,
            twin.id,
            datetime.now(timezone.utc).date(),
        )

        with patch(
            "app.api.v1.workout.WorkoutGenerationAgent"
        ) as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.return_value = workout
            mock_instance.load_steps.return_value = steps
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/athletes/{athlete.id}/sessions/{planned_session.id}/generate-workout",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 201
        data = response.json()
        assert "generated_workout" in data
        assert "steps" in data
        assert len(data["steps"]) == 3

    @pytest.mark.asyncio
    async def test_409_when_workout_already_generated(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, _, _, planned_session, _ = (
            await _create_athlete_with_onboarding(db_session)
        )
        await db_session.flush()

        existing_workout_id = uuid.uuid4()
        with patch(
            "app.api.v1.workout.WorkoutGenerationAgent"
        ) as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.side_effect = WorkoutAlreadyGeneratedError(
                existing_workout_id=existing_workout_id
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/athletes/{athlete.id}/sessions/{planned_session.id}/generate-workout",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 409
        data = response.json()
        assert "existing_workout_id" in data["detail"]

    @pytest.mark.asyncio
    async def test_502_on_llm_failure(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, _, _, planned_session, _ = (
            await _create_athlete_with_onboarding(db_session)
        )
        await db_session.flush()

        with patch(
            "app.api.v1.workout.WorkoutGenerationAgent"
        ) as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.side_effect = LLMServiceUnavailableError(
                "LLM call failed"
            )
            MockAgent.return_value = mock_instance

            response = await client.post(
                f"/athletes/{athlete.id}/sessions/{planned_session.id}/generate-workout",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response.status_code == 502
        assert "unavailable" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_404_when_session_not_found(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, *_ = await _create_athlete_with_onboarding(db_session)
        await db_session.flush()

        nonexistent_session_id = uuid.uuid4()

        response = await client.post(
            f"/athletes/{athlete.id}/sessions/{nonexistent_session_id}/generate-workout",
            headers=_auth_header(athlete.id, token_service),
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_403_accessing_different_athlete(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete1, _, _, _, planned_session1, _ = await _create_athlete_with_onboarding(
            db_session, f"athlete1-{uuid.uuid4()}@example.com"
        )
        athlete2, *_ = await _create_athlete_with_onboarding(
            db_session, f"athlete2-{uuid.uuid4()}@example.com"
        )
        await db_session.flush()

        # athlete1 tries to generate workout for athlete2's session
        response = await client.post(
            f"/athletes/{athlete2.id}/sessions/{planned_session1.id}/generate-workout",
            headers=_auth_header(athlete1.id, token_service),
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_401_without_auth(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
    ) -> None:
        athlete, _, _, _, planned_session, _ = (
            await _create_athlete_with_onboarding(db_session)
        )
        await db_session.flush()

        response = await client.post(
            f"/athletes/{athlete.id}/sessions/{planned_session.id}/generate-workout"
        )
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# Idempotency verification.
# ---------------------------------------------------------------------------


class TestIdempotency:
    """Tests for workout generation idempotency."""

    @pytest.mark.asyncio
    async def test_second_post_returns_409_with_same_workout(
        self,
        client: AsyncClient,
        db_session: AsyncSession,
        token_service: TokenService,
    ) -> None:
        athlete, _, twin, _, planned_session, _ = (
            await _create_athlete_with_onboarding(db_session)
        )
        await db_session.flush()

        workout, steps = _mock_workout_response(
            planned_session.id,
            twin.id,
            datetime.now(timezone.utc).date(),
        )

        # First call returns the newly generated workout
        with patch(
            "app.api.v1.workout.WorkoutGenerationAgent"
        ) as MockAgent:
            mock_instance = AsyncMock()
            mock_instance.generate.return_value = workout
            mock_instance.load_steps.return_value = steps
            MockAgent.return_value = mock_instance

            response1 = await client.post(
                f"/athletes/{athlete.id}/sessions/{planned_session.id}/generate-workout",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response1.status_code == 201

        # Second call raises WorkoutAlreadyGeneratedError → 409
        with patch(
            "app.api.v1.workout.WorkoutGenerationAgent"
        ) as MockAgent:
            existing_workout_id = workout.id
            mock_instance = AsyncMock()
            mock_instance.generate.side_effect = WorkoutAlreadyGeneratedError(
                existing_workout_id=existing_workout_id
            )
            MockAgent.return_value = mock_instance

            response2 = await client.post(
                f"/athletes/{athlete.id}/sessions/{planned_session.id}/generate-workout",
                headers=_auth_header(athlete.id, token_service),
            )

        assert response2.status_code == 409
        data = response2.json()
        assert data["detail"]["existing_workout_id"] == str(existing_workout_id)