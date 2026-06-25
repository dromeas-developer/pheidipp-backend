"""AthletePhysiology — current posterior estimates per physiological parameter.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/athlete-physiology.md.

Schema-only foundation: no Bayesian update service, threshold
detection pipeline, or ``PhysiologyMeasurement`` table is added by
this plan — those are deferred to later sub-phases. The model
persists the row shape with a one-to-one FK to ``Athlete`` so that
``cp`` / ``vo2max`` / ``max_hr`` / per-dimension LT1 / LT2 posterior
states can be read by downstream Phase-1.3 / 1.6 services.

Invariants codified at the DB layer:

* One ``AthletePhysiology`` row per ``Athlete`` — enforced via the
  ``uq_athlete_physiology_athlete`` ``UNIQUE`` index on
  ``(athlete_id)``.
* MUTABLE current-state entity — posterior estimates update in place
  on each threshold detection event. Historical state is captured
  inline in append-only ``TwinState`` records.
* ``cp`` and ``vo2max.*`` are stored as ``nullable`` JSONB; ``null``
  until a qualifying observation is made. They are NEVER bootstrapped
  from questionnaire estimates; the service layer enforces that
  invariant in later phases.
* ``max_hr`` is bootstrapped from ``220 - age`` at onboarding
  (service-layer concern in Phase 1.3).
* Nested ``PhysiologyParameterState`` shapes are normalised into
  per-dimension JSONB columns (``lt1``, ``lt2``, ``cp``, ``vo2max``,
  ``max_hr``) so the architecture shape is preserved without DDL
  churn on the nested field set.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AthletePhysiology(Base):
    """One-to-one current posterior state per athlete.

    Stores the per-parameter ``PhysiologyParameterState`` objects:
    ``lt1.hr / power / pace``, ``lt2.hr / power / pace``,
    ``cp``, ``vo2max.ml_kg_min / power``, ``max_hr``. Each is a
    nullable JSONB column that the application layer shapes per the
    architecture contract.

    Mutability:
        The service layer (Phase 1.6 ``PhysiologyUpdateService``) is
        the only writer; the table itself is fully mutable. Posterior
        decay and rescaling logic live outside the schema.
    """

    __tablename__ = "athlete_physiology"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ------------------------------------------------------------------
    # LT1 — three-dimension per-signal state objects.
    # JSONB shape: ``{hr: {...}, power: {...}, pace: {...}}`` where
    # each signal entry is either ``{value, uncertainty, prior_weight,
    # dominant_source, last_observation_date}`` or JSON ``null``.
    # ------------------------------------------------------------------
    lt1: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ------------------------------------------------------------------
    # LT2 — same shape as LT1.
    # ------------------------------------------------------------------
    lt2: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ------------------------------------------------------------------
    # Critical Power — full ``PhysiologyParameterState`` or null until
    # the first qualifying observation.
    # ------------------------------------------------------------------
    cp: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ------------------------------------------------------------------
    # VO2max — two sub-states (``ml_kg_min``, ``power``). Either or
    # both may be null.
    # ------------------------------------------------------------------
    vo2max: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ------------------------------------------------------------------
    # ``max_hr`` — bootstrapped from ``220 - age`` with prior_weight 0.5
    # at onboarding.
    # ------------------------------------------------------------------
    max_hr: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # One record per athlete.
        Index(
            "uq_athlete_physiology_athlete",
            "athlete_id",
            unique=True,
        ),
    )
