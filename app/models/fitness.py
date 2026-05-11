import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    String,
    DateTime,
    Date,
    Float,
    ForeignKey,
    text,
    func,
    Enum as SAEnum,
)
from sqlalchemy import UniqueConstraint as UC
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import DataSource

if TYPE_CHECKING:
    from app.models.athlete import Athlete


class AthleteFitness(Base):
    __tablename__ = "athlete_fitness"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=text("gen_random_uuid()"),
        primary_key=True,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    metric_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )
    tss: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    atl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ctl: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tsb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[DataSource] = mapped_column(
        SAEnum(DataSource, native_enum=False, length=20),
        nullable=False,
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

    athlete: Mapped["Athlete"] = relationship(back_populates="fitness_metrics")

    __table_args__ = (
        UC("athlete_id", "metric_date", name="uq_athlete_fitness_date"),
    )