"""SystemEventOutboxRepository — mutable publication state writes.

Per ADR-004, the outbox table is the only mutable event-related state
in the platform. Calls here MUST share the same ``AsyncSession`` as
the producing domain transaction so updates are atomic with the
SystemEvent row.

The publication pipeline (publisher worker) updates ``status`` to
``'published'`` or ``'failed'`` after the producing transaction has
already committed. Producers never modify state after commit.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_event import EventPublicationStatus, SystemEventOutbox


class SystemEventOutboxRepository:
    """Persistence for the ``system_event_outbox`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        event_id: uuid.UUID,
        status: EventPublicationStatus = EventPublicationStatus.PENDING,
    ) -> SystemEventOutbox:
        """Insert an outbox row within the caller's transaction.

        Producers should pass ``status='pending'`` (the default) so the
        post-commit publisher picks it up. The publisher flips the
        status to 'published'/'failed'/'dlq' based on delivery outcome.
        """
        outbox = SystemEventOutbox(event_id=event_id, status=status)
        self.session.add(outbox)
        await self.session.flush()
        return outbox

    async def get_pending(self, limit: int) -> list[SystemEventOutbox]:
        """Return up to *limit* outbox rows in the ``pending`` state.

        Ordered by ``created_at`` so publication proceeds in the same
        order the producing transactions committed. Backed by the
        ``ix_system_event_outbox_status_created`` index so the scan
        stays cheap as the table grows.

        Read-only: no flush, no commit. The caller (the outbox
        publisher worker) commits the subsequent ``mark_published``
        updates in its own transaction, separate from the producing
        domain transaction — preserving the transactional outbox
        atomicity invariant declared in
        ``docs/architecture/04-platform/system-event.md``.
        """
        result = await self.session.execute(
            select(SystemEventOutbox)
            .where(SystemEventOutbox.status == EventPublicationStatus.PENDING)
            .order_by(SystemEventOutbox.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_published(
        self,
        event_id: uuid.UUID,
        *,
        published_at: Optional[datetime] = None,
    ) -> None:
        """Mark the outbox row as published; only the publisher calls this."""
        row = await self.session.get(SystemEventOutbox, event_id)
        if row is None:
            return
        row.status = EventPublicationStatus.PUBLISHED
        row.published_at = published_at or datetime.now(timezone.utc)
        row.last_error = None
        await self.session.flush()
