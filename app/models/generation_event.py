"""GenerationEvent — append-only audit log for every LLM API call.

Implements the Phase-1.2c schema contract from
docs/architecture/01-entities/generation-event.md.

Schema-only foundation: no LLM-side instrumentation service, prompt
registry, or token-counting adapter is added by this plan. The model
persists the row shape with the strict ``failure_reason NOT NULL when
success = false`` invariant enforced at the DB layer.

Invariants codified at the DB layer:

* Every row represents a single LLM call attempt — success or
  failure. Records never update after creation. The service-layer
  ``LLMInstrumentationService`` (later phase) is the sole writer.
* ``failure_reason IS NOT NULL`` when ``success = false`` and
  ``failure_reason IS NULL`` when ``success = true`` — enforced
  via a CHECK constraint so the audit log stays consistent.
* ``input_token_count`` and ``output_token_count`` are required even
  on failure — captured as much as possible before the timeout /
  parse failure.
* ``latency_ms`` is required (performance dashboards).
* ``agent_name`` matches the class name of the caller.

Read patterns:

* Per-athlete audit → ``(athlete_id, created_at DESC)``
* Per-agent monitoring → ``(agent_name, created_at DESC)``
* Failure dashboards → ``(success, created_at DESC)``
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GenerationEvent(Base):
    """One terminal audit row per LLM API call.

    Written by the LLM-instrumentation adapter every time a call is
    attempted — successful or not. The PK is ``id`` (UUID); the
    repository exposes ``insert()`` only (no ``update`` / ``delete``)
    so the audit log never mutates after insert.

    Token counts default to 0 in the table so a failure-before-counts
    row can still be inserted without violating NOT NULL.
    """

    __tablename__ = "generation_events"

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
    agent_name: Mapped[str] = mapped_column(String(96), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    trigger_context: Mapped[str] = mapped_column(Text, nullable=False)

    input_token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    output_token_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    latency_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    success: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # Per-athlete audit feed.
        Index(
            "ix_generation_events_athlete_at",
            "athlete_id",
            "created_at",
        ),
        # Per-agent cost / success / latency dashboards.
        Index(
            "ix_generation_events_agent_at",
            "agent_name",
            "created_at",
        ),
        # Failure-rate dashboards.
        Index(
            "ix_generation_events_success_at",
            "success",
            "created_at",
        ),
        # Required token counts — non-negative on both axes.
        CheckConstraint(
            "input_token_count >= 0 AND output_token_count >= 0",
            name="ck_generation_events_token_counts_non_negative",
        ),
        # Architecture invariant — ``failure_reason`` non-null iff
        # ``success = false``.
        CheckConstraint(
            "(success = TRUE AND failure_reason IS NULL) OR "
            "(success = FALSE AND failure_reason IS NOT NULL)",
            name="ck_generation_events_failure_reason_consistency",
        ),
        # ``latency_ms`` is required and non-negative.
        CheckConstraint(
            "latency_ms >= 0",
            name="ck_generation_events_latency_non_negative",
        ),
    )
