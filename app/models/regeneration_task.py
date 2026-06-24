"""RegenerationTask — supporting storage for a coach-proposed date change.

Implements the Phase-1.2b schema contract from
docs/architecture/01-entities/training-goal.md → ``RegenerationTask``.

Schema-only foundation: this is the storage shape only. There is no
proposal, confirmation, or expiry service in this plan; those land in
a later phase. The pending-proposal index is created so future
services can scan pending tasks efficiently.

Status semantics (string column with CHECK):

    pending_confirmation   ← proposed, awaiting athlete decision
    confirmed              ← athlete accepted; plan regeneration
                             cascades to ``TrainingPlan``
    declined               ← athlete rejected the proposal
    expired                ← 14-day proposal TTL elapsed without
                             confirmation; serves the
                             "Stagnant Proposals" alert

``training_plan_id`` is nullable: it points to the new plan created
when the task is confirmed; for ``pending_confirmation``,
``declined``, and ``expired`` rows it stays null.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RegenerationTask(Base):
    """Coach-proposed date change against a parent ``TrainingGoal``.

    The lifecycle is short-lived (≤ 14 days); confirmed tasks lead to
    a new ``TrainingPlan`` row, declined / expired tasks remain
    immutable for audit. The trigger field captures the coach's
    rationale axis (trajectory_ahead / at_risk / conversation).
    """

    __tablename__ = "regeneration_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    training_goal_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_goals.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Nullable FK — set only when the task is confirmed and the new
    # plan has been generated. ``training_plans`` is in this same
    # migration, so the FK is satisfiable at creation time.
    training_plan_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("training_plans.id", ondelete="SET NULL"),
        nullable=True,
    )

    proposed_date: Mapped[date] = mapped_column(Date, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    # Inline-unioned values from the architecture contract:
    # trajectory_ahead | trajectory_at_risk | coach_conversation.
    trigger: Mapped[str] = mapped_column(Text, nullable=False)

    # Status lifecycle — checked allowed-values list.
    status: Mapped[str] = mapped_column(Text, nullable=False)

    proposed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        # Status must be one of the four canonical values.
        CheckConstraint(
            "status IN ('pending_confirmation', 'confirmed', 'declined', 'expired')",
            name="ck_regeneration_tasks_status_valid",
        ),
        # Partial index on pending proposals per goal — the
        # "Stagnant Proposals" alert query path.
        Index(
            "ix_regeneration_tasks_pending",
            "training_goal_id",
            "status",
            postgresql_where=text("status = 'pending_confirmation'"),
        ),
    )
