"""Unit tests for UnitOfWork."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.unit_of_work import UnitOfWork


@pytest.fixture
def mock_session_not_in_transaction():
    """Mock session that is not in a transaction."""
    session = MagicMock(spec=AsyncSession)
    session.in_transaction = MagicMock(return_value=False)
    session.begin = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


@pytest.fixture
def mock_session_in_transaction():
    """Mock session that is already in a transaction."""
    session = MagicMock(spec=AsyncSession)
    session.in_transaction = MagicMock(return_value=True)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.flush = AsyncMock()
    return session


class TestUnitOfWorkEnter:
    """Tests for UnitOfWork.__aenter__."""

    @pytest.mark.asyncio
    async def test_aenter_starts_transaction_when_not_in_one(
        self, mock_session_not_in_transaction
    ):
        """Verify __aenter__ starts a transaction when session is not already in one."""
        uow = UnitOfWork(mock_session_not_in_transaction)
        async with uow:
            mock_session_not_in_transaction.begin.assert_called_once()

    @pytest.mark.asyncio
    async def test_aenter_does_not_start_new_transaction_when_already_in_one(
        self, mock_session_in_transaction
    ):
        """Verify __aenter__ does NOT start a new transaction when session is already in one."""
        uow = UnitOfWork(mock_session_in_transaction)
        async with uow:
            mock_session_in_transaction.begin.assert_not_called()


class TestUnitOfWorkExit:
    """Tests for UnitOfWork.__aexit__."""

    @pytest.mark.asyncio
    async def test_aexit_commits_on_successful_exit(self, mock_session_in_transaction):
        """Verify __aexit__ commits on successful exit."""
        uow = UnitOfWork(mock_session_in_transaction)
        async with uow:
            pass
        mock_session_in_transaction.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_aexit_rollbacks_when_exception_raised(
        self, mock_session_not_in_transaction
    ):
        """Verify __aexit__ rolls back when an exception is raised."""
        uow = UnitOfWork(mock_session_not_in_transaction)
        with pytest.raises(ValueError):
            async with uow:
                raise ValueError("Test error")
        mock_session_not_in_transaction.rollback.assert_called_once()


class TestUnitOfWorkRepositories:
    """Tests for UnitOfWork repository access."""

    @pytest.mark.asyncio
    async def test_exposes_all_five_repositories(self, mock_session_not_in_transaction):
        """Verify UnitOfWork exposes all five repositories via attribute access."""
        uow = UnitOfWork(mock_session_not_in_transaction)
        async with uow as u:
            assert hasattr(u, "athletes")
            assert hasattr(u, "preferences")
            assert hasattr(u, "blocks")
            assert hasattr(u, "twin_states")
            assert hasattr(u, "profiles")

    @pytest.mark.asyncio
    async def test_accessing_repository_outside_async_with_raises_runtime_error(
        self, mock_session_not_in_transaction
    ):
        """Verify accessing a repository outside of 'async with' raises RuntimeError."""
        uow = UnitOfWork(mock_session_not_in_transaction)
        with pytest.raises(RuntimeError) as exc_info:
            uow.athletes
        assert "must be used with 'async with'" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_accessing_unknown_attribute_raises_attribute_error(
        self, mock_session_not_in_transaction
    ):
        """Verify accessing an unknown attribute raises AttributeError listing available keys."""
        uow = UnitOfWork(mock_session_not_in_transaction)
        async with uow:
            with pytest.raises(AttributeError) as exc_info:
                uow.unknown_repo
        assert "Available:" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_each_repository_uses_uow_session(
        self, mock_session_not_in_transaction
    ):
        """Verify each repository is constructed with the UoW's session (not a separate session)."""
        uow = UnitOfWork(mock_session_not_in_transaction)
        async with uow as u:
            # Verify that the repositories were created with the session
            # by checking that the session was passed to the repository constructors
            # The repositories should have the same session
            assert u.athletes.session is mock_session_not_in_transaction
            assert u.preferences.session is mock_session_not_in_transaction
            assert u.blocks.session is mock_session_not_in_transaction
            assert u.twin_states.session is mock_session_not_in_transaction
            assert u.profiles.session is mock_session_not_in_transaction