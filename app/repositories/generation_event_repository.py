"""GenerationEventRepository — append-only LLM audit log storage.

The repository contract enforces the architecture's append-only
invariant on ``GenerationEvent``: no ``update()`` or ``delete()``
methods are exposed. Every LLM call (success or failure) appends a
single row through :meth:`insert`.

Indexed reads:

* ``get_by_athlete_id`` — per-athlete audit feed (newest first).
"""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generation_event import GenerationEvent


class GenerationEventRepository:
    """Append-only read/write operations for the ``generation_events`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(self, event: GenerationEvent) -> GenerationEvent:
        """Append a new GenerationEvent to the session without committing.

        This is the ONLY write method exposed by the repository. No
        ``update()`` / ``delete()`` exists, by design — the audit log
        is append-only and immutable.
        """
        self.session.add(event)
        await self.session.flush()
        await self.session.refresh(event)
        return event

    async def get_by_athlete_id(
        self, athlete_id: uuid.UUID, limit: int = 50
    ) -> List[GenerationEvent]:
        """Return the most recent GenerationEvents for *athlete_id*, newest first.

        ``limit`` is bounded by the caller (the internal ops surface
        clamps to 100); this method does not re-clamp.
        """
        result = await self.session.execute(
            select(GenerationEvent)
            .where(GenerationEvent.athlete_id == athlete_id)
            .order_by(GenerationEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
