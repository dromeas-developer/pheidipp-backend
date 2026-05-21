import json
import time
import uuid
from typing import Tuple

import openai

from app.core.llm_router import get_llm
from app.config import settings
from app.agents.prompts.registry import PromptRegistry
from app.agents.prompts.plan_generation_v1 import _build_user_message
from app.core.telemetry import GenerationEvent, log_generation_event
from app.models.enums import GenerationOutcome
from app.schemas.plan_generation import PlanBlueprint
from app.services.plan_generation_brief_builder import PlanGenerationBrief


AGENT_NAME = "plan_generation"


class PlanGenerationAgent:
    def __init__(self):
        self._client = get_llm()

    async def generate(
        self, athlete_id: uuid.UUID, brief: PlanGenerationBrief
    ) -> Tuple[dict, dict]:
        prompt_record = PromptRegistry.current(AGENT_NAME)
        user_message = _build_user_message(brief)

        start_time = time.monotonic()
        input_tokens = None
        output_tokens = None
        stop_reason = None
        content = None

        try:
            response = await self._client.chat.completions.create(
                model=settings.LLM_MODEL,
                max_tokens=prompt_record.max_output_tokens,
                temperature=0.2,
                messages=[
                    {"role": "system", "content": prompt_record.system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            if response.choices:
                stop_reason = response.choices[0].finish_reason
                content = response.choices[0].message.content

            if not content:
                self._log_event(
                    athlete_id,
                    GenerationOutcome.MALFORMED,
                    prompt_record,
                    brief,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    stop_reason,
                    error_type="EmptyContent",
                    error_message="Agent returned empty content",
                )
                raise ValueError("Agent returned empty content")

            # Parse JSON content
            try:
                blueprint_dict = json.loads(content)
            except json.JSONDecodeError as e:
                self._log_event(
                    athlete_id,
                    GenerationOutcome.MALFORMED,
                    prompt_record,
                    brief,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    stop_reason,
                    error_type="JSONDecodeError",
                    error_message=str(e),
                )
                raise ValueError(f"Agent returned invalid JSON: {e}")

            # Validate against PlanBlueprint schema
            try:
                PlanBlueprint.model_validate(blueprint_dict)
            except Exception as e:
                self._log_event(
                    athlete_id,
                    GenerationOutcome.MALFORMED,
                    prompt_record,
                    brief,
                    latency_ms,
                    input_tokens,
                    output_tokens,
                    stop_reason,
                    error_type="SchemaValidationError",
                    error_message=str(e),
                )
                raise ValueError(f"Agent returned invalid blueprint: {e}")

            metadata = {
                "model": settings.LLM_MODEL,
                "prompt_version": prompt_record.version,
                "brief_version": brief.brief_version,
                "outcome": GenerationOutcome.SUCCESS.value,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "stop_reason": stop_reason,
            }

            self._log_event(
                athlete_id,
                GenerationOutcome.SUCCESS,
                prompt_record,
                brief,
                latency_ms,
                input_tokens,
                output_tokens,
                stop_reason,
            )

            return blueprint_dict, metadata

        except (openai.APITimeoutError, openai.APIStatusError) as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            if isinstance(e, openai.APITimeoutError):
                outcome = GenerationOutcome.TIMEOUT
            elif e.status_code == 429:
                outcome = GenerationOutcome.RATE_LIMITED
            else:
                outcome = GenerationOutcome.PROVIDER_ERROR

            self._log_event(
                athlete_id,
                outcome,
                prompt_record,
                brief,
                latency_ms,
                input_tokens,
                output_tokens,
                stop_reason,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            self._log_event(
                athlete_id,
                GenerationOutcome.INTERNAL_ERROR,
                prompt_record,
                brief,
                latency_ms,
                input_tokens,
                output_tokens,
                stop_reason,
                error_type=type(e).__name__,
                error_message=str(e),
            )
            raise

    def _log_event(
        self,
        athlete_id: uuid.UUID,
        outcome: GenerationOutcome,
        prompt_record,
        brief: PlanGenerationBrief,
        latency_ms: int,
        input_tokens: int | None,
        output_tokens: int | None,
        stop_reason: str | None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> None:
        twin = brief.twin_summary
        data_tier = twin.get("data_tier", "tier5")
        confidence = twin.get("confidence_level", "low")

        event = GenerationEvent(
            athlete_id=athlete_id,
            outcome=outcome,
            model=settings.LLM_MODEL,
            prompt_version=prompt_record.version,
            brief_version=brief.brief_version,
            data_tier=data_tier,
            confidence_level=confidence,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
            error_type=error_type,
            error_message=error_message,
        )
        log_generation_event(event)