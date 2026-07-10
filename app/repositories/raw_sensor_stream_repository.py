"""RawSensorStreamRepository — read and write operations for ``raw_sensor_streams``.

Implements the Phase-2.2 contract from
docs/architecture/01-entities/raw-sensor-stream.md.

The table is append-only: this repository exposes only ``insert`` and
read methods, no UPDATE or DELETE. The one-row-per-Activity invariant
is enforced at the DB layer by the UNIQUE constraint
``uq_raw_sensor_streams_activity`` and surfaced at the application
layer by ``exists_for_activity`` (idempotency check used by the
cleaning task's retry path) and ``get_by_activity_id`` (the
Phase-2.3 segmentation lookup).
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.raw_sensor_stream import RawSensorStream


class RawSensorStreamRepository:
    """Read and write operations for the ``raw_sensor_streams`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Writes.
    # ------------------------------------------------------------------

    async def insert(self, stream: RawSensorStream) -> RawSensorStream:
        """Add a RawSensorStream to the session without committing.

        Caller is responsible for committing the surrounding
        transaction. The cleaning task calls this AFTER the cleaned
        stream is uploaded to object storage so the row's
        ``fit_file_key`` points to a real key.
        """
        self.session.add(stream)
        await self.session.flush()
        await self.session.refresh(stream)
        return stream

    # ------------------------------------------------------------------
    # Reads.
    # ------------------------------------------------------------------

    async def get_by_activity_id(
        self, activity_id: uuid.UUID
    ) -> Optional[RawSensorStream]:
        """Return the RawSensorStream for the Activity, or ``None``.

        The one-to-one lookup used by Phase-2.3 segmentation to resolve
        the cleaned stream key for a given activity. Backed by the
        ``ix_raw_sensor_streams_activity`` index.
        """
        result = await self.session.execute(
            select(RawSensorStream).where(
                RawSensorStream.activity_id == activity_id
            )
        )
        return result.scalar_one_or_none()

    async def exists_for_activity(self, activity_id: uuid.UUID) -> bool:
        """Return ``True`` if a RawSensorStream already exists for the activity.

        Used by the cleaning task's retry path: if a row already exists
        the task treats the cleaning as already-done and returns
        success without re-running the pipeline. Backed by the same
        ``ix_raw_sensor_streams_activity`` index.
        """
        result = await self.session.execute(
            select(RawSensorStream.id).where(
                RawSensorStream.activity_id == activity_id
            )
        )
        return result.scalar_one_or_none() is not None
