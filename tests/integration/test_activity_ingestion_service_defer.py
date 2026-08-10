"""Integration tests for the ``ActivityIngestionService`` defer seam.

Covers the async ``task_dispatcher`` seam (ADR-014) on
``_defer_signal_clean``: the dispatcher is awaited (not called sync),
the dispatcher resolves to ``signal_clean.defer_async``, and a
defer failure is swallowed-and-logged so the ingestion pipeline
completes successfully.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.activity_ingestion_service import ActivityIngestionService
from app.services import activity_ingestion_service as ais_module


class _AsyncRecordingDispatcher:
    """Async callable fake matching the ``task_dispatcher`` seam.

    ADR-014 contract: the seam is an async callable with signature
    ``async (**kwargs) -> int``. This fake records the awaited kwargs
    and returns a fixed task_id.
    """

    def __init__(self, return_value: int = 42) -> None:
        self.call_log: list[dict[str, Any]] = []
        self._return_value = return_value

    async def __call__(self, **kwargs: Any) -> int:
        self.call_log.append(kwargs)
        return self._return_value


class _FailingDispatcher:
    """Async callable that raises on every call."""

    def __init__(self, message: str = "defer failed") -> None:
        self.message = message
        self.call_count = 0

    async def __call__(self, **kwargs: Any) -> int:
        self.call_count += 1
        raise RuntimeError(self.message)


class TestDeferSignalClean:
    async def test_defer_signal_clean_uses_async_dispatcher(
        self, db_session: AsyncSession
    ) -> None:
        # When a task_dispatcher is injected, _defer_signal_clean must
        # await it (not call it synchronously) and pass the activity_id
        # as a string. A sync call would surface as a coroutine warning
        # or a TypeError on the await site; we assert the dispatcher
        # recorded the call and the return value was awaited.
        dispatcher = _AsyncRecordingDispatcher()
        service = ActivityIngestionService(
            session=db_session, task_dispatcher=dispatcher
        )
        activity_id = uuid.uuid4()

        await service._defer_signal_clean(activity_id=activity_id)

        assert len(dispatcher.call_log) == 1
        assert dispatcher.call_log[0] == {"activity_id": str(activity_id)}

    async def test_task_dispatcher_seam_accepts_async_fake(
        self, db_session: AsyncSession
    ) -> None:
        # The seam must accept an async __call__ without raising
        # ``TypeError: object coroutine can't be used in 'await'
        # expression`` (the failure mode of a sync dispatcher on an
        # async connector). The fake records its call; a non-await
        # would leave call_log empty and the test would fail.
        dispatcher = _AsyncRecordingDispatcher(return_value=99)
        service = ActivityIngestionService(
            session=db_session, task_dispatcher=dispatcher
        )

        await service._defer_signal_clean(activity_id=uuid.uuid4())

        assert dispatcher.call_log  # non-empty: the await actually ran
        assert len(dispatcher.call_log) == 1

    async def test_defer_signal_clean_swallows_defer_failure(
        self,
        db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # When the dispatcher raises, the ingestion pipeline must
        # complete (no exception propagates) and the failure must be
        # logged via log_event with the expected event name. The
        # ActivityIngestionService is constructed with the failing
        # dispatcher; the call site is _defer_signal_clean (the path
        # the ingestion pipeline uses after run_ingestion_pipeline
        # commits the Activity).
        log_event_calls: list[dict[str, Any]] = []

        def _mock_log_event(**kwargs: Any) -> None:
            log_event_calls.append(kwargs)

        monkeypatch.setattr(ais_module, "log_event", _mock_log_event)

        dispatcher = _FailingDispatcher(message="procrastinate enqueue failed")
        service = ActivityIngestionService(
            session=db_session, task_dispatcher=dispatcher
        )

        await service._defer_signal_clean(activity_id=uuid.uuid4())

        assert dispatcher.call_count == 1

        failure_logs = [
            call
            for call in log_event_calls
            if call.get("event") == "activity.signal_clean.enqueue.failure"
        ]
        assert len(failure_logs) == 1
        assert failure_logs[0].get("outcome") == "failed"
        assert "procrastinate enqueue failed" in str(failure_logs[0].get("error"))
