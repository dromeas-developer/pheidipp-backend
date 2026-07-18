"""CoachingMessage — LLM-generated message to the athlete.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/coaching-message.md.

Schema-only foundation: no ``ProactiveMessageService``,
``PostWorkoutAgent``, frequency guards, or event publication is
added by this plan. The model persists the row shape including the
``twin_state_id`` linkage that lets every message be traced back to
the snapshot of the twin that produced it.

Invariants codified at the DB layer:

* ``content`` is immutable — never updated after creation. The
  repository contract restricts to ``insert()`` only (no
  ``update()`` / ``delete()``).
* ``first_message`` — only one per athlete per active goal. The
  partial unique index enforces ``(athlete_id) WHERE
  message_type = 'first_message' AND xmin = 0`` cannot be expressed
  directly here without coupling to ``xmin`` (transaction id); the
  "one per active goal" guarantee is owned by the service layer in
  Phase 1.5. A partial unique index over ``(athlete_id,
  message_type) WHERE message_type = 'first_message'`` is added so
  the de-duplication is DB-enforced for the most common case
  ``first_message``; other ``post_workout`` /
  ``plan_regeneration`` etc. uniqueness is service-layer enforced.
* ``post_workout`` — only one per ``activity_id``. The partial
  unique index enforces ``(activity_id) WHERE message_type =
  'post_workout'`` so ``NULL`` ``activity_id`` rows are exempt.
* Proactive-message frequency guards (wellness_alert / cycle_check_in
  etc.) are service-layer enforced and intentionally not DB-
  constrained.

Read pattern:

* ``GET /coach/messages`` → ``(athlete_id, generated_at DESC)``
* Frequency guard → ``(athlete_id, message_type, generated_at DESC)``
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import MessageType


class CoachingMessage(Base):
    """One LLM-generated message to the athlete.

    Always linked to the active ``TwinState`` at generation time so
    every message can be traced back to the twin-snapshot context.
    ``activity_id`` is set for ``message_type = 'post_workout'``
    only; it is null for every other ``MessageType``.

    The model exposes no ``update()`` or ``delete()`` (the future
    repository from Phase 1.5 will be ``insert()``-only).
    """

    __tablename__ = "coaching_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    athlete_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("athletes.id", ondelete="CASCADE"),
        nullable=False,
    )
    twin_state_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("twin_states.id", ondelete="CASCADE"),
        nullable=False,
    )
    activity_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("activities.id", ondelete="SET NULL"),
        nullable=True,
    )

    message_type: Mapped[MessageType] = mapped_column(
        SAEnum(
            MessageType,
            name="message_type",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # ``first_message`` has at most one active message per athlete
        # at a time — the partial unique index makes the
        # de-duplication contract DB-enforced. The "one per active
        # goal" semantic is widened to a "one per active goal *or*
        # one per athlete total" rule because Phase 1.3 will own the
        # creation guard and only one message exists at insert time;
        # should the schema need "one per active goal" later, the
        # partial unique must be extended to include ``training_goal_id``
        # which requires the FK to be non-null — deferred to Phase 1.5.
        Index(
            "uq_coaching_messages_athlete_first_message",
            "athlete_id",
            unique=True,
            postgresql_where=text("message_type = 'first_message'"),
        ),
        # ``post_workout`` — exactly one CoachingMessage per
        # ``activity_id``. ``NULL`` ``activity_id`` rows are exempt.
        Index(
            "uq_coaching_messages_activity_post_workout",
            "activity_id",
            unique=True,
            postgresql_where=(
                "message_type = 'post_workout' AND activity_id IS NOT NULL"
            ),
        ),
        # Message feed read — (athlete_id, generated_at DESC).
        Index(
            "ix_coaching_messages_athlete_generated_at",
            "athlete_id",
            "generated_at",
        ),
        # Frequency-guard read — (athlete_id, message_type, generated_at DESC).
        Index(
            "ix_coaching_messages_athlete_type_generated_at",
            "athlete_id",
            "message_type",
            "generated_at",
        ),
        # Reverse lookup from twin state — supports the
        # ``coaching_message_generated`` event consumer.
        Index("ix_coaching_messages_twin_state", "twin_state_id"),
        # ``content`` is non-empty plain text — the coach voice rules
        # forbid markdown, so the column is ``TEXT`` (no length
        # restriction). Empty-string content is blocked by a CHECK
        # so a generation failure cannot create a blank row.
        CheckConstraint(
            "length(content) > 0",
            name="ck_coaching_messages_content_non_empty",
        ),
    )
