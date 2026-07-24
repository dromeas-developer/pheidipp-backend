"""Integration regression tests for the re-routed ``outbox_publisher`` task.

Covers scenarios 19-25 of
``docs/implementation/phase-2/phase-2-7/batch-4-outbox-publisher-layer-fix-tests.md``.

Batch 4 re-routed the ``outbox_publisher`` task to call
``OutboxPublisherService.publish_pending`` instead of constructing
``SystemEventOutboxRepository`` and ``AsyncSessionLocal`` directly.
Observable behaviour is preserved from Batch 2 — these tests are
regression-only re-runs of Batch 2's scenarios 7-13, 15, 14 against
the re-routed implementation.

The test pattern mirrors
``tests/integration/test_outbox_publisher_task_integration.py``:
``AsyncSessionLocal`` is monkey-patched on both the worker module
AND the service module so the worker→service→repository chain all
share the same test engine and event loop.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.outbox_publisher_service as service_module
import app.worker.app as worker_module
from app.db.session import AsyncSessionLocal as _production_session_local
from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from tests.utils.factories import make_athlete


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


async def _make_outbox_row(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    status: EventPublicationStatus = EventPublicationStatus.PENDING,
    created_at: datetime | None = None,
) -> SystemEventOutbox:
    """Insert a paired ``SystemEvent`` + ``SystemEventOutbox`` row."""
    event = SystemEvent(
        event_id=uuid.uuid4(),
        event_type="test.outbox_publisher_re_routed",
        version="v1",
        athlete_id=athlete_id,
        payload={"k": "v"},
        produced_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    await db_session.flush()

    kwargs: dict[str, object] = {
        "event_id": event.event_id,
        "status": status,
    }
    if created_at is not None:
        kwargs["created_at"] = created_at
    outbox = SystemEventOutbox(**kwargs)
    db_session.add(outbox)
    await db_session.flush()
    return outbox


async def _run_publisher_task(
    db_session: AsyncSession,
    test_session_local: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """Run the re-routed outbox_publisher task and return its result.

    Monkey-patches ``AsyncSessionLocal`` on both the worker module
    AND the service module so the worker→service→repository chain
    all share the same test engine. The task is invoked directly as
    a coroutine — the procrastinate wrapper is not involved.
    """
    monkeypatch.setattr(worker_module, "AsyncSessionLocal", test_session_local)
    monkeypatch.setattr(
        service_module, "AsyncSessionLocal", test_session_local
    )
    try:
        return await worker_module.outbox_publisher(
            timestamp=int(time.time()),
        )
    finally:
        monkeypatch.setattr(
            worker_module, "AsyncSessionLocal", _production_session_local
        )
        monkeypatch.setattr(
            service_module, "AsyncSessionLocal", _production_session_local
        )


# ---------------------------------------------------------------------------
# Scenario 19 — Batch 2 scenario 7 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherTransitionsPendingToPublished:
    """Scenario 19 — running the re-routed publisher task transitions
    3 pending rows to ``published`` and returns ``published_count=3``.
    Same observable behaviour as Batch 2 scenario 7."""

    @pytest.mark.asyncio
    async def test_three_pending_rows_all_published(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(3):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=base + timedelta(seconds=i),
            )
        await db_session.commit()

        result = await _run_publisher_task(
            db_session, test_session_local, monkeypatch
        )

        assert result["published_count"] == 3

        db_session.expire_all()
        rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert len(rows) == 3
        for row in rows:
            assert row.status is EventPublicationStatus.PUBLISHED
            assert row.published_at is not None


# ---------------------------------------------------------------------------
# Scenario 20 — Batch 2 scenario 8 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherIsIdempotent:
    """Scenario 20 — running the re-routed publisher task twice
    returns 3 on the first run and 0 on the second run."""

    @pytest.mark.asyncio
    async def test_second_run_returns_zero(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        for i in range(3):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=datetime(2026, 7, 1, 12, 0, i, tzinfo=timezone.utc),
            )
        await db_session.commit()

        first = await _run_publisher_task(
            db_session, test_session_local, monkeypatch
        )
        assert first["published_count"] == 3

        second = await _run_publisher_task(
            db_session, test_session_local, monkeypatch
        )
        assert second["published_count"] == 0


# ---------------------------------------------------------------------------
# Scenario 21 — Batch 2 scenario 10 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherHandlesPartialBatch:
    """Scenario 21 — with 150 pending rows and ``limit=100``, the
    re-routed publisher transitions exactly 100 rows and 50 remain
    pending."""

    @pytest.mark.asyncio
    async def test_first_run_transitions_only_limit_rows(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(150):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=base + timedelta(seconds=i),
            )
        await db_session.commit()

        result = await _run_publisher_task(
            db_session, test_session_local, monkeypatch, limit=100
        )
        assert result["published_count"] == 100

        db_session.expire_all()
        published = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.status == EventPublicationStatus.PUBLISHED
                )
            )
        ).scalars().all()
        pending = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.status == EventPublicationStatus.PENDING
                )
            )
        ).scalars().all()
        assert len(published) == 100
        assert len(pending) == 50


# ---------------------------------------------------------------------------
# Scenario 22 — Batch 2 scenario 12 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherDoesNotProduceNewEvents:
    """Scenario 22 — the re-routed publisher does NOT insert new
    ``SystemEvent`` rows. It is a status transitioner, not an event
    producer."""

    @pytest.mark.asyncio
    async def test_event_count_unchanged_after_publisher_run(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        for i in range(3):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=datetime(2026, 7, 1, 12, 0, i, tzinfo=timezone.utc),
            )
        await db_session.commit()

        events_before = (
            await db_session.execute(select(SystemEvent))
        ).scalars().all()
        assert len(events_before) == 3

        result = await _run_publisher_task(
            db_session, test_session_local, monkeypatch
        )
        assert result["published_count"] == 3

        events_after = (
            await db_session.execute(select(SystemEvent))
        ).scalars().all()
        assert len(events_after) == 3


# ---------------------------------------------------------------------------
# Scenario 23 — Batch 2 scenario 13 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherDoesNotCallEventPublisherPublish:
    """Scenario 23 — ``EventPublisher.publish`` is NOT called by the
    re-routed publisher."""

    @pytest.mark.asyncio
    async def test_event_publisher_publish_not_called(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
        )
        await db_session.commit()

        with patch(
            "app.services.event_publisher.EventPublisher.publish",
            autospec=True,
        ) as spy:
            result = await _run_publisher_task(
                db_session, test_session_local, monkeypatch
            )

        assert result["published_count"] == 1
        spy.assert_not_called()


# ---------------------------------------------------------------------------
# Scenario 24 — Batch 2 scenario 15 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherStatusObservableAfterCommit:
    """Scenario 24 — the re-routed publisher's commit makes the
    status transition visible to a fresh session reading the rows."""

    @pytest.mark.asyncio
    async def test_fresh_session_sees_published_status(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        for i in range(3):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=datetime(2026, 7, 1, 12, 0, i, tzinfo=timezone.utc),
            )
        await db_session.commit()

        result = await _run_publisher_task(
            db_session, test_session_local, monkeypatch
        )
        assert result["published_count"] == 3

        async with test_session_local() as fresh_session:
            fresh_rows = (
                await fresh_session.execute(select(SystemEventOutbox))
            ).scalars().all()
            assert len(fresh_rows) == 3
            for row in fresh_rows:
                assert row.status is EventPublicationStatus.PUBLISHED
                assert row.published_at is not None


# ---------------------------------------------------------------------------
# Scenario 25 — Batch 2 scenario 14 regression.
# ---------------------------------------------------------------------------


class TestReRoutedPublisherRunsInOwnTransaction:
    """Scenario 25 — the re-routed publisher runs in its own session;
    an uncommitted row in another session is NOT visible to the
    publisher."""

    @pytest.mark.asyncio
    async def test_uncommitted_row_in_other_session_not_visible(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        # Open a SECOND session to insert a pending row WITHOUT
        # committing. The publisher's session must not see it.
        async with test_session_local() as other_session:
            # The outbox row has a FK to system_events.event_id, so
            # the parent SystemEvent row must exist first.
            event = SystemEvent(
                event_id=uuid.uuid4(),
                event_type="test.uncommitted_row_re_routed",
                version="v1",
                athlete_id=athlete.id,
                payload={"k": "v"},
                produced_at=datetime.now(timezone.utc),
            )
            other_session.add(event)
            await other_session.flush()

            outbox_repo = SystemEventOutboxRepository(other_session)
            uncommitted = await outbox_repo.add(
                event_id=event.event_id,
                status=EventPublicationStatus.PENDING,
            )
            # Note: NOT calling other_session.commit() — the row is
            # only visible inside other_session's transaction.

            result = await _run_publisher_task(
                db_session, test_session_local, monkeypatch
            )
            assert result["published_count"] == 0

            # The uncommitted row still exists in the other session
            # and is still pending.
            await other_session.refresh(uncommitted)
            assert uncommitted.status is EventPublicationStatus.PENDING
