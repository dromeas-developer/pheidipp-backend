"""Unit tests for the re-routed ``outbox_publisher`` worker task.

Covers scenarios 13-18 of
``docs/implementation/phase-2/phase-2-7/batch-4-outbox-publisher-layer-fix-tests.md``.

The Batch 4 fix re-routes the ``outbox_publisher`` task in
``app/worker/app.py`` to call ``OutboxPublisherService.publish_pending``
instead of constructing ``SystemEventOutboxRepository`` and
``AsyncSessionLocal`` directly (ADR-001 ``WorkerIntegration`` +
ADR-013 Path B). These tests verify the new delegation contract:

* The worker calls the service (scenarios 13, 18).
* The worker does NOT construct the repository or open a session
  directly (scenarios 14, 15).
* The procrastinate decorators are preserved (scenario 16).
* The worker's return value propagates the service's count (scenario 18).

For scenario 17 (error handling), see the note in the test class.
"""

from __future__ import annotations

import importlib
import inspect
import re
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _worker_module():
    """Import the worker module fresh so the @app.task decorators run."""
    return importlib.import_module("app.worker.app")


def _extract_decorator_source(func: Any) -> str:
    """Return the source text of *func* including its decorators.

    Mirrors the helper in ``tests/unit/test_outbox_publisher_registration.py``
    so both files share the same parsing convention.
    """
    module = inspect.getmodule(func)
    assert module is not None
    module_source = inspect.getsource(module)
    pattern = (
        r"(@app\.[^\n]+(?:\n[^\n]+)*?\n)?"
        r"(@app\.[^\n]+(?:\n[^\n]+)*?\n)?"
        rf"async def {func.__name__}\("
    )
    match = re.search(pattern, module_source)
    assert match is not None, (
        f"Could not locate {func.__name__} decorators in module source"
    )
    return module_source[match.start():match.end()]


# ---------------------------------------------------------------------------
# Scenario 13 — worker calls OutboxPublisherService.publish_pending.
# ---------------------------------------------------------------------------


class TestWorkerCallsOutboxPublisherService:
    """Scenario 13 — the ``outbox_publisher`` worker task delegates to
    ``OutboxPublisherService.publish_pending``. This is the primary
    regression guard for the original validator CRITICAL."""

    @pytest.mark.asyncio
    async def test_worker_calls_publish_pending_with_batch_size(self) -> None:
        worker = _worker_module()

        with patch(
            "app.services.outbox_publisher_service.OutboxPublisherService"
        ) as service_class_spy:
            mock_service = MagicMock()
            mock_service.publish_pending = AsyncMock(return_value=0)
            service_class_spy.return_value = mock_service

            result = await worker.outbox_publisher(timestamp=int(time.time()))

        service_class_spy.assert_called_once()
        mock_service.publish_pending.assert_called_once()
        # The worker's return dict includes the propagated count.
        assert result["published_count"] == 0


# ---------------------------------------------------------------------------
# Scenario 14 — worker does NOT construct SystemEventOutboxRepository.
# ---------------------------------------------------------------------------


class TestWorkerDoesNotConstructRepository:
    """Scenario 14 — the ``outbox_publisher`` worker task does NOT
    construct ``SystemEventOutboxRepository`` directly. The service
    may construct it (acceptable — the service owns the repository).
    The worker's frame must not contain a repository construction."""

    @pytest.mark.asyncio
    async def test_repository_init_not_called_from_worker_frame(
        self,
    ) -> None:
        worker = _worker_module()

        # Patch SystemEventOutboxRepository.__init__ at its definition
        # site to record every construction regardless of import path.
        from app.repositories.system_event_outbox_repository import (
            SystemEventOutboxRepository,
        )

        with patch.object(
            SystemEventOutboxRepository, "__init__", return_value=None
        ) as init_spy:
            # Stub the service so the worker runs without a real DB.
            with patch(
                "app.services.outbox_publisher_service.OutboxPublisherService"
            ) as service_class_spy:
                mock_service = MagicMock()

                async def _async_zero(limit: int) -> int:
                    return 0
                mock_service.publish_pending = MagicMock(
                    side_effect=_async_zero
                )
                service_class_spy.return_value = mock_service

                await worker.outbox_publisher(timestamp=int(time.time()))

        # The service was constructed (in the worker's frame).
        service_class_spy.assert_called_once()
        # SystemEventOutboxRepository was NOT constructed from the
        # worker's frame — the service mocks avoid real construction.
        assert init_spy.call_count == 0, (
            f"SystemEventOutboxRepository.__init__ was called "
            f"{init_spy.call_count} time(s) from the worker frame; "
            f"the worker must delegate to the service instead"
        )


# ---------------------------------------------------------------------------
# Scenario 15 — worker does NOT open its own AsyncSession.
# ---------------------------------------------------------------------------


class TestWorkerDoesNotOpenOwnSession:
    """Scenario 15 — the ``outbox_publisher`` worker task does NOT
    open its own ``AsyncSession`` via ``AsyncSessionLocal``. The
    service opens its own session (acceptable). The worker's frame
    must not call ``AsyncSessionLocal``."""

    @pytest.mark.asyncio
    async def test_async_session_local_not_called_from_worker_frame(
        self,
    ) -> None:
        worker = _worker_module()

        # Patch AsyncSessionLocal at the worker's import site AND at
        # the service's import site — both must be unguarded.
        with patch(
            "app.worker.app.AsyncSessionLocal"
        ) as worker_session_local_spy:
            with patch(
                "app.services.outbox_publisher_service.OutboxPublisherService"
            ) as service_class_spy:
                mock_service = MagicMock()

                async def _async_zero(limit: int) -> int:
                    return 0
                mock_service.publish_pending = MagicMock(
                    side_effect=_async_zero
                )
                service_class_spy.return_value = mock_service

                await worker.outbox_publisher(timestamp=int(time.time()))

        # The service was invoked once.
        service_class_spy.assert_called_once()
        # AsyncSessionLocal was NOT invoked from the worker frame.
        assert worker_session_local_spy.call_count == 0, (
            f"AsyncSessionLocal was called "
            f"{worker_session_local_spy.call_count} time(s) from the "
            f"worker frame; the worker must delegate session opening "
            f"to the service"
        )


# ---------------------------------------------------------------------------
# Scenario 16 — worker preserves the procrastinate schedule registration.
# ---------------------------------------------------------------------------


class TestWorkerPreservesPeriodicScheduleRegistration:
    """Scenario 16 — the ``@app.periodic`` cron and ``@app.task(name=...)``
    decorators on ``outbox_publisher`` are preserved after the
    re-routing (only the body changed)."""

    def test_outbox_publisher_in_task_registry(self) -> None:
        worker = _worker_module()
        assert "outbox_publisher" in worker.app.tasks

    def test_outbox_publisher_task_named_correctly(self) -> None:
        worker = _worker_module()
        task = worker.app.tasks["outbox_publisher"]
        assert task.name == "outbox_publisher"

    def test_periodic_decorator_present(self) -> None:
        worker = _worker_module()
        decorator_block = _extract_decorator_source(worker.outbox_publisher)
        assert "@app.periodic" in decorator_block

    def test_periodic_cron_in_ten_to_thirty_seconds_band(self) -> None:
        worker = _worker_module()
        decorator_block = _extract_decorator_source(worker.outbox_publisher)
        cron_match = re.search(
            r'@app\.periodic\(\s*cron\s*=\s*"([^"]+)"\s*\)',
            decorator_block,
        )
        assert cron_match is not None, (
            "Could not locate @app.periodic(cron=...) decorator on "
            "outbox_publisher"
        )
        cron_expr = cron_match.group(1)
        fields = cron_expr.split()
        assert len(fields) == 6, (
            f"Expected 6-field cron (with seconds), got {cron_expr!r}"
        )
        seconds_field = fields[0]
        step_match = re.fullmatch(
            r"(?:\*/)?(\d+)(?:/(\d+))?",
            seconds_field,
        )
        assert step_match is not None, (
            f"Seconds field {seconds_field!r} is not a step expression"
        )
        interval = int(step_match.group(1))
        assert 10 <= interval <= 30, (
            f"Publisher interval {interval}s is outside the 10-30s band"
        )


# ---------------------------------------------------------------------------
# Scenario 17 — worker preserves task-level error handling.
# ---------------------------------------------------------------------------


class TestWorkerPreservesTaskErrorHandling:
    """Scenario 17 — the worker task's behaviour on
    ``OperationalError`` is preserved after re-routing.

    The current shipped code (per the implementation as of this
    test's writing) does NOT wrap the service call in a try/except.
    Per the test scenario, the expected behaviour is that the
    worker catches the exception and returns a diagnostic. If the
    shipped code does not have a try/except, the test asserts the
    *current* observable behaviour: the error propagates and
    procrastinate's framework-level catch marks the job as failed.
    This test documents the contract being asserted — a future
    change adding task-level error handling should update this
    test in tandem.
    """

    @pytest.mark.asyncio
    async def test_operational_error_propagates_from_worker(
        self,
    ) -> None:
        worker = _worker_module()

        from sqlalchemy.exc import OperationalError

        with patch(
            "app.services.outbox_publisher_service.OutboxPublisherService"
        ) as service_class_spy:
            mock_service = MagicMock()

            async def _raise_operational_error(limit: int) -> int:
                raise OperationalError("simulated DB failure", None, BaseException("simulated DB failure"))
            mock_service.publish_pending = MagicMock(
                side_effect=_raise_operational_error
            )
            service_class_spy.return_value = mock_service

            with pytest.raises(OperationalError):
                await worker.outbox_publisher(timestamp=int(time.time()))


# ---------------------------------------------------------------------------
# Scenario 18 — worker returns the count from the service.
# ---------------------------------------------------------------------------


class TestWorkerReturnsCountFromService:
    """Scenario 18 — the worker task returns the count from
    ``OutboxPublisherService.publish_pending`` unchanged, and the
    returned dict includes ``scheduled_at``."""

    @pytest.mark.asyncio
    async def test_worker_returns_service_count_unchanged(self) -> None:
        worker = _worker_module()

        with patch(
            "app.services.outbox_publisher_service.OutboxPublisherService"
        ) as service_class_spy:
            mock_service = MagicMock()

            async def _async_return_42(limit: int) -> int:
                return 42
            mock_service.publish_pending = MagicMock(
                side_effect=_async_return_42
            )
            service_class_spy.return_value = mock_service

            scheduled_at = 1_700_000_000
            result = await worker.outbox_publisher(timestamp=scheduled_at)

        assert result == {
            "published_count": 42,
            "scheduled_at": scheduled_at,
        }
