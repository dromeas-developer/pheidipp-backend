"""Integration tests for ``OutboxPublisherService.publish_pending``.

Covers scenarios 5-9 of
``docs/implementation/phase-2/phase-2-7/batch-4-outbox-publisher-layer-fix-tests.md``.

The service is the publish-side transaction owner introduced by
Batch 4 (ADR-013 Path B). It opens its own ``AsyncSession`` via
``AsyncSessionLocal``, fetches pending rows via
``SystemEventOutboxRepository.get_pending``, transitions each to
``published`` via ``mark_published``, and commits.

These tests exercise the service against a real database (the
``test_session_local`` fixture from ``tests/conftest.py``) by
monkey-patching ``AsyncSessionLocal`` on the service module so the
service's own session is bound to the test engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.services.outbox_publisher_service as service_module
from app.db.session import AsyncSessionLocal as _production_session_local
from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)
from app.services.outbox_publisher_service import OutboxPublisherService
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
        event_type="test.outbox_publisher_service",
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


async def _run_service(
    db_session: AsyncSession,
    test_session_local: Any,
    monkeypatch: pytest.MonkeyPatch,
    *,
    limit: int = 100,
) -> int:
    """Run the service against the test engine and return its count.

    Mirrors the worker-task pattern: the service's
    ``AsyncSessionLocal`` is monkey-patched to ``test_session_local``
    so the service's own session is bound to the same engine and
    event loop as the test's ``db_session`` fixture.
    """
    monkeypatch.setattr(
        service_module, "AsyncSessionLocal", test_session_local
    )
    try:
        service = OutboxPublisherService()
        return await service.publish_pending(limit=limit)
    finally:
        monkeypatch.setattr(
            service_module, "AsyncSessionLocal", _production_session_local
        )


# ---------------------------------------------------------------------------
# Scenario 5 — service commits the transaction.
# ---------------------------------------------------------------------------


class TestServiceCommitsTransaction:
    """Scenario 5 — after ``publish_pending`` returns, the status
    transition is observable in a fresh session (the service's
    commit is durable)."""

    @pytest.mark.asyncio
    async def test_fresh_session_observes_published_status(
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

        count = await _run_service(db_session, test_session_local, monkeypatch)
        assert count == 3

        # Fresh session — proves the commit is durable, not a local change.
        async with test_session_local() as fresh_session:
            fresh_rows = (
                await fresh_session.execute(select(SystemEventOutbox))
            ).scalars().all()
            assert len(fresh_rows) == 3
            for row in fresh_rows:
                assert row.status is EventPublicationStatus.PUBLISHED


# ---------------------------------------------------------------------------
# Scenario 6 — service returns the transitioned count.
# ---------------------------------------------------------------------------


class TestServiceReturnsTransitionedCount:
    """Scenario 6 — ``publish_pending`` returns the number of
    ``pending`` rows that were transitioned. Pre-existing
    ``published`` rows are NOT counted."""

    @pytest.mark.asyncio
    async def test_returns_only_pending_count_not_total(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        # 3 pending rows
        for i in range(3):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                status=EventPublicationStatus.PENDING,
                created_at=datetime(2026, 7, 1, 12, 0, i, tzinfo=timezone.utc),
            )
        # 2 pre-existing published rows — must NOT be counted
        for i in range(2):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                status=EventPublicationStatus.PUBLISHED,
                created_at=datetime(2026, 7, 1, 13, 0, i, tzinfo=timezone.utc),
            )
        await db_session.commit()

        count = await _run_service(db_session, test_session_local, monkeypatch)

        # Only the 3 pending rows were transitioned.
        assert count == 3


# ---------------------------------------------------------------------------
# Scenario 7 — service handles empty queue.
# ---------------------------------------------------------------------------


class TestServiceHandlesEmptyQueue:
    """Scenario 7 — ``publish_pending`` on an empty outbox returns 0
    and does not modify any rows."""

    @pytest.mark.asyncio
    async def test_empty_queue_returns_zero(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        count = await _run_service(db_session, test_session_local, monkeypatch)
        assert count == 0

    @pytest.mark.asyncio
    async def test_empty_queue_does_not_modify_published_rows(
        self,
        db_session: AsyncSession,
        test_session_local: Any,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        athlete = await make_athlete(db_session)

        # Pre-existing published row — must remain untouched.
        published_row = await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            status=EventPublicationStatus.PUBLISHED,
        )
        original_published_at = datetime(
            2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc
        )
        published_row.published_at = original_published_at
        await db_session.commit()

        count = await _run_service(db_session, test_session_local, monkeypatch)
        assert count == 0

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
# Scenario 8 — service handles partial batch.
# ---------------------------------------------------------------------------


class TestServiceHandlesPartialBatch:
    """Scenario 8 — ``publish_pending`` respects the ``limit``
    argument. With 150 pending rows and ``limit=100``, exactly
    100 rows transition; 50 remain pending."""

    @pytest.mark.asyncio
    async def test_first_call_transitions_only_limit_rows(
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

        count = await _run_service(
            db_session, test_session_local, monkeypatch, limit=100
        )
        assert count == 100

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
# Scenario 9 — service is idempotent across calls.
# ---------------------------------------------------------------------------


class TestServiceIdempotentAcrossCalls:
    """Scenario 9 — calling ``publish_pending`` twice on the same
    row set transitions 3 rows on the first call and 0 rows on
    the second call."""

    @pytest.mark.asyncio
    async def test_second_call_returns_zero(
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

        first = await _run_service(db_session, test_session_local, monkeypatch)
        assert first == 3

        # Capture state before the second call.
        db_session.expire_all()
        rows = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        snapshot = [(r.event_id, r.published_at) for r in rows]

        second = await _run_service(db_session, test_session_local, monkeypatch)
        assert second == 0

        # No row was modified by the second call.
        db_session.expire_all()
        rows_after = (
            await db_session.execute(select(SystemEventOutbox))
        ).scalars().all()
        assert [
            (r.event_id, r.published_at) for r in rows_after
        ] == snapshot
