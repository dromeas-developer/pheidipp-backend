"""ActivityRepository — read and write operations for the ``activities`` table.

Implements the read surface required by the Phase-1.6 ingestion pipeline
and the post-workout analysis endpoint. ``Activity`` rows are written
by :class:`app.services.activity_ingestion_service.ActivityIngestionService`
inside the caller's transaction; this repository exposes only
``add`` (for new ingestion) and lookup methods so the append-only
invariant is preserved at the application layer.

Invariants codified here:

* ``Activity.fit_file_key`` is always set for
  ``source != 'manual_entry'``. The repository does not enforce this
  (the ingestion pipeline owns the invariant) but it does surface
  the column on every read so callers can check.

* Deduplication is enforced at the DB layer via the partial unique
  index ``uq_activities_athlete_external_source`` on
  ``(athlete_id, external_id, source) WHERE external_id IS NOT NULL``.
  Manual entries (no ``external_id``) are exempt.

* ``Activity`` rows for a superseded ``TrainingPlan`` retain the old
  ``planned_session_id`` — staleness risk is documented at the model
  level. Queries for "current plan activities" MUST join through
  ``PlannedSession → WeeklyPlan.training_plan_id``.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.enums import SportType


class ActivityRepository:
    """Read and write operations for the ``activities`` table."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Writes — append-only at the row level; mutation of load scores
    # is permitted but the ingestion pipeline performs a single
    # ``insert`` + ``update`` cycle per activity rather than mutating
    # columns piecemeal.
    # ------------------------------------------------------------------

    async def add(self, activity: Activity) -> Activity:
        """Add an Activity to the session without committing.

        Caller is responsible for committing the surrounding
        transaction. The ingestion pipeline calls this BEFORE
        ``load_scores`` are populated so the partial unique index
        catches duplicate uploads before any expensive work runs.
        """
        self.session.add(activity)
        await self.session.flush()
        await self.session.refresh(activity)
        return activity

    async def update_load_scores(
        self,
        *,
        activity_id: uuid.UUID,
        aerobic_load: Optional[float],
        neuromuscular_load: Optional[float],
        structural_load: Optional[float],
    ) -> Activity:
        """Update the three load-score columns in place.

        The mutation is permitted by the schema contract ("load
        scores may be written after Activity creation") but the row
        stays effectively immutable thereafter — only load scores,
        calibration eligibility, and version fields are mutated,
        per the architecture contract.
        """
        activity = await self.get_by_id(activity_id)
        if activity is None:
            raise LookupError(f"activity {activity_id} not found")
        activity.aerobic_load = aerobic_load
        activity.neuromuscular_load = neuromuscular_load
        activity.structural_load = structural_load
        await self.session.flush()
        await self.session.refresh(activity)
        return activity

    async def update_calibration_eligibility(
        self,
        *,
        activity_id: uuid.UUID,
        calibration_eligible: bool,
    ) -> Activity:
        """Set the ``calibration_eligible`` flag.

        Per the architecture invariant, this is the only method that
        is permitted to set the flag — manual overrides via direct
        attribute assignment would bypass
        :class:`CalibrationEligibilityService`.
        """
        activity = await self.get_by_id(activity_id)
        if activity is None:
            raise LookupError(f"activity {activity_id} not found")
        activity.calibration_eligible = calibration_eligible
        await self.session.flush()
        await self.session.refresh(activity)
        return activity

    async def update_cleaning_version(
        self,
        *,
        activity_id: uuid.UUID,
        version: str,
    ) -> Activity:
        """Set the ``cleaning_pipeline_version`` on the activity.

        The only permitted transition is ``null → non-null``: cleaning
        the stream once is final for the version that did the work.
        Re-cleaning with a new version is a future-phase concern
        (flagged in ADR-009 tradeoffs) and is not exposed here.
        """
        activity = await self.get_by_id(activity_id)
        if activity is None:
            raise LookupError(f"activity {activity_id} not found")
        activity.cleaning_pipeline_version = version
        await self.session.flush()
        await self.session.refresh(activity)
        return activity

    # ------------------------------------------------------------------
    # Reads.
    # ------------------------------------------------------------------

    async def get_by_id(self, activity_id: uuid.UUID) -> Optional[Activity]:
        """Return the activity by id, or ``None``."""
        result = await self.session.execute(
            select(Activity).where(Activity.id == activity_id)
        )
        return result.scalar_one_or_none()

    async def list_for_athlete(
        self,
        athlete_id: uuid.UUID,
        *,
        limit: int = 20,
        offset: int = 0,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> List[Activity]:
        """List activities for the athlete, newest first.

        Optional ``from_date`` / ``to_date`` filter on the
        ``activity_date`` column. The ``ix_activities_athlete_date``
        composite index supports the unbounded lookup; date
        filtering adds a single extra predicate that PostgreSQL
        applies during the index scan.
        """
        stmt = (
            select(Activity)
            .where(Activity.athlete_id == athlete_id)
            .order_by(Activity.start_time.desc())
        )
        if from_date is not None:
            stmt = stmt.where(Activity.activity_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Activity.activity_date <= to_date)
        stmt = stmt.limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_athlete(
        self,
        athlete_id: uuid.UUID,
        *,
        from_date: Optional[date] = None,
        to_date: Optional[date] = None,
    ) -> int:
        """Return the total count of activities for the athlete."""
        stmt = select(func.count()).where(Activity.athlete_id == athlete_id)
        if from_date is not None:
            stmt = stmt.where(Activity.activity_date >= from_date)
        if to_date is not None:
            stmt = stmt.where(Activity.activity_date <= to_date)
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def find_by_external_id(
        self,
        *,
        athlete_id: uuid.UUID,
        external_id: str,
        source: str,
    ) -> Optional[Activity]:
        """Return the activity matching ``(athlete_id, external_id, source)``.

        Used by the ingestion pipeline's deduplication gate. The
        partial unique index
        ``uq_activities_athlete_external_source`` makes this lookup
        O(1) and guarantees at most one row matches.
        """
        result = await self.session.execute(
            select(Activity).where(
                Activity.athlete_id == athlete_id,
                Activity.external_id == external_id,
                Activity.source == source,
            )
        )
        return result.scalar_one_or_none()

    async def get_recent_activities_for_athlete(
        self,
        athlete_id: uuid.UUID,
        sport_type: SportType,
        limit: int = 20,
    ) -> List[Activity]:
        """Return recent calibration-eligible activities for one sport.

        Filters on ``sport_type`` and ``calibration_eligible = true``,
        ordered newest first. Used by the natural training analysis
        algorithm (LT1 passive inference method 3) to query the
        recent history of easy / recovery runs.

        The natural training analysis then filters further by the
        session's ``PlannedSession.session_type`` (easy_run /
        recovery_run) once the cleaned stream is downloaded and the
        mean HR is computed. This method returns the candidate
        activities only — the session layer applies the
        session_type and HR-pattern filters.

        Backed by the
        ``ix_activities_athlete_calibration_eligible`` index, which
        covers ``(athlete_id, activity_date) WHERE calibration_eligible
        = true``. The ``sport_type`` predicate is applied as a
        post-index filter.
        """
        stmt = (
            select(Activity)
            .where(
                Activity.athlete_id == athlete_id,
                Activity.sport_type == sport_type,
                Activity.calibration_eligible.is_(True),
            )
            .order_by(Activity.start_time.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_structural_load(
        self,
        athlete_id: uuid.UUID,
        since_date: date,
    ) -> float:
        """Sum ``structural_load`` for calibration-eligible activities
        in the time window starting at ``since_date``.

        Filters on ``calibration_eligible = true`` and
        ``structural_load IS NOT NULL`` per the architecture doc.
        Used by the structural load density-penalty calculation.
        Returns 0.0 when no qualifying activities exist.
        """
        stmt = (
            select(func.coalesce(func.sum(Activity.structural_load), 0.0))
            .where(
                Activity.athlete_id == athlete_id,
                Activity.calibration_eligible.is_(True),
                Activity.structural_load.isnot(None),
                Activity.activity_date >= since_date,
            )
        )
        result = await self.session.execute(stmt)
        total = result.scalar_one()
        return float(total) if total is not None else 0.0