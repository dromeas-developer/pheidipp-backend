"""Athlete — root identity entity.

Implements the Phase-1.1 contract from
docs/architecture/01-entities/athlete.md.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Athlete(Base):
    """Root identity for every user; owns the onboarding-complete gate."""

    __tablename__ = "athletes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    onboarding_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        # DB-enforced case-insensitive email uniqueness: the application
        # always stores lowercased emails so the column value already
        # matches ``lower(column)``; this functional index gives us a
        # defensible protection layer if a non-normalised value slips
        # into the column.
        Index(
            "ix_athletes_lower_email_unique",
            func.lower(text("email")),
            unique=True,
        ),
    )
