"""AthleteProfile — stable demographic identity.

Implements the Phase-1.2a contract from
docs/architecture/01-entities/athlete-profile.md.

The table was originally created in Phase-1.1 with a minimal registration
schema (``date_of_birth``, ``sex``, ``height_cm``); it is now extended
additively to hold the full personalisation / location / scheduling /
effort-generation profile without dropping any existing column.

All onboarding-required enrichment fields (``timezone``, fitted model
JSONBs, ``structural_risk_flag``, ``current_effort_generation``,
``objective_thresholds``) are nullable so the Phase-1.1 registration
journey continues to create exactly one minimal profile. Onboarding
writes are out of scope for this plan.
"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import Sex


class AthleteProfile(Base):
    """One-to-one demographic profile for an athlete.

    Owns stable demographics and fitted personalisation models only.
    Mutable training configuration (hardware, schedule, platform)
    belongs to ``AthletePreferences``.
    """

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
    # Phase-1.1 invariants — immutable demographics at registration.
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=False)
    sex: Mapped[Sex] = mapped_column(
        SAEnum(
            Sex,
            name="sex",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    # Numeric to support decimal heights; nullable per Phase-1.1 spec.
    height_cm: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)

    # ------------------------------------------------------------------
    # Phase-1.2a extension — personalisation model JSONBs.
    #
    # Each field is nullable. ``null`` means "no fitted model available";
    # services fall back to population defaults in that case. See the
    # architecture doc for fit rules (e.g. ``gap_curve_model`` requires
    # ``r_squared >= 0.70`` to upgrade ``current_effort_generation``).
    # ------------------------------------------------------------------
    gap_curve_model: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    weather_response_model: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    banister_constants: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    cycle_personal_model: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # ------------------------------------------------------------------
    # ``timezone`` is validated at onboarding against the IANA tz
    # database and immutable thereafter — changing it requires a
    # support process. All scheduled tasks (MissedSessionSweepTask,
    # WorkoutPrefetchTask) read this value verbatim.
    # ``training_window`` defaults to 06:00–20:00 if not set; stored as
    # structured JSONB so the prefetch task can read it without parsing.
    # ------------------------------------------------------------------
    location_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    location_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    training_window: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # ------------------------------------------------------------------
    # Effort-generation and risk state.
    #
    # ``current_effort_generation`` is a 3-state hysteresis value
    # (1|2|3) maintained by ``GapCurveFittingService``.
    # ``structural_risk_flag`` is computed at onboarding from
    # ``AthletePreferences.sport_background`` to switch the structural
    # load coefficient between the running default and the crossover
    # adjustment. Both are nullable so a fresh profile created during
    # the Phase-1.1 registration path continues to be valid.
    # ``objective_thresholds`` is optional per-athlete override of the
    # population evaluation thresholds.
    # ------------------------------------------------------------------
    current_effort_generation: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    structural_risk_flag: Mapped[bool | None] = mapped_column(nullable=True)
    objective_thresholds: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
