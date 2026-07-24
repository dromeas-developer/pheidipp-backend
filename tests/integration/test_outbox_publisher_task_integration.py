"""Integration tests for the ``outbox_publisher`` procrastinate task.

Covers scenarios 7-15 of
``docs/implementation/phase-2/phase-2-7/batch-2-outbox-publisher-tests.md``.

The publisher task in ``app/worker/app.py`` opens its own
``AsyncSessionLocal`` session, fetches pending outbox rows via
``SystemEventOutboxRepository.get_pending``, transitions each to
``published`` via ``mark_published``, and commits. The test pattern
mirrors ``tests/integration/test_discard_refresh_token_ips.py``:
``AsyncSessionLocal`` is monkeypatched to ``test_session_local`` so
the task body and the test session share the same test engine and
event loop. The task is invoked directly as a coroutine — the
procrastinate wrapper is not involved.
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

import app.worker.app as worker_module
import app.services.outbox_publisher_service as publisher_service_module
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
# Helpers — row builders + a publisher-body invoker.
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
        event_type="test.outbox_publisher",
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


async def _run_publisher_body(
    db_session: AsyncSession,
    test_session_local: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    limit: int = 100,
) -> dict[str, Any]:
    """Run the outbox_publisher task body and return its result.

    Mirrors the task body in ``app/worker/app.py`` step for step,
    using the per-test ``test_session_local`` so the task's
    session is bound to the same engine and event loop as the
    test's own ``db_session`` fixture.

    The publisher service (``OutboxPublisherService``) imports
    ``AsyncSessionLocal`` directly from ``app.db.session`` at
    module load time, so the monkeypatch must target the service
    module — not the worker module — for the service to use the
    test's session factory.
    """
    monkeypatch.setattr(
        publisher_service_module, "AsyncSessionLocal", test_session_local
    )
    try:
        return await worker_module.outbox_publisher(
            timestamp=int(time.time()),
        )
    finally:
        # Restore so a later test in the same session does not see
        # the monkeypatched value if any shared module state is reused.
        monkeypatch.setattr(
            publisher_service_module, "AsyncSessionLocal", _production_session_local
        )


# ---------------------------------------------------------------------------
# Test: status transition (scenario 7).
# ---------------------------------------------------------------------------


class TestPublisherTransitionsPendingToPublished:
    """Scenario 7 — running the publisher transitions all pending rows."""

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

        result = await _run_publisher_body(
            db_session,
            test_session_local,
            monkeypatch,
        )

        assert result["published_count"] == 3

        # All rows now show status='published' with published_at set.
        db_session.expire_all()
        rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert len(rows) == 3
        for row in rows:
            assert row.status is EventPublicationStatus.PUBLISHED
            assert row.published_at is not None


# ---------------------------------------------------------------------------
# Test: idempotency (scenario 8).
# ---------------------------------------------------------------------------


class TestPublisherIsIdempotent:
    """Scenario 8 — running the publisher twice transitions 3 rows on the
    first run and 0 rows on the second run."""

    @pytest.mark.asyncio
    async def test_second_run_returns_zero_and_modifies_nothing(
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

        first = await _run_publisher_body(
            db_session, test_session_local, monkeypatch
        )
        assert first["published_count"] == 3

        # Capture state before the second run.
        db_session.expire_all()
        rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        snapshot = [(r.event_id, r.published_at) for r in rows]

        second = await _run_publisher_body(
            db_session, test_session_local, monkeypatch
        )
        assert second["published_count"] == 0

        # No row was modified by the second run.
        db_session.expire_all()
        rows_after = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert [
            (r.event_id, r.published_at) for r in rows_after
        ] == snapshot


# ---------------------------------------------------------------------------
# Test: empty queue (scenario 9).
# ---------------------------------------------------------------------------


class TestPublisherHandlesEmptyQueue:
    """Scenario 9 — running with no pending rows returns 0, no error."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_zero(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        result = await _run_publisher_body(
            db_session, test_session_local, monkeypatch
        )
        assert result["published_count"] == 0

    @pytest.mark.asyncio
    async def test_empty_queue_does_not_modify_existing_published_rows(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        # Pre-existing published rows must remain untouched.
        published_row = await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            status=EventPublicationStatus.PUBLISHED,
        )
        original_published_at = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        published_row.published_at = original_published_at
        await db_session.commit()

        result = await _run_publisher_body(
            db_session, test_session_local, monkeypatch
        )
        assert result["published_count"] == 0

        db_session.expire_all()
        row = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.event_id == published_row.event_id
                )
            )
        ).scalars().one()
        assert row.published_at == original_published_at
        assert row.status is EventPublicationStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Test: partial batch (scenarios 10-11).
# ---------------------------------------------------------------------------


class TestPublisherHandlesPartialBatch:
    """Scenarios 10-11 — 150 pending rows, limit=100, first run transitions
    100 rows, second run transitions the remaining 50."""

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

        first = await _run_publisher_body(
            db_session, test_session_local, monkeypatch, limit=100
        )
        assert first["published_count"] == 100

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

    @pytest.mark.asyncio
    async def test_second_run_transitions_remaining_rows(
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

        first = await _run_publisher_body(
            db_session, test_session_local, monkeypatch, limit=100
        )
        assert first["published_count"] == 100

        second = await _run_publisher_body(
            db_session, test_session_local, monkeypatch, limit=100
        )
        assert second["published_count"] == 50

        db_session.expire_all()
        pending = (
            await db_session.execute(
                select(SystemEventOutbox).where(
                    SystemEventOutbox.status == EventPublicationStatus.PENDING
                )
            )
        ).scalars().all()
        assert len(pending) == 0


# ---------------------------------------------------------------------------
# Test: no new domain events produced (scenario 12).
# ---------------------------------------------------------------------------


class TestPublisherDoesNotProduceNewEvents:
    """Scenario 12 — running the publisher does not insert new
    ``SystemEvent`` rows; it is a status transitioner, not an event producer."""

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

        result = await _run_publisher_body(
            db_session, test_session_local, monkeypatch
        )
        assert result["published_count"] == 3

        events_after = (
            await db_session.execute(select(SystemEvent))
        ).scalars().all()
        assert len(events_after) == 3


# ---------------------------------------------------------------------------
# Test: EventPublisher.publish is not called (scenario 13).
# ---------------------------------------------------------------------------


class TestPublisherDoesNotCallEventPublisherPublish:
    """Scenario 13 — the publisher does not call EventPublisher.publish.
    The publisher is a status transitioner, not a write-side producer."""

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
            result = await _run_publisher_body(
                db_session, test_session_local, monkeypatch
            )

        assert result["published_count"] == 1
        spy.assert_not_called()


# ---------------------------------------------------------------------------
# Test: own transaction (scenario 14).
# ---------------------------------------------------------------------------


class TestPublisherRunsInOwnTransaction:
    """Scenario 14 — the publisher runs in its own session; an
    uncommitted row in another session is not visible to the publisher."""

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
                event_type="test.uncommitted_row",
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

            result = await _run_publisher_body(
                db_session, test_session_local, monkeypatch
            )
            assert result["published_count"] == 0

            # The uncommitted row still exists in the other session
            # and is still pending.
            await other_session.refresh(uncommitted)
            assert uncommitted.status is EventPublicationStatus.PENDING


# ---------------------------------------------------------------------------
# Test: commit visibility (scenario 15).
# ---------------------------------------------------------------------------


class TestPublisherStatusTransitionObservableAfterCommit:
    """Scenario 15 — the publisher's commit makes the status transition
    visible to a fresh session reading the rows."""

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

        result = await _run_publisher_body(
            db_session, test_session_local, monkeypatch
        )
        assert result["published_count"] == 3

        # Open a fresh session and read — the publisher's commit
        # is visible.
        async with test_session_local() as fresh_session:
            fresh_rows = (
                await fresh_session.execute(select(SystemEventOutbox))
            ).scalars().all()
            assert len(fresh_rows) == 3
            for row in fresh_rows:
                assert row.status is EventPublicationStatus.PUBLISHED
                assert row.published_at is not None
