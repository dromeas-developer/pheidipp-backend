"""Integration tests for ``SystemEventOutboxRepository.get_pending``.

Covers scenarios 1-6 of
``docs/implementation/phase-2/phase-2-7/batch-2-outbox-publisher-tests.md``.

The repository's ``get_pending(limit)`` method is the publisher's
read-side: it returns outbox rows in the ``pending`` state, ordered
by ``created_at`` so publication proceeds in commit order. The
method must be read-only — no flush, no commit, no implicit status
transition.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_event import (
    EventPublicationStatus,
    SystemEvent,
    SystemEventOutbox,
)
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from tests.utils.factories import make_athlete


async def _make_outbox_row(
    db_session: AsyncSession,
    *,
    athlete_id: uuid.UUID,
    status: EventPublicationStatus = EventPublicationStatus.PENDING,
    created_at: datetime | None = None,
) -> SystemEventOutbox:
    """Insert a ``SystemEvent`` + paired ``SystemEventOutbox`` row.

    Returns the outbox row. The outbox ``created_at`` is set to the
    explicit value (so tests can control ordering) or to ``func.now()``
    server-side default if ``None``.
    """
    event = SystemEvent(
        event_id=uuid.uuid4(),
        event_type="test.outbox_get_pending",
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


class TestGetPendingReturnsPendingRowsOrdered:
    """Scenario 1 — get_pending returns pending rows ordered by created_at ASC."""

    @pytest.mark.asyncio
    async def test_returns_all_pending_rows_within_limit(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(5):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                status=EventPublicationStatus.PENDING,
                created_at=base + timedelta(seconds=i),
            )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=10)

        assert len(rows) == 5
        for row in rows:
            assert row.status is EventPublicationStatus.PENDING

    @pytest.mark.asyncio
    async def test_results_ordered_by_created_at_ascending(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        created = [
            base + timedelta(seconds=4),
            base + timedelta(seconds=1),
            base + timedelta(seconds=3),
            base + timedelta(seconds=0),
            base + timedelta(seconds=2),
        ]
        for ts in created:
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=ts,
            )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=10)

        assert [r.created_at for r in rows] == sorted(created)


class TestGetPendingExcludesPublishedRows:
    """Scenario 2 — get_pending does not return published rows."""

    @pytest.mark.asyncio
    async def test_does_not_return_published_rows(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(3):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                status=EventPublicationStatus.PENDING,
                created_at=base + timedelta(seconds=i),
            )
        for i in range(2):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                status=EventPublicationStatus.PUBLISHED,
                created_at=base + timedelta(seconds=10 + i),
            )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=10)

        assert len(rows) == 3
        assert all(r.status is EventPublicationStatus.PENDING for r in rows)

    @pytest.mark.asyncio
    async def test_does_not_return_failed_or_dlq_rows(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            status=EventPublicationStatus.PENDING,
            created_at=base,
        )
        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            status=EventPublicationStatus.FAILED,
            created_at=base + timedelta(seconds=1),
        )
        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            status=EventPublicationStatus.DLQ,
            created_at=base + timedelta(seconds=2),
        )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=10)

        assert len(rows) == 1
        assert rows[0].status is EventPublicationStatus.PENDING


class TestGetPendingRespectsLimit:
    """Scenario 3 — get_pending respects the limit argument."""

    @pytest.mark.asyncio
    async def test_returns_at_most_limit_rows(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        for i in range(10):
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=base + timedelta(seconds=i),
            )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=5)

        assert len(rows) == 5

    @pytest.mark.asyncio
    async def test_limit_returns_oldest_by_created_at(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        base = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        all_timestamps = [base + timedelta(seconds=i) for i in range(10)]
        for ts in all_timestamps:
            await _make_outbox_row(
                db_session,
                athlete_id=athlete.id,
                created_at=ts,
            )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=5)

        returned = [r.created_at for r in rows]
        assert returned == sorted(all_timestamps)[:5]


class TestGetPendingEmptyQueue:
    """Scenario 4 — get_pending on empty outbox returns [] with no error."""

    @pytest.mark.asyncio
    async def test_returns_empty_list_when_no_rows(
        self, db_session: AsyncSession
    ) -> None:
        repo = SystemEventOutboxRepository(db_session)
        rows = await repo.get_pending(limit=10)

        assert rows == []


class TestGetPendingIsReadOnly:
    """Scenario 5 — get_pending is read-only: no flush, no commit, no
    implicit status transition."""

    @pytest.mark.asyncio
    async def test_does_not_modify_status(
        self, db_session: AsyncSession
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

        repo = SystemEventOutboxRepository(db_session)
        returned = await repo.get_pending(limit=10)

        assert len(returned) == 3
        for row in returned:
            assert row.status is EventPublicationStatus.PENDING

        # Re-query the rows in a fresh read — they should still be
        # 'pending' in the same session (no implicit status transition).
        db_session.expire_all()
        status_check = (
            await db_session.execute(
                select(SystemEventOutbox.status).where(
                    SystemEventOutbox.event_id.in_(
                        [r.event_id for r in returned]
                    )
                )
            )
        ).scalars().all()

        assert all(s is EventPublicationStatus.PENDING for s in status_check)

    @pytest.mark.asyncio
    async def test_published_at_remains_null(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
        )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        await repo.get_pending(limit=10)

        # The row's published_at must remain null — get_pending does
        # not stamp it.
        result = await db_session.execute(
            select(SystemEventOutbox).limit(1)
        )
        row = result.scalars().one()
        assert row.published_at is None
        assert row.status is EventPublicationStatus.PENDING


class TestGetPendingDeterministicTiebreak:
    """Scenario 6 — get_pending ordering is stable across calls.

    The exact tiebreak key is implementation-defined; the contract
    is that repeated calls return rows in the same order.
    """

    @pytest.mark.asyncio
    async def test_identical_created_at_returns_stable_order(
        self, db_session: AsyncSession
    ) -> None:
        athlete = await make_athlete(db_session)

        same_ts = datetime(2026, 7, 1, 12, 0, 0, tzinfo=timezone.utc)
        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            created_at=same_ts,
        )
        await _make_outbox_row(
            db_session,
            athlete_id=athlete.id,
            created_at=same_ts,
        )
        await db_session.commit()

        repo = SystemEventOutboxRepository(db_session)
        first = await repo.get_pending(limit=10)
        second = await repo.get_pending(limit=10)

        assert len(first) == 2
        assert len(second) == 2
        # Stable order across calls.
        assert [r.event_id for r in first] == [r.event_id for r in second]
