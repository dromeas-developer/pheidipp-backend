"""Unit tests for ``ContextBudgetService``.

Tests token estimation and context assembly:
- Token estimation: deterministic `len(JSON) / 4` formula
- Budget enforcement: logs warning when exceeded
- Context assembly: fetches twin state, goal, plan, profile, preferences

Reference plan: docs/implementation/phase-1/phase-1-5a-first-coach-message.md
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock

import pytest

from app.models.enums import (
    DataTier,
    GoalType,
    RecoveryModifierLevel,
    SportBackground,
    TwinConfidenceLevel,
)
from app.models.twin_state import TwinState
from app.repositories.athlete_preferences_repository import AthletePreferencesRepository
from app.repositories.athlete_profile_repository import AthleteProfileRepository
from app.repositories.training_goal_repository import TrainingGoalRepository
from app.repositories.training_plan_repository import TrainingPlanRepository
from app.repositories.twin_state_repository import TwinStateRepository
from app.services.context_budget_service import (
    ContextBudgetService,
    FIRST_MESSAGE_PRIORITY_PROFILE,
    MAX_TOKENS,
    ContextSection,
    FirstMessageContext,
)


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def twin_states_repo() -> AsyncMock:
    return AsyncMock(spec=TwinStateRepository)


@pytest.fixture
def training_goals_repo() -> AsyncMock:
    return AsyncMock(spec=TrainingGoalRepository)


@pytest.fixture
def plans_repo() -> AsyncMock:
    return AsyncMock(spec=TrainingPlanRepository)


@pytest.fixture
def profiles_repo() -> AsyncMock:
    return AsyncMock(spec=AthleteProfileRepository)


@pytest.fixture
def preferences_repo() -> AsyncMock:
    return AsyncMock(spec=AthletePreferencesRepository)


@pytest.fixture
def service(
    twin_states_repo: AsyncMock,
    training_goals_repo: AsyncMock,
    plans_repo: AsyncMock,
    profiles_repo: AsyncMock,
    preferences_repo: AsyncMock,
    mock_preferences: MagicMock,
    mock_active_goal: MagicMock,
    mock_twin_state: MagicMock,
) -> ContextBudgetService:
    # Default return value so tests that don't explicitly configure preferences
    # still get a properly-mocked object (not an implicit AsyncMock).
    preferences_repo.get_by_athlete_id.return_value = mock_preferences
    # Default return values so tests that don't explicitly configure these
    # repos still get properly-mocked objects rather than implicit AsyncMocks.
    training_goals_repo.get_active.return_value = mock_active_goal
    twin_states_repo.get_latest.return_value = mock_twin_state
    return ContextBudgetService(
        twin_states=twin_states_repo,
        training_goals=training_goals_repo,
        plans=plans_repo,
        profiles=profiles_repo,
        preferences=preferences_repo,
    )


@pytest.fixture
def athlete_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def mock_twin_state() -> MagicMock:
    ts = MagicMock(spec=TwinState)
    ts.id = uuid.uuid4()
    ts.readiness_level = RecoveryModifierLevel.GREEN
    ts.confidence_level = TwinConfidenceLevel.LOW
    ts.form = 0.0
    ts.data_tier = DataTier.TIER_5
    return ts


@pytest.fixture
def mock_active_goal() -> MagicMock:
    goal = MagicMock()
    goal.goal_type = GoalType.RACE_EVENT
    goal.goal_event_type = MagicMock(value="5K")
    goal.goal_event_date = date(2026, 9, 1)
    goal.goal_description = "Run a 5K race"
    return goal


@pytest.fixture
def mock_active_plan() -> MagicMock:
    plan = MagicMock()
    plan.phases_summary = [
        {"label": "Base", "weeks": 4, "primary_focus": "aerobic base"},
        {"label": "Build", "weeks": 4, "primary_focus": "threshold work"},
    ]
    plan.weekly_distributions = [
        {"session_types": ["easy run", "long run"], "primary_focus": "aerobic base"},
        {"session_types": ["interval", "easy run"], "primary_focus": "threshold work"},
    ]
    return plan


@pytest.fixture
def mock_profile() -> MagicMock:
    profile = MagicMock()
    profile.fitness_level = 3
    profile.recent_injury = None
    return profile


class _MockPreferences:
    """Plain class — not a MagicMock — so attribute access returns real values.

    Using a plain class avoids MagicMock's __getattr__ overriding PropertyMock
    descriptors. All attributes are real Python values, not child mocks.
    """

    def __init__(self) -> None:
        self.sport_background = SportBackground.RUNNING_PRIMARY
        self.years_structured_training = 3


@pytest.fixture
def mock_preferences() -> _MockPreferences:
    return _MockPreferences()


# ---------------------------------------------------------------------------
# Token estimation.
# ---------------------------------------------------------------------------


class TestTokenEstimation:
    """Token estimation uses `len(JSON.stringify(obj)) / 4` — a
    deterministic formula with no external dependencies."""

    def test_returns_integer(self) -> None:
        result = ContextBudgetService.estimate_tokens({"key": "value"})
        assert isinstance(result, int)

    def test_same_input_produces_same_output(self) -> None:
        obj = {"key": "value", "number": 42}
        a = ContextBudgetService.estimate_tokens(obj)
        b = ContextBudgetService.estimate_tokens(obj)
        assert a == b

    def test_longer_content_produces_more_tokens(self) -> None:
        short = {"content": "short"}
        long = {"content": "a" * 1000}
        assert ContextBudgetService.estimate_tokens(long) > ContextBudgetService.estimate_tokens(short)

    def test_handles_empty_dict(self) -> None:
        result = ContextBudgetService.estimate_tokens({})
        assert result >= 0

    def test_handles_nested_structures(self) -> None:
        obj = {
            "profile_summary": {
                "sport_background": "running_primary",
                "years_structured_training": 3,
            },
            "goal_summary": {
                "goal_type": "race_event",
                "weeks_to_event": 10,
            },
        }
        result = ContextBudgetService.estimate_tokens(obj)
        assert result > 0

    def test_estimate_is_conservative_for_token_budget(self) -> None:
        """The formula may over- or under-estimate vs real tokenizers;
        the architecture specifies this as the contract for MVP so
        tests pin the implementation, not absolute accuracy."""
        obj = {"content": "hello world"}
        result = ContextBudgetService.estimate_tokens(obj)
        # At ~2 tokens for "hello world" via tiktoken, our formula
        # should give a higher number (conservative for budget).
        expected = (len('{"content": "hello world"}') + 3) // 4
        assert result == expected


# ---------------------------------------------------------------------------
# MAX_TOKENS thresholds.
# ---------------------------------------------------------------------------


class TestMaxTokens:
    def test_first_message_max_tokens_is_5000(self) -> None:
        assert MAX_TOKENS["first_message"] == 5000


# ---------------------------------------------------------------------------
# Priority profile structure.
# ---------------------------------------------------------------------------


class TestPriorityProfile:
    def test_profile_contains_context_sections(self) -> None:
        assert len(FIRST_MESSAGE_PRIORITY_PROFILE) > 0

    def test_sections_have_names(self) -> None:
        for section in FIRST_MESSAGE_PRIORITY_PROFILE:
            assert section.name
            assert isinstance(section.name, str)

    def test_sections_have_priority_weights_1_to_100(self) -> None:
        for section in FIRST_MESSAGE_PRIORITY_PROFILE:
            assert 1 <= section.priority_weight <= 100

    def test_profile_sections_are_ordered_high_to_low_priority(self) -> None:
        weights = [s.priority_weight for s in FIRST_MESSAGE_PRIORITY_PROFILE]
        assert weights == sorted(weights, reverse=True)


# ---------------------------------------------------------------------------
# Context assembly.
# ---------------------------------------------------------------------------


class TestBuildFirstMessageContext:
    @pytest.mark.asyncio
    async def test_fetches_twin_state(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        twin_states_repo: AsyncMock,
        mock_twin_state: MagicMock,
    ) -> None:
        twin_states_repo.get_latest.return_value = mock_twin_state
        service._twin_states = twin_states_repo  # inject directly

        await service.build_first_message_context(athlete_id)

        twin_states_repo.get_latest.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_fetches_active_goal(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        training_goals_repo: AsyncMock,
        mock_active_goal: MagicMock,
    ) -> None:
        training_goals_repo.get_active.return_value = mock_active_goal

        await service.build_first_message_context(athlete_id)

        training_goals_repo.get_active.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_fetches_active_plan(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        plans_repo: AsyncMock,
        mock_active_plan: MagicMock,
    ) -> None:
        plans_repo.get_active_for_athlete.return_value = mock_active_plan

        await service.build_first_message_context(athlete_id)

        plans_repo.get_active_for_athlete.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_fetches_profile(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        profiles_repo: AsyncMock,
        mock_profile: MagicMock,
    ) -> None:
        profiles_repo.get_by_athlete_id.return_value = mock_profile

        await service.build_first_message_context(athlete_id)

        profiles_repo.get_by_athlete_id.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_fetches_preferences(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        preferences_repo: AsyncMock,
        mock_preferences: MagicMock,
    ) -> None:
        preferences_repo.get_by_athlete_id.return_value = mock_preferences

        await service.build_first_message_context(athlete_id)

        preferences_repo.get_by_athlete_id.assert_called_once_with(athlete_id)

    @pytest.mark.asyncio
    async def test_returns_first_message_context(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        twin_states_repo: AsyncMock,
        training_goals_repo: AsyncMock,
        plans_repo: AsyncMock,
        profiles_repo: AsyncMock,
        preferences_repo: AsyncMock,
        mock_twin_state: MagicMock,
        mock_active_goal: MagicMock,
        mock_active_plan: MagicMock,
        mock_profile: MagicMock,
        mock_preferences: MagicMock,
    ) -> None:
        twin_states_repo.get_latest.return_value = mock_twin_state
        training_goals_repo.get_active.return_value = mock_active_goal
        plans_repo.get_active_for_athlete.return_value = mock_active_plan
        profiles_repo.get_by_athlete_id.return_value = mock_profile
        preferences_repo.get_by_athlete_id.return_value = mock_preferences

        context = await service.build_first_message_context(athlete_id)

        assert isinstance(context, FirstMessageContext)
        assert context.profile_summary is not None
        assert context.goal_summary is not None

    @pytest.mark.asyncio
    async def test_context_includes_computed_observations(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        twin_states_repo: AsyncMock,
        preferences_repo: AsyncMock,
        mock_twin_state: MagicMock,
        mock_preferences: MagicMock,
    ) -> None:
        twin_states_repo.get_latest.return_value = mock_twin_state
        preferences_repo.get_by_athlete_id.return_value = mock_preferences

        context = await service.build_first_message_context(athlete_id)

        assert context.computed_observations is not None
        assert "structural_risk_flag" in context.computed_observations
        assert "aerobic_base_assessment" in context.computed_observations

    @pytest.mark.asyncio
    async def test_context_includes_plan_overview(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        plans_repo: AsyncMock,
        mock_active_plan: MagicMock,
    ) -> None:
        plans_repo.get_active_for_athlete.return_value = mock_active_plan

        context = await service.build_first_message_context(athlete_id)

        assert context.plan_overview is not None
        assert len(context.plan_overview.phases) > 0

    @pytest.mark.asyncio
    async def test_context_includes_first_block_preview(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        plans_repo: AsyncMock,
        mock_active_plan: MagicMock,
    ) -> None:
        plans_repo.get_active_for_athlete.return_value = mock_active_plan

        context = await service.build_first_message_context(athlete_id)

        assert context.first_block_preview is not None

    @pytest.mark.asyncio
    async def test_handles_missing_twin_state(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        twin_states_repo: AsyncMock,
    ) -> None:
        twin_states_repo.get_latest.return_value = None

        context = await service.build_first_message_context(athlete_id)

        assert context.readiness_level == "green"  # fallback
        assert context.confidence_level == "low"  # fallback

    @pytest.mark.asyncio
    async def test_handles_missing_goal(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        training_goals_repo: AsyncMock,
        twin_states_repo: AsyncMock,
        mock_twin_state: MagicMock,
    ) -> None:
        twin_states_repo.get_latest.return_value = mock_twin_state
        training_goals_repo.get_active.return_value = None

        context = await service.build_first_message_context(athlete_id)

        assert context.goal_summary is None

    @pytest.mark.asyncio
    async def test_handles_missing_plan(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        plans_repo: AsyncMock,
        training_goals_repo: AsyncMock,
        twin_states_repo: AsyncMock,
        mock_twin_state: MagicMock,
        mock_active_goal: MagicMock,
    ) -> None:
        twin_states_repo.get_latest.return_value = mock_twin_state
        training_goals_repo.get_active.return_value = mock_active_goal
        plans_repo.get_active_for_athlete.return_value = None

        context = await service.build_first_message_context(athlete_id)

        assert context.plan_overview is None
        assert context.first_block_preview is None

    @pytest.mark.asyncio
    async def test_weeks_to_event_calculation(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        training_goals_repo: AsyncMock,
        twin_states_repo: AsyncMock,
        mock_twin_state: MagicMock,
    ) -> None:
        # Goal event 10 weeks from now
        from datetime import timedelta
        future_date = date.today() + timedelta(weeks=10)
        mock_goal = MagicMock()
        mock_goal.goal_type = GoalType.RACE_EVENT
        mock_goal.goal_event_type = MagicMock(value="5K")
        mock_goal.goal_event_date = future_date
        mock_goal.goal_description = "Run a 5K"

        twin_states_repo.get_latest.return_value = mock_twin_state
        training_goals_repo.get_active.return_value = mock_goal

        context = await service.build_first_message_context(athlete_id)

        assert context.goal_summary is not None
        assert context.goal_summary.weeks_to_event is not None
        assert context.goal_summary.weeks_to_event >= 9  # allow 1 week tolerance

    @pytest.mark.asyncio
    async def test_structural_risk_flag_for_crossover_athlete(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        twin_states_repo: AsyncMock,
        preferences_repo: AsyncMock,
        mock_twin_state: MagicMock,
    ) -> None:
        """Athletes whose primary sport is not running have structural_risk_flag=True."""
        mock_prefs = MagicMock()
        type(mock_prefs).sport_background = PropertyMock(
            return_value=SportBackground.CYCLING_PRIMARY
        )
        type(mock_prefs).years_structured_training = PropertyMock(return_value=5)

        twin_states_repo.get_latest.return_value = mock_twin_state
        preferences_repo.get_by_athlete_id.return_value = mock_prefs

        context = await service.build_first_message_context(athlete_id)

        assert context.computed_observations["structural_risk_flag"] is True
        assert context.computed_observations["structural_risk_reason"] == "non-running primary sport background"

    @pytest.mark.asyncio
    async def test_structural_risk_flag_false_for_running_athlete(
        self,
        service: ContextBudgetService,
        athlete_id: uuid.UUID,
        twin_states_repo: AsyncMock,
        preferences_repo: AsyncMock,
        mock_twin_state: MagicMock,
    ) -> None:
        mock_prefs = MagicMock()
        type(mock_prefs).sport_background = PropertyMock(
            return_value=SportBackground.RUNNING_PRIMARY
        )
        type(mock_prefs).years_structured_training = PropertyMock(return_value=3)

        twin_states_repo.get_latest.return_value = mock_twin_state
        preferences_repo.get_by_athlete_id.return_value = mock_prefs

        context = await service.build_first_message_context(athlete_id)

        assert context.computed_observations["structural_risk_flag"] is False


# ---------------------------------------------------------------------------
# FirstMessageContext.to_dict() serialization.
# ---------------------------------------------------------------------------


class TestFirstMessageContextSerialization:
    def test_to_dict_returns_dict(self) -> None:
        ctx = FirstMessageContext(
            readiness_level="green",
            confidence_level="low",
        )
        result = ctx.to_dict()
        assert isinstance(result, dict)

    def test_to_dict_contains_all_sections(self) -> None:
        ctx = FirstMessageContext(
            readiness_level="green",
            confidence_level="low",
            profile_summary=MagicMock(
                sport_background=MagicMock(value="running_primary"),
                years_structured_training=3,
                fitness_level=3,
                recent_injury=None,
            ),
            goal_summary=MagicMock(
                goal_type=MagicMock(value="race_event"),
                goal_event_type="5K",
                goal_event_date="2026-09-01",
                weeks_to_event=10,
                goal_description="Run a 5K",
            ),
            plan_overview=MagicMock(
                phases=[{"label": "Base", "weeks": 4}],
                total_weeks=8,
            ),
            first_block_preview=MagicMock(
                session_types_in_week_1=["easy run"],
                session_types_in_week_2=["long run"],
                primary_focus="aerobic base",
            ),
        )
        result = ctx.to_dict()
        assert "readiness_level" in result
        assert "confidence_level" in result
        assert "profile_summary" in result
        assert "goal_summary" in result
        assert "plan_overview" in result
        assert "first_block_preview" in result