"""Coaching message response schemas (Phase 1.5a)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
