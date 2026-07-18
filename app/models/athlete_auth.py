"""AthleteAuth — authentication credentials and provider state.

Implements the Phase-1.1 contract from
docs/architecture/01-entities/athlete-auth.md.

Phase-1.1 only persists the ``email`` provider path. The ``provider``,
``provider_user_id``, and ``provider_tokens`` columns exist for OAuth
extension but are not used by any Phase-1.1 code path. ``hashed_password``
is bcrypt with cost >= 12.
"""

from __future__ import annotations

from typing import Any

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._enum_helpers import enum_str_values
from app.models.enums import AuthProvider


class AthleteAuth(Base):
    """Authentication credential record for a single athlete-provider pair."""

    __tablename__ = "athlete_auths"

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
    provider: Mapped[AuthProvider] = mapped_column(
        SAEnum(
            AuthProvider,
            name="auth_provider",
            native_enum=False,
            length=32,
            values_callable=enum_str_values,
        ),
        nullable=False,
    )
    provider_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # bcrypt cost >= 12; null for OAuth providers.
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Encrypted JSON (AES-256-GCM) — null for email provider.
    provider_tokens: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
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
        UniqueConstraint(
            "athlete_id", "provider", name="uq_athlete_auths_athlete_id_provider"
        ),
        # Partial unique index enforcing the Phase-1.1 invariant that
        # exactly one AthleteAuth row per athlete has ``is_primary = true``.
        # PostgreSQL-specifies the WHERE clause; rows with ``is_primary = false``
        # are excluded so multiple non-primary methods may coexist.
        Index(
            "ix_athlete_auths_single_primary",
            "athlete_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
        ),
        Index(
            "ix_athlete_auths_provider_user_id",
            "provider_user_id",
        ),
    )
