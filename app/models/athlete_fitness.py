"""AthleteFitness — Banister model rolling fitness/fatigue scores.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/athlete-fitness.md.

Schema-only foundation: no ``FitnessUpdateService``,
``TimeConstantFittingService``, or wellness-modifier logic in this
plan. The model persists the row shape so later phases can plug in
the Banister update without altering column shape.

Invariants codified at the DB layer:

* One ``AthleteFitness`` row per ``Athlete`` — enforced via the
  ``uq_athlete_fitness_athlete`` ``UNIQUE`` index on ``(athlete_id)``.
* MUTABLE current-state entity — scores update in place on every
  calibration-eligible activity. Historical state is captured
  inline in append-only ``TwinState`` records.
* ``aggregate`` is always populated.
* ``form = fitness - fatigue`` MUST hold for every ``DimensionalScores``
  JSON shape (aggregate + each populated dimensional block). The
  invariant is enforced via PostgreSQL ``CHECK`` constraints on the
  JSONB ``form`` / ``fitness`` / ``fatigue`` keys.
* Negative ``form`` is valid (load phase) per the architecture
  invariant; no lower-bound CHECK is applied to ``form``.
* ``time_constants.source`` is constrained at the application layer
  (Phase 1.6 ``TimeConstantFittingService``) — schema accepts both
  ``population_default`` and ``individual_fitted``.
* ``time_constants.fit_quality_score`` per the schema is captured as
  a numeric column on the JSONB object rather than a separate table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# PostgreSQL-side boolean expression for the form = fitness - fatigue
# invariant. Re-used by every ``DimensionalScores`` JSONB column
# (aggregate + each populated dimension). ``NULL`` JSONB values skip
# the constraint so optional dimensional blocks are not blocked.
_FORM_INVARIANT = (
    "({col} IS NULL) OR "
    "(({col}->>'form')::float "
    "= ({col}->>'fitness')::float - ({col}->>'fatigue')::float)"
)


class AthleteFitness(Base):
    """One Banister rolling-state row per athlete.

    Stores the aggregate score pair (always populated), optional
    dimensional scores (aerobic / neuromuscular / structural,
    populated when data quality permits), the time-constants config,
    and the ``last_activity_id`` anchoring reference.

    Mutability:
        The service layer (Phase 1.6 ``FitnessUpdateService``) is the
        only writer; the table is fully mutable and ``form`` is
        enforced equal to ``fitness - fatigue`` at the DB layer.
    """

    __tablename__ = "athlete_fitness"

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
    # Aggregate score — always populated, ``form`` derived.
    # ------------------------------------------------------------------
    aggregate: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ------------------------------------------------------------------
    # Per-dimension scores — optional. When populated, each carries
    # its own ``form`` field equal to ``fitness - fatigue``. Populated
    # when ``FitnessUpdateService`` has data quality for the
    # dimension (per architecture doc).
    # ------------------------------------------------------------------
    aerobic: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    neuromuscular: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    structural: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ------------------------------------------------------------------
    # ``BanisterTimeConstants`` — JSONB carrying the dimension-by-
    # dimension tau values plus ``source`` and ``fitted_at``.
    # ------------------------------------------------------------------
    time_constants: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # ------------------------------------------------------------------
    # Anchoring reference — last activity that wrote this row.
    # ------------------------------------------------------------------
    last_activity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )

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
            "uq_athlete_fitness_athlete",
            "athlete_id",
            unique=True,
        ),
        # Reverse lookup from the last committed activity that drove
        # this fitness update (monitoring / debugging).
        Index("ix_athlete_fitness_last_activity", "last_activity_id"),
        # ``form = fitness - fatigue`` MUST hold for the aggregate row
        # and for each populated dimensional block. The aggregate
        # column is non-null, so the constraint is unconditional there.
        CheckConstraint(
            "(aggregate->>'form')::float = "
            "(aggregate->>'fitness')::float - (aggregate->>'fatigue')::float",
            name="ck_athlete_fitness_aggregate_form_invariant",
        ),
        CheckConstraint(
            _FORM_INVARIANT.format(col="aerobic"),
            name="ck_athlete_fitness_aerobic_form_invariant",
        ),
        CheckConstraint(
            _FORM_INVARIANT.format(col="neuromuscular"),
            name="ck_athlete_fitness_neuromuscular_form_invariant",
        ),
        CheckConstraint(
            _FORM_INVARIANT.format(col="structural"),
            name="ck_athlete_fitness_structural_form_invariant",
        ),
        # ``time_constants.source`` is the inline union documented in
        # the architecture doc — bound to one of the two values.
        CheckConstraint(
            "(time_constants->>'source') IN "
            "('population_default', 'individual_fitted')",
            name="ck_athlete_fitness_time_constants_source_valid",
        ),
    )
