"""RawSensorStream — append-only metadata record for cleaned sensor streams.

Implements the Phase-2.2 contract from
docs/architecture/01-entities/raw-sensor-stream.md.

One row per Activity. The cleaned stream itself lives in object storage
at the key recorded in ``fit_file_key``; this table is the lookup index
that downstream segmentation in Phase-2.3 reads from.

The table is append-only: there are no ``updated_at`` or ``cleaned_at``
mutation columns, and the repository exposes no UPDATE/DELETE methods.
The one-row-per-Activity invariant is enforced by a UNIQUE constraint
on ``activity_id``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RawSensorStream(Base):
    """Metadata record for a cleaned time-series stream.

    The cleaned stream is the segmentation input produced by Phase-2.2
    (signal cleaning). The raw FIT remains the reprocessing anchor —
    both keys are retained indefinitely per the architecture doc.
    """

    __tablename__ = "raw_sensor_streams"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="CASCADE"),
        nullable=False,
    )
    # The cleaned-stream object key, NOT the raw FIT key. Naming mirrors
    # ``Activity.fit_file_key`` intentionally per the architecture doc.
    fit_file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    # Default/stored 1.0 after resampling — the column is non-null
    # because every cleaned stream has been resampled to a fixed rate.
    sampling_rate_hz: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0, server_default="1.0"
    )
    available_channels: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    cleaning_pipeline_version: Mapped[str] = mapped_column(
        String(32), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # One-row-per-Activity — the architecture invariant that
        # segmentation in Phase-2.3 relies on for its one-to-one lookup.
        UniqueConstraint(
            "activity_id",
            name="uq_raw_sensor_streams_activity",
        ),
        # FK index — supports the one-to-one lookup
        # ``RawSensorStreamRepository.get_by_activity_id``.
        Index("ix_raw_sensor_streams_activity", "activity_id"),
    )
