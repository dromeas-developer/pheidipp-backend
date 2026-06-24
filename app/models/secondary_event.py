"""SecondaryEvent — supporting storage table for a TrainingGoal's B/C-races.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/training-goal.md → ``SecondaryEvent``.

Schema-only foundation: there is no registration or removal service
in this plan. The table exists so the ``training_goals`` FK graph is
complete at the database layer and so later phases can attach
services without re-creating supporting storage.

Maximum-3-per-goal and conflict-with-taper semantics are enforced
at the application layer in later phases; this schema only stores
the rows.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Index, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import GoalEventType, SecondaryEventPriority


class SecondaryEvent(Base):
    """B-event / C-event recorded against a parent ``TrainingGoal``.

    Always represents an event that influences plan structure but is
    not the primary periodisation driver.
    """

    __tablename__ = "secondary_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # FK to training_goals. The training_goals table is created in
    # the same migration so this FK is satisfiable at DB creation
    # time.
    training_goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[GoalEventType] = mapped_column(
        SAEnum(
            GoalEventType,
            name="goal_event_type",
            native_enum=False,
            length=32,
            values_callable=lambda x: [e.value for e in x],
            create_type=False,
        ),
        nullable=False,
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[SecondaryEventPriority] = mapped_column(
        SAEnum(
            SecondaryEventPriority,
            name="secondary_event_priority",
            native_enum=False,
            length=16,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_secondary_events_goal_date", "training_goal_id", "event_date"),
        Index("ix_secondary_events_goal", "training_goal_id"),
    )
