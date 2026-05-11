import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    String,
    DateTime,
    Date,
    Integer,
    Float,
    ForeignKey,
    text,
    func,
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Index

from app.db.base import Base
from app.models.enums import DataSource

if TYPE_CHECKING:
    from app.models.athlete import Athlete


class AthletePhysiology(Base):
    __tablename__ = "athlete_physiology"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ftp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lt1: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    lt2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    vo2_max: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_hr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source: Mapped[DataSource] = mapped_column(
        SAEnum(DataSource, native_enum=False, length=20),
        nullable=False,
        default=DataSource.MANUAL,
    )
    effective_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    effective_to: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
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
    athlete: Mapped["Athlete"] = relationship(back_populates="physiology_versions")

    __table_args__ = (
        Index(
            "ix_athlete_physiology_athlete_date_range",
            "athlete_id",
            "effective_from",
            "effective_to",
        ),
    )
