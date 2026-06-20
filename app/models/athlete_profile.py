"""AthleteProfile — stable demographic identity.

Implements the Phase-1.1 contract from
docs/architecture/01-entities/athlete-profile.md.

Phase-1.1 keeps the profile minimal: only ``date_of_birth``, ``sex`` and
``height_cm`` are written at registration. Fields such as location,
timezone, training_window, the personalisation models (gap_curve_model,
weather_response_model, banister_constants, cycle_personal_model), and the
structural/effort generation state belong to Phase-1.2a / later phases.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import Sex


class AthleteProfile(Base):
    """One-to-one demographic profile for an athlete."""

    __tablename__ = "athlete_profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Sex] = mapped_column(
        SAEnum(
            Sex,
            name="sex",
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )
    # Numeric to support decimal heights; nullable per Phase-1.1 spec.
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
