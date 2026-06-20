"""RefreshToken — append-only revocation ledger for Pheidipp sessions.

Implements the Phase-1.1 contract from
docs/architecture/01-entities/athlete-auth.md.

Rotation is the only mutation: the old row is marked revoked and a new row
is inserted in the same transaction. Plaintext refresh tokens are never
persisted; only SHA-256 hashes are stored.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RefreshToken(Base):
    """Opaque refresh token record (append-only)."""

    __tablename__ = "athlete_refresh_tokens"

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
    # SHA-256 hex digest of the opaque refresh token. Unique by hash.
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # Self-referencing FK to the replacement token. Populated atomically on
    # rotation so the audit trail links old -> new.
    replaced_by_refresh_token_id: Mapped[uuid.UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("athlete_refresh_tokens.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index(
            "ix_athlete_refresh_tokens_athlete_expires",
            "athlete_id",
            "expires_at",
        ),
    )
