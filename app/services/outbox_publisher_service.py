from __future__ import annotations

from app.db.session import AsyncSessionLocal
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)


class OutboxPublisherService:
    """Publish-side transaction owner for ``system_event_outbox`` status transitions.

    Per ADR-013, this service — not the worker task — owns the
    publish-side transaction. The worker calls
    :meth:`publish_pending` and the service opens its own
    ``AsyncSession``, transitions ``pending`` rows to ``published``,
    and commits.
    """

    async def publish_pending(self, limit: int) -> int:
        async with AsyncSessionLocal() as session:
            repo = SystemEventOutboxRepository(session)
            pending = await repo.get_pending(limit)
            for row in pending:
                await repo.mark_published(row.event_id)
            await session.commit()
            return len(pending)
