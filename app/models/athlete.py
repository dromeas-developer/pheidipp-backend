import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    String,
    DateTime,
    Date,
    ForeignKey,
    Enum as SAEnum,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    AthleteStatus,
    Gender,
    CountryCode,
    Timezone,
    LanguageCode,
    UnitPreference,
)

if TYPE_CHECKING:
    from app.models.activity import Activity
    from app.models.wellness import AthleteWellness


class Athlete(Base):
    __tablename__ = "athletes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    status: Mapped[AthleteStatus] = mapped_column(
        SAEnum(AthleteStatus, native_enum=False, length=20),
        default=AthleteStatus.ONBOARDING,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    profile: Mapped[Optional["AthleteProfile"]] = relationship(
        back_populates="athlete",
        uselist=False,
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="athlete",
    )
    wellness_metrics: Mapped[list["AthleteWellness"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
    )


class AthleteProfile(Base):
    __tablename__ = "athlete_profiles"

    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        primary_key=True,
    )
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    display_name: Mapped[Optional[str]] = mapped_column(String(100))
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    gender: Mapped[Optional[Gender]] = mapped_column(
        SAEnum(Gender, native_enum=False, length=20)
    )
    country_code: Mapped[Optional[CountryCode]] = mapped_column(
        SAEnum(CountryCode, native_enum=False, length=5)
    )
    timezone: Mapped[Optional[Timezone]] = mapped_column(
        SAEnum(Timezone, native_enum=False, length=50)
    )
    language_code: Mapped[Optional[LanguageCode]] = mapped_column(
        SAEnum(LanguageCode, native_enum=False, length=5)
    )
    unit_preference: Mapped[UnitPreference] = mapped_column(
        SAEnum(UnitPreference, native_enum=False, length=20),
        default=UnitPreference.METRIC,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    athlete: Mapped["Athlete"] = relationship(back_populates="profile")
