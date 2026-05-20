import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    UUID,
    Text,
    DateTime,
    Enum as SAEnum,
    Index,
    ForeignKey,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import MessageType

if TYPE_CHECKING:
    from app.models.athlete import Athlete
    from app.models.twin_state import TwinState
    from app.models.training_block import TrainingBlock


class CoachMessage(Base):
    __tablename__ = "coach_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    twin_state_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("twin_states.id", ondelete="SET NULL"),
        nullable=True,
    )
    training_block_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("training_blocks.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(MessageType, native_enum=False, length=30),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    generation_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    athlete: Mapped["Athlete"] = relationship(
        back_populates="coach_messages",
    )
    twin_state: Mapped[Optional["TwinState"]] = relationship(
        foreign_keys=[twin_state_id],
    )
    training_block: Mapped[Optional["TrainingBlock"]] = relationship(
        foreign_keys=[training_block_id],
    )

    __table_args__ = (
        Index("ix_coach_messages_athlete_type", "athlete_id", "message_type"),
        Index("ix_coach_messages_athlete_created_at", "athlete_id", "created_at"),
    )