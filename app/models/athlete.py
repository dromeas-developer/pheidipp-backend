import uuid
from datetime import  datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    String,
    DateTime,
    Boolean,
    Enum as SAEnum,
    text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AthleteStatus

if TYPE_CHECKING:
    from app.models.athlete_profile import AthleteProfile
    from app.models.activity import Activity
    from app.models.physiology import AthletePhysiology
    from app.models.wellness import AthleteWellness
    from app.models.fitness import AthleteFitness
    from app.models.athlete_preferences import AthletePreferences
    from app.models.training_block import TrainingBlock



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
        nullable=False,
    )
    onboarding_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
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
        cascade="all, delete-orphan",
    )
    activities: Mapped[list["Activity"]] = relationship(
        back_populates="athlete",
    )
    physiology_versions: Mapped[list["AthletePhysiology"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
    )
    wellness_metrics: Mapped[list["AthleteWellness"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
    )
    fitness_metrics: Mapped[list["AthleteFitness"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
    )
    preferences: Mapped[Optional["AthletePreferences"]] = relationship(
        back_populates="athlete",
        uselist=False,
        cascade="all, delete-orphan",
    )
    training_blocks: Mapped[list["TrainingBlock"]] = relationship(
        back_populates="athlete",
        cascade="all, delete-orphan",
        order_by="TrainingBlock.created_at.desc()",
    )
