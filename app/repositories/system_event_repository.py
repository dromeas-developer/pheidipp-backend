"""SystemEventRepository — append-only event log writes.

Paired with :class:`SystemEventOutboxRepository`, this enforces ADR-004
(Event Persistence Atomicity): each event row's persistence is followed
in the SAME database transaction by a matching outbox row with
status='pending'. The producing service is responsible for invoking
both adds within a single transaction and committing once.

Direct callers that need to persist events atomically with domain state
should use :func:`app.services.event_publisher.publish_event` instead —
it composes both repositories and ensures the invariant by construction.
"""

from __future__ import annotations

from typing import Any
import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.system_event import SystemEvent


class SystemEventRepository:
    """Persistence for the ``system_events`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        event_id: uuid.UUID,
        event_type: str,
        version: str,
        athlete_id: uuid.UUID,
        payload: dict[str, Any],
        produced_at: datetime,
    ) -> SystemEvent:
        """Insert a SystemEvent within the caller's transaction.

        The companion outbox row must be inserted in the same transaction;
        callers should prefer :func:`event_publisher.publish_event` so both
        rows land atomically. This method exists for direct unit-test
        access where the outbox is exercised separately.
        """
        event = SystemEvent(
            event_id=event_id,
            event_type=event_type,
            version=version,
            athlete_id=athlete_id,
            payload=payload,
            produced_at=produced_at,
        )
        self.session.add(event)
        await self.session.flush()
        return event
