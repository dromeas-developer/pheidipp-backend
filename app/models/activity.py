"""Activity — lean physiological observation index.

Implements the Phase-1.2a + Phase-1.2b contract from
docs/architecture/01-entities/activity.md.

The table is a lean index: identity, source, timing, signal-availability
flags, load scores, and reprocessing anchors only. No workout-summary or
dashboard fields (no ``avg_hr``, no ``avg_pace``, no ``avg_power``, no
``avg_cadence``, no lap data) ever appear here — those belong in the
FIT file or in execution-analysis records.

``planned_session_id`` is a nullable UUID with a foreign key to
``planned_sessions.id``. Phase-1.2a initially created the column WITHOUT
the FK (so a fresh-DB migration could stand alone on the head it
inherited); Phase-1.2b emits an explicit
``op.create_foreign_key('fk_activities_planned_session',
'activities', 'planned_sessions', ['planned_session_id'], ['id'])``
operation that wires the FK while preserving the column's nullable
semantics and zero-downtime additive intent.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import ActivitySource, SportType


class Activity(Base):
    """Lean running observation index row.

    One row per ingested or manually entered session. Never holds workout
    summaries; the FIT file is the source of truth.

    Deduplication:
        The partial unique index on
        ``(athlete_id, external_id, source) WHERE external_id IS NOT NULL``
        prevents the same external source session from being inserted
        twice. Source ``manual_entry`` uses ``external_id IS NULL`` and
        therefore falls outside the index predicate.
    """

    __tablename__ = "activities"

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
    # Nullable UUID referencing ``planned_sessions.id``. Phase-1.2a
    # created the column without the FK; Phase-1.2b's migration wires
    # the FK via ``op.create_foreign_key`` rather than re-creating the
    # column. Keeping ``nullable=True`` is essential — unplanned
    # activities (Tier 6 manual entries) must persist without a session.
    planned_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("planned_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ------------------------------------------------------------------
    # Source and deduplication.
    #
    # ``external_id`` is the source-platform identifier; for
    # ``manual_entry`` it is always NULL so the partial unique index
    # does not apply.
    # ------------------------------------------------------------------
    source: Mapped[ActivitySource] = mapped_column(
        SAEnum(
            ActivitySource,
            name="activity_source",
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False)

    # ------------------------------------------------------------------
    # Timing / duration.
    # ------------------------------------------------------------------
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)

    # ------------------------------------------------------------------
    # Sport type — detection result from FIT file ingest.
    # Used for calibration eligibility gating (Principle #8: non-running
    # activities excluded from twin calibration).
    # ------------------------------------------------------------------
    sport_type: Mapped[SportType] = mapped_column(
        SAEnum(
            SportType,
            name="sport_type",
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        server_default="unknown",
    )
    sport_type_detection_version: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )

    # ------------------------------------------------------------------
    # Load scores (nullable; populated by LoadComputationService).
    # ------------------------------------------------------------------
    aerobic_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    neuromuscular_load: Mapped[float | None] = mapped_column(Float, nullable=True)
    structural_load: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ------------------------------------------------------------------
    # Signal availability flags. Run derivation separately so the FIT
    # ingest can record what signals were actually captured rather
    # than what the hardware tier would imply.
    # ------------------------------------------------------------------
    has_hr: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    has_rr_intervals: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    has_power: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    has_gps: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    # ------------------------------------------------------------------
    # Calibration and quality.
    # ------------------------------------------------------------------
    calibration_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    quality_flags: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )

    # ------------------------------------------------------------------
    # Reprocessing anchor + versioning.
    # ------------------------------------------------------------------
    fit_file_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ingestion_pipeline_version: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    cleaning_pipeline_version: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Partial unique index — enforces ``(athlete_id, external_id,
        # source)`` uniqueness for non-null ``external_id`` only,
        # mirroring the activities dedup contract.
        Index(
            "uq_activities_athlete_external_source",
            "athlete_id",
            "external_id",
            "source",
            unique=True,
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_activities_athlete_date", "athlete_id", "activity_date"),
        Index("ix_activities_athlete_start_time", "athlete_id", "start_time"),
        # Filtered index for calibration-eligible activities — used for
        # recent structural load queries.
        Index(
            "ix_activities_athlete_calibration_eligible",
            "athlete_id",
            "activity_date",
            postgresql_where=text("calibration_eligible = true"),
        ),
        # FK index — supports reverse lookup from planned_session_id
        # (e.g. ``session_completed`` consumer resolving the planned
        # session) and follows the "always index FK columns"
        # convention.
        Index("ix_activities_planned_session", "planned_session_id"),
    )