"""TwinState — append-only snapshot of the twin's current understanding.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/twin-state.md.

Schema-only foundation: no recalibration service, dedupe logic, or
event publication is added by this plan. The model persists the row
shape including the inline threshold / fitness / fatigue / readiness
snapshot values that downstream coaching consumers depend on.

Invariants codified at the DB layer:

* Append-only at every layer — no ``update()``/``delete()`` methods on
  the model and the repository contract restricts to ``insert``,
  ``get_latest``, ``get_by_activity``, and ``get_history``.
* ``training_goal_id``, ``model_version``, and ``activity_id`` are
  frozen at creation time via being non-nullable (or null at insert
  only for ``activity_id``).
* One ``TwinState`` per ``(athlete_id, activity_id)`` where
  ``activity_id IS NOT NULL`` — enforced via partial unique index so
  non-activity triggers (questionnaire / physiology_input /
  wellness_update) are not blocked.
* ``(athlete_id, created_at DESC)`` is the primary read pattern — the
  ``idx_twin_states_latest`` index supports the most frequent query
  in the system (``get_latest`` for the home view).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import (
    DataTier,
    RecoveryModifierLevel,
    TwinConfidenceLevel,
    TwinTrigger,
    WellnessTrend,
)


class TwinState(Base):
    """One immutable snapshot of the twin's beliefs at a point in time.

    Inline snapshot — fitness/fatigue/thresholds/readiness values are
    stored on the row rather than referenced via FK so historical
    records never drift as the operational layer mutates
    ``AthleteFitness`` / ``AthletePhysiology``.

    The application layer NEVER updates or deletes a ``TwinState``;
    the repository owned by Phase 1.3 will expose only ``insert``,
    ``get_latest``, ``get_by_activity``, and ``get_history``.
    """

    __tablename__ = "twin_states"

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
    training_goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Context fields owned by TwinState itself.
    # ``data_tier`` is an ``(int, Enum)`` — stored as the integer
    # value, not as a named PostgreSQL enum, so the column is
    # ``Integer``. Application code reads/writes the enum members;
    # SQLAlchemy persists the integer values via the
    # ``values_callable``.
    # ------------------------------------------------------------------
    data_tier: Mapped[DataTier] = mapped_column(
        Integer,
        nullable=False,
    )
    confidence_level: Mapped[TwinConfidenceLevel] = mapped_column(
        SAEnum(
            TwinConfidenceLevel,
            name="twin_confidence_level",
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    trigger: Mapped[TwinTrigger] = mapped_column(
        SAEnum(
            TwinTrigger,
            name="twin_trigger",
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    model_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Inline snapshot — fitness / fatigue / form.
    # ------------------------------------------------------------------
    fitness: Mapped[float] = mapped_column(Float, nullable=False)
    fatigue: Mapped[float] = mapped_column(Float, nullable=False)
    # ``form`` is stored for query convenience — application code
    # MUST always keep ``form == fitness - fatigue``. Atomicity of
    # those three writes is owned by the Phase-1.3 service layer.
    form: Mapped[float] = mapped_column(Float, nullable=False)

    # ------------------------------------------------------------------
    # Threshold snapshots — inline floats, nullable when no signal.
    # GAP values are stored as ``seconds_per_km`` floats; raw pace is
    # never persisted.
    # ------------------------------------------------------------------
    lt1_pace_sec_per_km: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    lt1_power_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    lt1_hr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    lt2_pace_sec_per_km: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    lt2_power_watts: Mapped[float | None] = mapped_column(Float, nullable=True)
    lt2_hr_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    cp_watts: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ------------------------------------------------------------------
    # Readiness context.
    # ------------------------------------------------------------------
    readiness_level: Mapped[RecoveryModifierLevel] = mapped_column(
        SAEnum(
            RecoveryModifierLevel,
            name="recovery_modifier_level",
            native_enum=False,
            length=8,
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    wellness_trend: Mapped[WellnessTrend | None] = mapped_column(
        SAEnum(
            WellnessTrend,
            name="wellness_trend",
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Per-metric confidence breakdown — JSONB of the
    # ``TwinState.metric_confidence`` shape (``lt1_hr``,
    # ``lt1_power`` / ``lt1_pace``, ``lt2_hr``, ``lt2_power`` /
    # ``lt2_pace``, ``cp``). Null fields use JSON ``null``.
    # ------------------------------------------------------------------
    metric_confidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        # Arch invariant — one TwinState per (athlete_id, activity_id)
        # for activity-linked triggers. The partial uniques index
        # keeps non-activity triggers (questionnaire, physiology_input,
        # wellness_update) outside the deduplication scope.
        Index(
            "uq_twin_states_athlete_activity",
            "athlete_id",
            "activity_id",
            unique=True,
            postgresql_where=text("activity_id IS NOT NULL"),
        ),
        # Primary read path — ``get_latest`` lookup for the home view.
        Index("idx_twin_states_latest", "athlete_id", "created_at"),
        # Reverse-lookup from training goal / activity — supports the
        # get_by_activity repository contract.
        Index(
            "ix_twin_states_training_goal",
            "training_goal_id",
        ),
        Index(
            "ix_twin_states_activity",
            "activity_id",
        ),
    )
