"""PhysiologyMeasurement — append-only record of a single physiological observation.

Implements the Phase-2.3-P1 contract from
docs/architecture/01-entities/athlete-physiology.md.

One row per observation of a single (athlete, parameter) pair. The
table is the historical record that ``ThresholdDetectionService``
appends to and that ``PhysiologyUpdateService`` (Phase 2.3-P2) reads
to update the per-athlete ``AthletePhysiology`` posterior state.

The table is append-only: there is no ``updated_at`` column and the
repository exposes no UPDATE/DELETE methods. Corrections are made by
inserting a new observation with a higher ``confidence_weight`` or a
more authoritative ``source``; the service layer is responsible for
choosing which row to treat as current.

Invariants codified at the DB layer:

* ``activity_id`` is nullable — lab/field test measurements are
  recorded without an associated ``Activity`` row. The FK uses
  ``ON DELETE SET NULL`` so deleting an activity does not destroy
  the historical observation record.
* ``parameter`` and ``source`` are stored as non-native ``String``
  enums (``native_enum=False``) so the closed ontologies live in
  ``app/models/enums.py`` and the DB stores the string value.
* ``algorithm_used`` is nullable — manual entries have no algorithm.
* ``confidence_weight`` is nullable — algorithm-specific confidence
  in the 0.0–1.0 range; manual entries omit it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import MeasurementSource, PhysiologyParameter


class PhysiologyMeasurement(Base):
    """Append-only record of a single physiological observation.

    Each row captures one (athlete, parameter, source, date) tuple
    with the observed value and any algorithm metadata. The table is
    the input to threshold detection and the historical record that
    posterior updates are derived from.
    """

    __tablename__ = "physiology_measurements"

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
    # Nullable — lab/field test measurements are recorded without an
    # associated Activity. ON DELETE SET NULL preserves the historical
    # observation when the activity is removed.
    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )
    parameter: Mapped[PhysiologyParameter] = mapped_column(
        SAEnum(
            PhysiologyParameter,
            name="physiology_parameter",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[MeasurementSource] = mapped_column(
        SAEnum(
            MeasurementSource,
            name="measurement_source",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    measurement_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Nullable — manual entries have no algorithm.
    algorithm_used: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    # Nullable — algorithm-specific confidence in the 0.0–1.0 range;
    # manual entries omit it.
    confidence_weight: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    raw_data_reference: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # History queries — newest first per athlete.
        Index(
            "ix_physiology_measurements_athlete_date",
            "athlete_id",
            "measurement_date",
        ),
        # Dedup lookup — find prior observations for the same
        # (athlete, parameter, source) tuple.
        Index(
            "ix_physiology_measurements_athlete_parameter_source",
            "athlete_id",
            "parameter",
            "source",
        ),
    )
