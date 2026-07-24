"""Unit tests for ``OutboxPublisherService``.

Covers scenarios 1-4, 10-12 of
``docs/implementation/phase-2/phase-2-7/batch-4-outbox-publisher-layer-fix-tests.md``.

The service is a status transitioner between the ``outbox_publisher``
worker task and the ``SystemEventOutboxRepository``. Per ADR-013
(Path B), the service — not the worker — owns the publish-side
transaction. These tests verify the service's structural contract
without exercising the real database (that coverage lives in
``tests/integration/test_outbox_publisher_service_integration.py``).

Layer-boundary rule (per ``tests/MOCKING_CONTRACT.md``):
* ``AsyncSessionLocal`` is patched at the service module level so
  the service's own session-opening is exercised through a mock.
* ``SystemEventOutboxRepository`` methods are patched individually
  (``get_pending``, ``mark_published``) — the unit test asserts
  *that* the service called them, not *how* the repository works.
* No real database is touched.
"""

from __future__ import annotations

import ast
import importlib
import inspect
import pathlib
import typing
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


_SERVICE_MODULE_PATH = "app.services.outbox_publisher_service"


def _load_service_module():
    return importlib.import_module(_SERVICE_MODULE_PATH)


# ---------------------------------------------------------------------------
# Scenario 1 — service exists with ADR-013 signature.
# ---------------------------------------------------------------------------


class TestPublishPendingSignature:
    """Scenario 1 — ``OutboxPublisherService.publish_pending`` exists,
    is ``async``, and has signature ``publish_pending(self, limit: int) -> int``."""

    def test_publish_pending_method_exists(self) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService

        assert hasattr(OutboxPublisherService, "publish_pending"), (
            "OutboxPublisherService must define publish_pending"
        )

    def test_publish_pending_is_coroutine_function(self) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService

        assert inspect.iscoroutinefunction(
            OutboxPublisherService.publish_pending
        ), "publish_pending must be an async (coroutine) function"

    def test_publish_pending_signature_is_self_limit_int(self) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService

        sig = inspect.signature(OutboxPublisherService.publish_pending)
        params = list(sig.parameters.values())
        # Self + limit
        assert len(params) == 2, (
            f"Expected 2 parameters (self, limit), got {len(params)}"
        )
        assert params[0].name == "self"
        assert params[1].name == "limit"
        # The source file uses ``from __future__ import annotations``
        # (PEP 563), so ``inspect.Parameter.annotation`` returns the
        # raw string ``"int"`` rather than the resolved type. Use
        # ``typing.get_type_hints`` to resolve forward references.
        resolved_hints = typing.get_type_hints(
            OutboxPublisherService.publish_pending
        )
        assert resolved_hints["limit"] is int, (
            f"limit annotation must be int, got {resolved_hints['limit']!r}"
        )
        assert resolved_hints["return"] is int, (
            f"Return annotation must be int, got {resolved_hints['return']!r}"
        )

    def test_publish_pending_no_session_argument_on_public_signature(
        self,
    ) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService

        sig = inspect.signature(OutboxPublisherService.publish_pending)
        param_names = [p.name for p in sig.parameters.values()]
        assert "session" not in param_names, (
            "publish_pending must NOT take a session argument — the "
            "service owns its own AsyncSession per ADR-013"
        )


# ---------------------------------------------------------------------------
# Scenario 2 — service opens its own AsyncSession.
# ---------------------------------------------------------------------------


class TestPublishPendingOpensOwnSession:
    """Scenario 2 — the service opens its own ``AsyncSession`` via
    ``AsyncSessionLocal``; no session is passed in by the caller."""

    @pytest.mark.asyncio
    async def test_async_session_local_invoked_inside_service(self) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService
        from app.repositories.system_event_outbox_repository import (
            SystemEventOutboxRepository,
        )

        # Build a mock session context manager.
        mock_session = MagicMock(name="session")
        mock_session.commit = AsyncMock(name="session.commit")

        mock_session_cm = MagicMock(name="session_cm")
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            f"{_SERVICE_MODULE_PATH}.AsyncSessionLocal",
            return_value=mock_session_cm,
        ) as session_local_spy:
            # Mock the repository so we don't reach into the real DB.
            mock_repo = MagicMock(spec=SystemEventOutboxRepository)
            mock_repo.get_pending = AsyncMock(return_value=[])
            mock_repo.mark_published = AsyncMock()

            with patch(
                f"{_SERVICE_MODULE_PATH}.SystemEventOutboxRepository",
                return_value=mock_repo,
            ):
                service = OutboxPublisherService()
                result = await service.publish_pending(limit=10)

        # AsyncSessionLocal was invoked.
        session_local_spy.assert_called_once()
        # The service returned 0 (empty pending list).
        assert result == 0
        # The context manager was used (entered and exited).
        mock_session_cm.__aenter__.assert_awaited_once()
        mock_session_cm.__aexit__.assert_awaited_once()
        # commit was called on the service's own session.
        mock_session.commit.assert_awaited_once()


# ---------------------------------------------------------------------------
# Scenario 3 — service calls SystemEventOutboxRepository.get_pending.
# ---------------------------------------------------------------------------


class TestPublishPendingCallsGetPending:
    """Scenario 3 — ``publish_pending`` calls
    ``SystemEventOutboxRepository.get_pending(limit)`` and returns the
    count of rows returned."""

    @pytest.mark.asyncio
    async def test_get_pending_called_with_limit_and_count_returned(
        self,
    ) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService
        from app.repositories.system_event_outbox_repository import (
            SystemEventOutboxRepository,
        )

        row1, row2, row3 = MagicMock(), MagicMock(), MagicMock()

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            f"{_SERVICE_MODULE_PATH}.AsyncSessionLocal",
            return_value=mock_session_cm,
        ):
            mock_repo = MagicMock(spec=SystemEventOutboxRepository)
            mock_repo.get_pending = AsyncMock(
                return_value=[row1, row2, row3]
            )
            mock_repo.mark_published = AsyncMock()

            with patch(
                f"{_SERVICE_MODULE_PATH}.SystemEventOutboxRepository",
                return_value=mock_repo,
            ):
                service = OutboxPublisherService()
                result = await service.publish_pending(limit=10)

        # get_pending was called with limit=10.
        mock_repo.get_pending.assert_awaited_once_with(10)
        # Service returned 3 (the count of pending rows).
        assert result == 3


# ---------------------------------------------------------------------------
# Scenario 4 — service iterates mark_published per pending row.
# ---------------------------------------------------------------------------


class TestPublishPendingIteratesMarkPublished:
    """Scenario 4 — ``publish_pending`` calls
    ``SystemEventOutboxRepository.mark_published`` once per pending
    row's ``event_id``."""

    @pytest.mark.asyncio
    async def test_mark_published_called_once_per_pending_row(
        self,
    ) -> None:
        from app.services.outbox_publisher_service import OutboxPublisherService
        from app.repositories.system_event_outbox_repository import (
            SystemEventOutboxRepository,
        )

        # Build three mock pending rows with distinguishable event_ids.
        event_id_1 = "11111111-1111-1111-1111-111111111111"
        event_id_2 = "22222222-2222-2222-2222-222222222222"
        event_id_3 = "33333333-3333-3333-3333-333333333333"

        row1 = MagicMock()
        row1.event_id = event_id_1
        row2 = MagicMock()
        row2.event_id = event_id_2
        row3 = MagicMock()
        row3.event_id = event_id_3

        mock_session = MagicMock()
        mock_session.commit = AsyncMock()

        mock_session_cm = MagicMock()
        mock_session_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_cm.__aexit__ = AsyncMock(return_value=None)

        with patch(
            f"{_SERVICE_MODULE_PATH}.AsyncSessionLocal",
            return_value=mock_session_cm,
        ):
            mock_repo = MagicMock(spec=SystemEventOutboxRepository)
            mock_repo.get_pending = AsyncMock(
                return_value=[row1, row2, row3]
            )
            mock_repo.mark_published = AsyncMock()

            with patch(
                f"{_SERVICE_MODULE_PATH}.SystemEventOutboxRepository",
                return_value=mock_repo,
            ):
                service = OutboxPublisherService()
                result = await service.publish_pending(limit=10)

        # mark_published was called exactly three times.
        assert mock_repo.mark_published.await_count == 3
        # Each call passed the row's event_id.
        called_event_ids = [
            call.args[0] for call in mock_repo.mark_published.await_args_list
        ]
        assert called_event_ids == [event_id_1, event_id_2, event_id_3]
        # Return value matches the number of mark_published calls.
        assert result == 3


# ---------------------------------------------------------------------------
# Scenario 10 — service is registered in app.services.__all__.
# ---------------------------------------------------------------------------


class TestServiceRegisteredInAll:
    """Scenario 10 — ``OutboxPublisherService`` is exported via
    ``app.services.__all__`` and importable as
    ``from app.services import OutboxPublisherService``."""

    def test_outbox_publisher_service_in_all(self) -> None:
        import app.services as services_module

        assert "OutboxPublisherService" in services_module.__all__, (
            "OutboxPublisherService must be listed in app.services.__all__"
        )

    def test_outbox_publisher_service_importable_from_package(self) -> None:
        # If the symbol is in __all__ but not actually importable,
        # the contract is still broken.
        from app.services import OutboxPublisherService  # noqa: F401

        assert OutboxPublisherService is not None


# ---------------------------------------------------------------------------
# Scenario 11 — service does not import EventPublisher.
# ---------------------------------------------------------------------------


class TestServiceDoesNotImportEventPublisher:
    """Scenario 11 — the service does not import ``EventPublisher``;
    it is a status transitioner, not a write-side participant."""

    def test_no_event_publisher_import_in_service_module(self) -> None:
        module = _load_service_module()
        # Walk the module's namespace for any symbol containing
        # "EventPublisher" or "event_publisher".
        for name in dir(module):
            assert "EventPublisher" not in name, (
                f"OutboxPublisherService module must not expose "
                f"EventPublisher — found symbol {name!r}"
            )

    def test_no_event_publisher_import_in_source(self) -> None:
        # Defensive: parse the AST and confirm no import names
        # reference event_publisher.
        source_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "app"
            / "services"
            / "outbox_publisher_service.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                imported_names = {alias.name for alias in node.names}
                assert "EventPublisher" not in imported_names, (
                    f"outbox_publisher_service.py imports "
                    f"EventPublisher at line {node.lineno}"
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert "event_publisher" not in alias.name, (
                        f"outbox_publisher_service.py imports "
                        f"{alias.name} at line {node.lineno}"
                    )


# ---------------------------------------------------------------------------
# Scenario 12 — service does not import any message bus client.
# ---------------------------------------------------------------------------


class TestServiceDoesNotImportMessageBus:
    """Scenario 12 — the service does not import any external message
    bus client (redis, nats, kafka, aio_pika, etc.). It is a status
    transitioner only."""

    @pytest.mark.parametrize(
        "bus_module",
        ["redis", "nats", "kafka", "aio_pika", "aiormq", "pika", "kombu",
         "celery", "pubsub"],
    )
    def test_service_does_not_import_bus_client(self, bus_module: str) -> None:
        source_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "app"
            / "services"
            / "outbox_publisher_service.py"
        )
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] == bus_module:
                    pytest.fail(
                        f"outbox_publisher_service.py imports from "
                        f"{node.module!r} at line {node.lineno} — "
                        f"the service must not import a message bus client"
                    )
                for alias in node.names:
                    assert bus_module not in alias.name, (
                        f"outbox_publisher_service.py imports "
                        f"{alias.name!r} at line {node.lineno}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    assert top_level != bus_module, (
                        f"outbox_publisher_service.py imports "
                        f"{alias.name!r} at line {node.lineno}"
                    )
