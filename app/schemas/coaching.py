"""Coaching message response schemas (Phase 1.5a).

Wire-format contracts for the coach endpoints:

- ``GET /athletes/{id}/coach/messages`` → ``MessagesListResponse``
- ``POST /athletes/{id}/coach/first-message`` → ``CoachingMessageResponse``

All ORM rows feed directly into Pydantic via ``model_validate`` /
``from_attributes=True`` so the conversion lives in one place.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CoachingMessageResponse(BaseModel):
    """One coaching message returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    message_type: str
    content: str
    generated_at: datetime
    prompt_version: str
    twin_state_id: UUID


class FirstMessageConflictResponse(BaseModel):
    """Response body when a first message already exists (HTTP 409)."""

    existing_message_id: UUID
    message_type: str = "first_message"


class MessagesListResponse(BaseModel):
    """List of coaching messages for an athlete."""

    messages: list[CoachingMessageResponse]
    total: int