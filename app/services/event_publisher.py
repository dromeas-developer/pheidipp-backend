"""Event publisher — atomically write SystemEvent + outbox row.

Implements ADR-004 rule "Event Persistence Atomicity". The helper
inserts the event row and its companion outbox row in the caller's
transaction; the producer commits the whole transaction — domain
state plus event plus outbox — exactly once.

External publication (message bus delivery) is owned by the platform
publisher worker and runs strictly after the producing transaction
commits. This module never publishes externally.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from app.models.system_event import EventPublicationStatus, SystemEvent
from app.repositories.system_event_outbox_repository import (
    SystemEventOutboxRepository,
)
from app.repositories.system_event_repository import SystemEventRepository


@dataclass(frozen=True)
class OutboxEvent:
    """Value object describing an event ready for transactional outbox."""

    event_id: uuid.UUID
    event_type: str
    version: str
    athlete_id: UUID
    payload: dict


class EventPublisher:
    """Write SystemEvent + SystemEventOutbox atomically within one session."""

    def __init__(
        self,
        events: SystemEventRepository,
        outbox: SystemEventOutboxRepository,
    ) -> None:
        self._events = events
        self._outbox = outbox

    async def publish(
        self,
        *,
        event_type: str,
        athlete_id: UUID,
        payload: dict,
        version: str = "v1",
    ) -> SystemEvent:
        """Insert the event row and an outbox row in the same transaction.

        Returns the inserted :class:`SystemEvent` so callers can log the
        resulting ``event_id`` for audit purposes. Caller is responsible
        for committing the surrounding transaction exactly once.
        """
        event_id = uuid.uuid4()
        produced_at = datetime.now(timezone.utc)
        event = await self._events.add(
            event_id=event_id,
            event_type=event_type,
            version=version,
            athlete_id=athlete_id,
            payload=payload,
            produced_at=produced_at,
        )
        await self._outbox.add(
            event_id=event_id,
            status=EventPublicationStatus.PENDING,
        )
        return event
