"""Activity — lean physiological observation index.

Implements the Phase-1.2a contract from
docs/architecture/01-entities/activity.md.

The table is a lean index: identity, source, timing, signal-availability
flags, load scores, and reprocessing anchors only. No workout-summary or
dashboard fields (no ``avg_hr``, no ``avg_pace``, no ``avg_power``, no
``avg_cadence``, no lap data) ever appear here — those belong in the
FIT file or in execution-analysis records.

``planned_session_id`` is a nullable UUID without a foreign key. The
``planned_sessions`` table is created in Phase-1.2b; the FK is added by
that plan's migration. Referencing it here would couple this plan to
the next sub-phase and risk a forward-only migration path that can
break the head.
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
from app.models.enums import ActivitySource


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
    # Nullable UUID only — the FK to ``planned_sessions`` is added by
    # Phase-1.2b's migration when that table exists. Do NOT add the FK
    # here or this plan's migration will fail on a fresh database.
    planned_session_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
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
    )