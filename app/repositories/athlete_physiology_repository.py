"""AthletePhysiologyRepository — posterior threshold state lookups and writes."""

from __future__ import annotations

import uuid
from typing import Mapping, Optional, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.athlete_physiology import AthletePhysiology


# Module-private sentinel used by :meth:`update_in_place` to
# distinguish "caller did not pass the argument" (no-op) from
# "caller passed ``None``" (clear the nullable column). The
# ``lt1`` / ``lt2`` columns are non-nullable, so they use a plain
# ``None`` default.
_UNSET: object = object()

#: Public alias for :data:`_UNSET` — exported for cross-module
#: callers (e.g. :class:`PhysiologyUpdateService`) that need to
#: pass the "do not touch" sentinel to :meth:`update_in_place`.
UNSET_SENTINEL: object = _UNSET


class AthletePhysiologyRepository:
    """Read and write operations for the ``athlete_physiology`` table.

    One ``AthletePhysiology`` row per athlete — enforced by the
    ``uq_athlete_physiology_athlete`` ``UNIQUE`` index. The
    Phase-1.3 onboarding bootstrap is the first writer; the
    Phase-2.3 ``PhysiologyUpdateService`` performs all subsequent
    updates in place via :meth:`update_in_place`.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_athlete_id(
        self, athlete_id: uuid.UUID
    ) -> Optional[AthletePhysiology]:
        result = await self.session.execute(
            select(AthletePhysiology).where(
                AthletePhysiology.athlete_id == athlete_id
            )
        )
        return result.scalar_one_or_none()

    async def add(
        self, physiology: AthletePhysiology
    ) -> AthletePhysiology:
        """Add a physiology row to the session without committing."""
        self.session.add(physiology)
        await self.session.flush()
        await self.session.refresh(physiology)
        return physiology

    async def update_in_place(
        self,
        athlete_id: uuid.UUID,
        *,
        lt1: Optional[Mapping[str, object]] = None,
        lt2: Optional[Mapping[str, object]] = None,
        cp: object = _UNSET,
        max_hr: object = _UNSET,
    ) -> AthletePhysiology:
        """Mutate the existing ``AthletePhysiology`` row in place.

        The ``Phase-2.3 PhysiologyUpdateService`` owns the only call
        site for this method. The row must already exist (created by
        the Phase-1.3 onboarding bootstrap); this method does NOT
        insert a new row.

        ``lt1`` / ``lt2`` are the outer three-dimension JSONB
        containers (``{hr: {...}, power: {...}, pace: {...}}``) and
        are required-shape — both columns are non-nullable. Pass
        the post-mutation value; ``None`` is treated as "do not
        touch" and the caller is responsible for always passing
        the latest value.

        ``cp`` / ``max_hr`` are nullable JSONB columns carrying a
        single ``PhysiologyParameterState`` dict. Because the column
        itself may legitimately be ``None`` (e.g. ``cp`` stays null
        until the first qualifying observation), this method uses
        an explicit sentinel to distinguish "caller did not pass the
        argument" (no-op) from "caller passed ``None``" (clear the
        column back to null). Pass a dict to set a new value.

        The session is flushed so the ``updated_at`` ``onupdate=``
        hook fires, but the caller (worker task in Phase-2.3-P3)
        owns the commit boundary — no commit is performed here.

        Raises:
            RuntimeError: no row exists for ``athlete_id`` (the
                service-layer caller treats this as a data-integrity
                failure rather than a recoverable user error).
        """
        row = await self.get_by_athlete_id(athlete_id)
        if row is None:
            raise RuntimeError(
                f"no AthletePhysiology row for athlete {athlete_id}"
            )
        if lt1 is not None:
            row.lt1 = dict(lt1)
        if lt2 is not None:
            row.lt2 = dict(lt2)
        if cp is not _UNSET:
            row.cp = (
                dict(cast(Mapping[str, object], cp))
                if cp is not None
                else None
            )
        if max_hr is not _UNSET:
            row.max_hr = (
                dict(cast(Mapping[str, object], max_hr))
                if max_hr is not None
                else None
            )
        await self.session.flush()
        return row
