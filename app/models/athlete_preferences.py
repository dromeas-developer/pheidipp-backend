"""AthletePreferences — mutable training configuration.

Implements the Phase-1.2a contract from
docs/architecture/01-entities/athlete-preferences.md.

Owns hardware, platform, and schedule preferences. Drives data-tier
inference and weekly schedule-aware plan generation. Distinct from
``AthleteProfile``, which owns stable demographic identity and fitted
personalisation models.
"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import (
    DataTier,
    GpsSource,
    HrSource,
    PowerSource,
    PrimaryTrainingPlatform,
    SportBackground,
    TrainingTimeOfDay,
)


class AthletePreferences(Base):
    """One-to-one mutable training configuration for an athlete.

    Existence:
        Created during onboarding (out of scope for this plan).
        One ``AthletePreferences`` row per ``Athlete`` — enforced by the
        unique constraint on ``athlete_id``.

    Weekly schedule:
        ``weekly_schedule`` is structured JSONB, keyed by weekday with
        per-day ``available``, ``max_hours``, ``long_workout``,
        ``doubles_eligible`` fields. The schema is enforced at the
        application layer; storage stays flexible so partial PATCH
        merges at the day level.

    Data tier:
        Derived from ``hr_source`` and ``power_source`` at read time —
        no separate column. See
        ``docs/architecture/00-foundations/data-tiers.md``.
    """

    __tablename__ = "athlete_preferences"

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

    # ------------------------------------------------------------------
    # ``running_primary`` is the canonical running-only path; any other
    # value marks a crossover athlete and triggers the structural
    # capacity ramp in plan generation.
    # ------------------------------------------------------------------
    sport_background: Mapped[SportBackground] = mapped_column(
        SAEnum(
            SportBackground,
            name="sport_background",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    years_structured_training: Mapped[int] = mapped_column(Integer, nullable=False)

    # ------------------------------------------------------------------
    # ``training_time_of_day`` feeds the time-of-day modifier in
    # ``WellnessModifierService``.
    # ``weekly_schedule`` is structured JSONB; each day carries
    # ``available``, ``max_hours``, ``long_workout``,
    # ``doubles_eligible`` — see architecture doc.
    # ------------------------------------------------------------------
    training_time_of_day: Mapped[TrainingTimeOfDay] = mapped_column(
        SAEnum(
            TrainingTimeOfDay,
            name="training_time_of_day",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    weekly_schedule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)

    # ------------------------------------------------------------------
    # Hardware fields drive data-tier inference (see architecture doc).
    # ``primary_training_platform`` is the source of truth for the
    # integration team — when the athlete's primary platform changes,
    # the integration team re-syncs their connector.
    # ------------------------------------------------------------------
    gps_source: Mapped[GpsSource] = mapped_column(
        SAEnum(
            GpsSource,
            name="gps_source",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    hr_source: Mapped[HrSource] = mapped_column(
        SAEnum(
            HrSource,
            name="hr_source",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    power_source: Mapped[PowerSource] = mapped_column(
        SAEnum(
            PowerSource,
            name="power_source",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    primary_training_platform: Mapped[PrimaryTrainingPlatform] = mapped_column(
        SAEnum(
            PrimaryTrainingPlatform,
            name="primary_training_platform",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Architecture invariant: ``years_structured_training >= 0``.
        CheckConstraint(
            "years_structured_training >= 0",
            name="ck_athlete_preferences_years_structured_training_non_negative",
        ),
    )


def infer_data_tier(hr_source: HrSource, power_source: PowerSource) -> DataTier:
    """Map an athlete's HR + power source to a hardware data tier.

    Implements the canonical inference rule from
    ``docs/architecture/00-foundations/data-tiers.md``. Outcomes:

    * Running power meter + chest strap (RR) → Tier 1
    * Running power meter + non-RR HR → Tier 2
    * Chest strap (RR) alone → Tier 3
    * Chest strap (no RR) or wrist optical → Tier 4
    * ``HrSource.NONE`` → Tier 5
    * Fallback → Tier 6 (manual-entry path)

    The function is pure; the model row carries the source enums, this
    helper is invoked at read time by services that need the tier
    (e.g. ``PlanGenerationService``, ``WellnessModifierService``).
    """
    if hr_source == HrSource.NONE:
        return DataTier.TIER_5
    if power_source == PowerSource.RUNNING_POWER_METER:
        return (
            DataTier.TIER_1 if hr_source == HrSource.CHEST_STRAP_RR else DataTier.TIER_2
        )
    if hr_source == HrSource.CHEST_STRAP_RR:
        return DataTier.TIER_3
    if hr_source in {HrSource.CHEST_STRAP_NO_RR, HrSource.WRIST_OPTICAL}:
        return DataTier.TIER_4
    return DataTier.TIER_6
