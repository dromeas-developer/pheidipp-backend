"""CoachingMessageRepository — append-only message storage.

The repository contract enforces the architecture's append-only
invariant on ``CoachingMessage``: no ``update()`` or ``delete()``
methods are exposed. Insertions are limited to ``insert()`` — the
generation agent (``FirstMessageAgent``) is the sole writer.

Indexed reads:

* ``get_by_athlete_id`` — message feed (newest first).
* ``get_by_athlete_and_type`` — frequency-guard lookup
  (``first_message`` is one-per-athlete-per-active-goal).
* ``get_existing_first_message`` — convenience for the
  second-call-to-first-message agent which short-circuits to a 409.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coaching_message import CoachingMessage
from app.models.enums import MessageType


class CoachingMessageRepository:
    """Append-only read/write operations for the ``coaching_messages`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def insert(self, message: CoachingMessage) -> CoachingMessage:
        """Append a new CoachingMessage to the session without committing.

        This is the ONLY write method exposed by the repository. No
        ``update()`` / ``delete()`` exists, by design — messages are
        immutable once persisted.
        """
        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)
        return message

    async def get_by_athlete_id(
        self,
        athlete_id: uuid.UUID,
        *,
        message_type: Optional[MessageType] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[CoachingMessage]:
        """Return messages for *athlete_id*, newest first.

        Optional ``message_type`` filters at the DB layer using the
        ``ix_coaching_messages_athlete_type_generated_at`` composite
        index. ``limit`` is bounded by the caller (the API layer
        clamps to a maximum of 100); this method does not re-clamp.
        ``offset`` skips that many rows from the newest-first ordering.
        """
        stmt = (
            select(CoachingMessage)
            .where(CoachingMessage.athlete_id == athlete_id)
            .order_by(CoachingMessage.generated_at.desc())
        )
        if message_type is not None:
            stmt = stmt.where(CoachingMessage.message_type == message_type)
        stmt = (
            stmt.limit(limit).offset(offset)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_athlete_and_type(
        self,
        athlete_id: uuid.UUID,
        message_type: MessageType,
    ) -> List[CoachingMessage]:
        """Return all messages of *message_type* for *athlete_id*, newest first.

        Used by the frequency-guard logic for ``wellness_alert`` /
        ``cycle_check_in`` / ``phase_transition`` etc. (those
        rate-limited types are service-layer enforced, not DB
        constrained). ``first_message`` callers should use
        :meth:`get_existing_first_message` instead.
        """
        result = await self.session.execute(
            select(CoachingMessage)
            .where(
                CoachingMessage.athlete_id == athlete_id,
                CoachingMessage.message_type == message_type,
            )
            .order_by(CoachingMessage.generated_at.desc())
        )
        return list(result.scalars().all())

    async def get_existing_first_message(
        self, athlete_id: uuid.UUID
    ) -> Optional[CoachingMessage]:
        """Return the existing ``first_message`` for *athlete_id*, if any.

        The DB enforces at most one ``first_message`` per athlete via
        the partial unique index
        ``uq_coaching_messages_athlete_first_message``, so this
        returns at most one row.
        """
        result = await self.session.execute(
            select(CoachingMessage).where(
                CoachingMessage.athlete_id == athlete_id,
                CoachingMessage.message_type == MessageType.FIRST_MESSAGE,
            )
        )
        return result.scalar_one_or_none()

    async def get_all_count(
        self,
        athlete_id: uuid.UUID,
        *,
        message_type: Optional[MessageType] = None,
    ) -> int:
        """Return the total count of messages for *athlete_id*.

        Optional ``message_type`` filters the count. Used by the list
        endpoint to compute pagination totals.
        """
        stmt = select(func.count()).where(
            CoachingMessage.athlete_id == athlete_id
        )
        if message_type is not None:
            stmt = stmt.where(CoachingMessage.message_type == message_type)
        result = await self.session.execute(stmt)
        return result.scalar_one()