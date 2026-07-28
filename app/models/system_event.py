"""SystemEvent — append-only event log persistence.

Implements the persistence layer required by
docs/architecture/00-foundations/event-catalogue.md and
docs/architecture/04-platform/system-event.md.

The ``system_events`` table is append-only — never UPDATE or DELETE —
matching the architecture's invariant that production events are an
immutable audit trail. The companion ``system_event_outbox`` table is
the only mutable event-related state, tracking publication status for
at-least-once delivery semantics defined in ADR-004.

The producer writes the SystemEvent row and a paired
``SystemEventOutbox`` row with status='pending' in the SAME database
transaction as the producing domain state change. This satisfies
ADR-004 rule "Event Persistence Atomicity". The transaction commits
exactly once.
"""

from __future__ import annotations

from typing import Any

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values


class EventPublicationStatus(str, enum.Enum):
    """Publication state machine for an event in ``system_event_outbox``."""

    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
    DLQ = "dlq"


class SystemEvent(Base):
    """Append-only event log row. ``event_id`` is the primary key."""

    __tablename__ = "system_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(96), nullable=False)
    version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    athlete_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    produced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_system_events_athlete_at", "athlete_id", "produced_at"),
        Index("ix_system_events_type_at", "event_type", "produced_at"),
    )


class SystemEventOutbox(Base):
    """Mutable publication state for a persisted SystemEvent.

    One row per event; the unique ``event_id`` constraint guarantees that
    the producer cannot write the event's outbox entry twice. Publication
    state transitions are the only allowed mutation on event-related
    tables ADR-004 rule "Outbox Status Management".

    The DB column is named ``status`` (per the original
    ADR-004 schema: a single mutable state column on the outbox
    row). Public callers and the test manifest canonically refer
    to the same field as ``publication_status``. The
    ``publication_status`` mapped attribute below aliases the
    ``status`` column so both names read from the same underlying
    state — no schema change, no app breakage when callers use
    either name in tests.
    """

    __tablename__ = "system_event_outbox"

    event_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("system_events.event_id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[EventPublicationStatus] = mapped_column(
        SAEnum(
            EventPublicationStatus,
            name="event_publication_status",
            native_enum=False,
            length=16,
            values_callable=enum_str_values,
        ),
        nullable=False,
        default=EventPublicationStatus.PENDING,
        server_default=EventPublicationStatus.PENDING.value,
        name="status",
        doc=(
            "Publication state for this outbox row. See "
            "``publication_status`` for the canonical public-facing "
            "alias used by API and test contracts."
        ),
    )

    @property
    def publication_status(self) -> EventPublicationStatus:
        """Canonical public-facing alias for ``status``.

        Mirrors ``docs/architecture/04-platform/system-event.md``
        (``EventPublicationStatus``) and the
        ``tests/test-manifest/phase-1-4.yaml`` contract
        ("SystemEventOutbox row exists with publication_status='pending'
        paired with the SystemEvent row"). Returns the underlying
        ``status`` so writes through ``status = ...`` and reads
        through ``publication_status`` always agree.
        """
        return self.status

    @publication_status.setter
    def publication_status(self, value: EventPublicationStatus) -> None:
        """Allow callers to write through the public alias too.

        The publisher worker may flip either field to
        ``PUBLISHED`` / ``FAILED`` / ``DLQ``; both writes land on the
        same DB column thanks to the Python-level setter route.
        """
        self.status = value

    attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','published','failed','dlq')",
            name="ck_system_event_outbox_status_valid",
        ),
        Index(
            "ix_system_event_outbox_status_created",
            "status",
            "created_at",
        ),
        Index(
            "ix_system_event_outbox_pending_failed",
            "created_at",
            postgresql_where=("status IN ('pending', 'failed')"),
        ),
    )
