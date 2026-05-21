"""Unit tests for generate_training_plan background task."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.enums import GenerationOutcome
from app.tasks.plan_generation_task import generate_training_plan


def _make_mock_session():
    """Create a mock session that supports async context manager."""
    session = MagicMock()
    session.close = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    return session


def _make_mock_uow_class(uow_impl):
    """Create a mock UnitOfWork class that supports async context manager."""
    mock_class = MagicMock()
    mock_instance = MagicMock()
    mock_instance.__aenter__ = AsyncMock(return_value=uow_impl)
    mock_instance.__aexit__ = AsyncMock(return_value=None)
    mock_class.return_value = mock_instance
    return mock_class


class TestGenerateTrainingPlanTask:
    @pytest.mark.asyncio
    async def test_task_checks_active_plan_first_and_returns_early(self):
        athlete_id = uuid.uuid4()
        uow = MagicMock()
        uow.training_plans.get_active_by_athlete = AsyncMock(return_value=MagicMock())

        mock_session = _make_mock_session()
        mock_uow_class = _make_mock_uow_class(uow)

        with patch("app.tasks.plan_generation_task.AsyncSessionLocal", return_value=mock_session):
            with patch("app.tasks.plan_generation_task.UnitOfWork", mock_uow_class):
                with patch("app.tasks.plan_generation_task.TrainingPlanService") as mock_svc:
                    await generate_training_plan(athlete_id)

                    mock_svc.assert_not_called()

    @pytest.mark.asyncio
    async def test_task_logs_missing_data_when_athlete_not_found(self):
        athlete_id = uuid.uuid4()
        uow = MagicMock()
        uow.training_plans.get_active_by_athlete = AsyncMock(return_value=None)
        uow.athletes.get_by_id = AsyncMock(return_value=None)

        mock_session = _make_mock_session()
        mock_uow_class = _make_mock_uow_class(uow)

        with patch("app.tasks.plan_generation_task.AsyncSessionLocal", return_value=mock_session):
            with patch("app.tasks.plan_generation_task.UnitOfWork", mock_uow_class):
                with patch("app.tasks.plan_generation_task.log_generation_event") as mock_log:
                    await generate_training_plan(athlete_id)

                    mock_log.assert_called()
                    call_args = mock_log.call_args[0][0]
                    assert call_args.outcome == GenerationOutcome.MISSING_DATA

    @pytest.mark.asyncio
    async def test_task_calls_service_generate_plan_when_all_data_present(self):
        athlete_id = uuid.uuid4()
        uow = MagicMock()
        uow.training_plans.get_active_by_athlete = AsyncMock(return_value=None)
        uow.athletes.get_by_id = AsyncMock(return_value=MagicMock())
        uow.preferences.get_by_athlete = AsyncMock(return_value=MagicMock())
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=MagicMock())
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=MagicMock())

        mock_service = MagicMock()
        mock_service.generate_plan = AsyncMock(return_value=MagicMock())

        mock_session = _make_mock_session()
        mock_uow_class = _make_mock_uow_class(uow)

        with patch("app.tasks.plan_generation_task.AsyncSessionLocal", return_value=mock_session):
            with patch("app.tasks.plan_generation_task.UnitOfWork", mock_uow_class):
                with patch(
                    "app.tasks.plan_generation_task.TrainingPlanService",
                    return_value=mock_service
                ):
                    await generate_training_plan(athlete_id)

                    mock_service.generate_plan.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_catches_exceptions_and_does_not_reraise(self):
        athlete_id = uuid.uuid4()
        uow = MagicMock()
        uow.training_plans.get_active_by_athlete = AsyncMock(return_value=None)
        uow.athletes.get_by_id = AsyncMock(side_effect=Exception("DB error"))

        mock_session = _make_mock_session()
        mock_uow_class = _make_mock_uow_class(uow)

        with patch("app.tasks.plan_generation_task.AsyncSessionLocal", return_value=mock_session):
            with patch("app.tasks.plan_generation_task.UnitOfWork", mock_uow_class):
                with patch("app.tasks.plan_generation_task.TrainingPlanService"):
                    # Should not raise
                    await generate_training_plan(athlete_id)

    @pytest.mark.asyncio
    async def test_task_closes_session_in_finally_block(self):
        athlete_id = uuid.uuid4()
        uow = MagicMock()
        uow.training_plans.get_active_by_athlete = AsyncMock(return_value=MagicMock())

        mock_session = _make_mock_session()
        mock_uow_class = _make_mock_uow_class(uow)

        with patch("app.tasks.plan_generation_task.AsyncSessionLocal", return_value=mock_session):
            with patch("app.tasks.plan_generation_task.UnitOfWork", mock_uow_class):
                with patch("app.tasks.plan_generation_task.TrainingPlanService"):
                    await generate_training_plan(athlete_id)

                    mock_session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_task_constructs_service_with_required_dependencies(self):
        athlete_id = uuid.uuid4()
        uow = MagicMock()
        uow.training_plans.get_active_by_athlete = AsyncMock(return_value=None)
        uow.athletes.get_by_id = AsyncMock(return_value=MagicMock())
        uow.preferences.get_by_athlete = AsyncMock(return_value=MagicMock())
        uow.blocks.get_active_by_athlete = AsyncMock(return_value=MagicMock())
        uow.twin_states.get_by_athlete_id = AsyncMock(return_value=MagicMock())

        mock_service = MagicMock()
        mock_service.generate_plan = AsyncMock()

        mock_session = _make_mock_session()
        mock_uow_class = _make_mock_uow_class(uow)

        with patch("app.tasks.plan_generation_task.AsyncSessionLocal", return_value=mock_session):
            with patch("app.tasks.plan_generation_task.UnitOfWork", mock_uow_class):
                with patch(
                    "app.tasks.plan_generation_task.TrainingPlanService"
                ) as mock_svc_class:
                    mock_svc_class.return_value = mock_service

                    await generate_training_plan(athlete_id)

                    mock_svc_class.assert_called_once()
                    call_kwargs = mock_svc_class.call_args.kwargs
                    assert len(call_kwargs) >= 7  # All dependencies
