"""TwinStateRepository — append-only snapshot reads and writes.

The repository contract enforces the architecture's append-only
invariant on ``TwinState``: no ``update()`` or ``delete()`` methods
are exposed. The bootstrap writer (``OnboardingService``) calls
``insert``; subsequent appends belong to the recalibration pipeline
(Phase 1.6+). Reads are restricted to ``get_latest``, ``get_by_id``,
``get_by_activity``, and ``get_history``.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.twin_state import TwinState


class TwinStateRepository:
    """Append-only read/write operations for the ``twin_states`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_latest(
        self, athlete_id: uuid.UUID
    ) -> Optional[TwinState]:
        """Return the most recent ``TwinState`` for *athlete_id*, or ``None``.

        Uses the ``idx_twin_states_latest`` composite index on
        ``(athlete_id, created_at)`` to satisfy the home-view read path
        without a sort.
        """
        result = await self.session.execute(
            select(TwinState)
            .where(TwinState.athlete_id == athlete_id)
            .order_by(TwinState.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_id(
        self, twin_state_id: uuid.UUID
    ) -> Optional[TwinState]:
        result = await self.session.execute(
            select(TwinState).where(TwinState.id == twin_state_id)
        )
        return result.scalar_one_or_none()

    async def get_by_activity(
        self, activity_id: uuid.UUID
    ) -> Optional[TwinState]:
        """Return the TwinState recorded for *activity_id*, if any.

        Activity-linked triggers guarantee at most one TwinState per
        activity (partial unique index on
        ``(athlete_id, activity_id) WHERE activity_id IS NOT NULL``).
        """
        result = await self.session.execute(
            select(TwinState).where(TwinState.activity_id == activity_id)
        )
        return result.scalar_one_or_none()

    async def get_history(
        self, athlete_id: uuid.UUID, limit: int = 20
    ) -> List[TwinState]:
        """Return the most recent TwinStates for *athlete_id*, newest first.

        ``limit`` is bounded by the caller (the API layer clamps to a
        maximum of 100); this method does not re-clamp.
        """
        result = await self.session.execute(
            select(TwinState)
            .where(TwinState.athlete_id == athlete_id)
            .order_by(TwinState.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def insert(self, twin_state: TwinState) -> TwinState:
        """Append a new TwinState to the session without committing.

        This is the ONLY write method exposed by the repository — no
        ``update`` / ``delete`` exists, by design.
        """
        self.session.add(twin_state)
        await self.session.flush()
        await self.session.refresh(twin_state)
        return twin_state
