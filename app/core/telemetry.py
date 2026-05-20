import logging
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID

from app.models.enums import GenerationOutcome

logger = logging.getLogger("pheidipp.generation")


@dataclass
class GenerationEvent:
    athlete_id: UUID
    outcome: GenerationOutcome
    model: str
    prompt_version: str
    brief_version: str
    data_tier: str
    confidence_level: str
    latency_ms: int
    event_name: str = "generation_event"
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    stop_reason: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    context_budget: Optional[dict] = None


def log_generation_event(event: GenerationEvent) -> None:
    payload = {
        "event_name": event.event_name,
        "athlete_id": str(event.athlete_id),
        "outcome": event.outcome.value,
        "model": event.model,
        "prompt_version": event.prompt_version,
        "brief_version": event.brief_version,
        "data_tier": event.data_tier,
        "confidence_level": event.confidence_level,
        "latency_ms": event.latency_ms,
    }

    if event.input_tokens is not None:
        payload["input_tokens"] = event.input_tokens
    if event.output_tokens is not None:
        payload["output_tokens"] = event.output_tokens
    if event.stop_reason is not None:
        payload["stop_reason"] = event.stop_reason
    if event.error_type is not None:
        payload["error_type"] = event.error_type
    if event.error_message is not None:
        payload["error_message"] = event.error_message[:200]
    if event.context_budget is not None:
        payload["context_budget"] = event.context_budget

    if event.outcome == GenerationOutcome.SUCCESS:
        logger.info("Generation event", extra=payload)
    else:
        logger.error("Generation event failed", extra=payload)