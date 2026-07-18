"""PhysiologyMeasurementRepository — read and write operations for ``physiology_measurements``.

Implements the Phase-2.3-P1 contract from
docs/architecture/01-entities/athlete-physiology.md.

The table is append-only: this repository exposes only ``insert`` and
read methods, no UPDATE or DELETE. Corrections are made by inserting a
new observation with a higher ``confidence_weight`` or a more
authoritative ``source``; the service layer is responsible for
choosing which row to treat as current.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import MeasurementSource, PhysiologyParameter
from app.models.physiology_measurement import PhysiologyMeasurement


class PhysiologyMeasurementRepository:
    """Read and write operations for the ``physiology_measurements`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Writes.
    # ------------------------------------------------------------------

    async def insert(
        self, measurement: PhysiologyMeasurement
    ) -> PhysiologyMeasurement:
        """Add a PhysiologyMeasurement to the session without committing.

        Caller is responsible for committing the surrounding
        transaction. The threshold detection service calls this after
        computing the observation so the row is persisted atomically
        with any downstream posterior update.
        """
        self.session.add(measurement)
        await self.session.flush()
        await self.session.refresh(measurement)
        return measurement

    # ------------------------------------------------------------------
    # Reads.
    # ------------------------------------------------------------------

    async def get_by_athlete(
        self, athlete_id: uuid.UUID, limit: int
    ) -> list[PhysiologyMeasurement]:
        """Return the most recent measurements for an athlete, newest first.

        Backed by the ``ix_physiology_measurements_athlete_date``
        index. Used by the threshold detection service to assemble the
        full observation history for an athlete.
        """
        result = await self.session.execute(
            select(PhysiologyMeasurement)
            .where(PhysiologyMeasurement.athlete_id == athlete_id)
            .order_by(PhysiologyMeasurement.measurement_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_athlete_and_parameter(
        self,
        athlete_id: uuid.UUID,
        parameter: PhysiologyParameter,
        limit: int,
    ) -> list[PhysiologyMeasurement]:
        """Return the most recent measurements for one parameter, newest first.

        Backed by the
        ``ix_physiology_measurements_athlete_parameter_source`` index.
        Used by the posterior update service to read the history of a
        single parameter when computing the next state.
        """
        result = await self.session.execute(
            select(PhysiologyMeasurement)
            .where(
                PhysiologyMeasurement.athlete_id == athlete_id,
                PhysiologyMeasurement.parameter == parameter,
            )
            .order_by(PhysiologyMeasurement.measurement_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_for_parameter(
        self,
        athlete_id: uuid.UUID,
        parameter: PhysiologyParameter,
        source: MeasurementSource,
        from_date: date,
        limit: int,
    ) -> list[PhysiologyMeasurement]:
        """Return recent measurements for one (parameter, source) pair.

        Filters to observations on or after ``from_date`` and orders
        newest first. Used by:

        * Dedup detection — find prior observations of the same
          (parameter, source) tuple before inserting a new one.
        * Natural training analysis queries — read the recent
          training-derived observations for a parameter.

        Backed by the
        ``ix_physiology_measurements_athlete_parameter_source`` index.
        """
        result = await self.session.execute(
            select(PhysiologyMeasurement)
            .where(
                PhysiologyMeasurement.athlete_id == athlete_id,
                PhysiologyMeasurement.parameter == parameter,
                PhysiologyMeasurement.source == source,
                PhysiologyMeasurement.measurement_date >= from_date,
            )
            .order_by(PhysiologyMeasurement.measurement_date.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
