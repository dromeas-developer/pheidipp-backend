import time
import uuid
from typing import Tuple

import openai

from app.core.llm import get_litellm_client
from app.config import settings
from app.agents.prompts.registry import PromptRegistry
from app.core.telemetry import GenerationEvent, log_generation_event
from app.models.enums import GenerationOutcome
from app.services.first_message_brief_builder import FirstMessageCoachingBrief


AGENT_NAME = "first_message"


def _build_user_message(brief: FirstMessageCoachingBrief) -> str:
    athlete = brief.athlete
    goal = brief.goal
    twin = brief.twin
    plan = brief.plan
    insights = brief.insights

    message_parts = [
        f"Athlete: {athlete.first_name}",
    ]

    if athlete.age:
        message_parts.append(f"Age: {athlete.age}")
    if athlete.gender:
        message_parts.append(f"Gender: {athlete.gender.value}")
    if athlete.sport_background:
        message_parts.append(f"Sport background: {athlete.sport_background.value}")
    if athlete.years_structured_training:
        message_parts.append(f"Years of structured training: {athlete.years_structured_training}")
    if athlete.training_time_of_day:
        message_parts.append(f"Preferred training time: {athlete.training_time_of_day}")

    message_parts.append("")
    message_parts.append("Goal:")

    if goal.goal_type:
        message_parts.append(f"  Type: {goal.goal_type.value}")
    if goal.goal_event_type:
        message_parts.append(f"  Event: {goal.goal_event_type}")
    if goal.goal_event_name:
        message_parts.append(f"  Event name: {goal.goal_event_name}")
    if goal.goal_event_date:
        message_parts.append(f"  Event date: {goal.goal_event_date}")
    if goal.goal_description:
        message_parts.append(f"  Description: {goal.goal_description}")
    if goal.weeks_to_event is not None:
        message_parts.append(f"  Weeks to event: {goal.weeks_to_event}")
    message_parts.append(f"  Open training: {goal.is_open_training}")

    message_parts.append("")
    message_parts.append("Twin State:")
    message_parts.append(f"  Fitness score: {twin.fitness_score} ({twin.fitness_band})")
    message_parts.append(f"  Fatigue score: {twin.fatigue_score}")
    message_parts.append(f"  Structural capacity: {twin.structural_capacity_score:.2f} ({twin.structural_band})")
    message_parts.append(f"  Confidence level: {twin.confidence_level.value}")
    message_parts.append(f"  Data tier: {twin.data_tier}")

    if twin.include_threshold_descriptors:
        message_parts.append(f"  Max HR: {twin.hr_descriptor}")
        message_parts.append(f"  LT1 HR estimate: {twin.lt1_hr_estimate}")
        message_parts.append(f"  LT2 HR estimate: {twin.lt2_hr_estimate}")
        if twin.lt1_pace_estimate:
            message_parts.append(f"  LT1 pace estimate: {twin.lt1_pace_estimate}")
        if twin.lt2_pace_estimate:
            message_parts.append(f"  LT2 pace estimate: {twin.lt2_pace_estimate}")

    message_parts.append("")
    message_parts.append("Plan:")
    message_parts.append(f"  Arc: {plan.plan_arc}")
    message_parts.append(f"  First block focus: {plan.first_block_focus}")
    message_parts.append(f"  Sessions per week: {plan.sessions_per_week}")
    message_parts.append(f"  Primary focus: {plan.primary_focus}")

    if insights.strengths:
        message_parts.append("")
        message_parts.append("Strengths:")
        for strength in insights.strengths:
            message_parts.append(f"  - {strength}")

    if insights.gaps:
        message_parts.append("")
        message_parts.append("Gaps to address:")
        for gap in insights.gaps:
            message_parts.append(f"  - {gap}")

    if insights.crossover_note:
        message_parts.append("")
        message_parts.append(f"Crossover note: {insights.crossover_note}")

    if insights.cycle_tracking_note:
        message_parts.append("")
        message_parts.append(f"Cycle tracking: {insights.cycle_tracking_note}")

    return "\n".join(message_parts)


class FirstMessageAgent:
    def __init__(self):
        self._client = get_litellm_client()

    async def generate(
        self, athlete_id: uuid.UUID, brief: FirstMessageCoachingBrief
    ) -> Tuple[str, dict]:
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
                messages=[
                    {"role": "system", "content": prompt_record.system_prompt},
                    {"role": "user", "content": user_message},
                ],
            )

            latency_ms = int((time.monotonic() - start_time) * 1000)

            if response.usage:
                input_tokens = response.usage.prompt_tokens
                output_tokens = response.usage.completion_tokens

            if response.choices:
                stop_reason = response.choices[0].finish_reason
                content = response.choices[0].message.content

            if not content or content.count("\n\n") < 2:
                event = GenerationEvent(
                    athlete_id=athlete_id,
                    outcome=GenerationOutcome.MALFORMED,
                    model=settings.LLM_MODEL,
                    prompt_version=prompt_record.version,
                    brief_version=brief.brief_version,
                    data_tier=brief.twin.data_tier,
                    confidence_level=brief.twin.confidence_level.value,
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    stop_reason=stop_reason,
                    context_budget=brief.budget_snapshot,
                )
                log_generation_event(event)
                raise ValueError("Response malformed: insufficient paragraph breaks")

            metadata = {
                "model": settings.LLM_MODEL,
                "prompt_version": prompt_record.version,
                "brief_version": brief.brief_version,
                "outcome": GenerationOutcome.SUCCESS.value,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "latency_ms": latency_ms,
                "stop_reason": stop_reason,
                "data_tier": brief.twin.data_tier,
                "confidence_level": brief.twin.confidence_level.value,
                "context_budget": brief.budget_snapshot,
            }

            event = GenerationEvent(
                athlete_id=athlete_id,
                outcome=GenerationOutcome.SUCCESS,
                model=settings.LLM_MODEL,
                prompt_version=prompt_record.version,
                brief_version=brief.brief_version,
                data_tier=brief.twin.data_tier,
                confidence_level=brief.twin.confidence_level.value,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                stop_reason=stop_reason,
                context_budget=brief.budget_snapshot,
            )
            log_generation_event(event)

            return content, metadata

        except openai.APITimeoutError as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            event = GenerationEvent(
                athlete_id=athlete_id,
                outcome=GenerationOutcome.TIMEOUT,
                model=settings.LLM_MODEL,
                prompt_version=prompt_record.version,
                brief_version=brief.brief_version,
                data_tier=brief.twin.data_tier,
                confidence_level=brief.twin.confidence_level.value,
                latency_ms=latency_ms,
                error_type="APITimeoutError",
                error_message=str(e),
                context_budget=brief.budget_snapshot,
            )
            log_generation_event(event)
            raise

        except openai.APIStatusError as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            if e.status_code == 429:
                outcome = GenerationOutcome.RATE_LIMITED
            else:
                outcome = GenerationOutcome.PROVIDER_ERROR

            event = GenerationEvent(
                athlete_id=athlete_id,
                outcome=outcome,
                model=settings.LLM_MODEL,
                prompt_version=prompt_record.version,
                brief_version=brief.brief_version,
                data_tier=brief.twin.data_tier,
                confidence_level=brief.twin.confidence_level.value,
                latency_ms=latency_ms,
                error_type="APIStatusError",
                error_message=str(e),
                context_budget=brief.budget_snapshot,
            )
            log_generation_event(event)
            raise

        except Exception as e:
            latency_ms = int((time.monotonic() - start_time) * 1000)
            event = GenerationEvent(
                athlete_id=athlete_id,
                outcome=GenerationOutcome.INTERNAL_ERROR,
                model=settings.LLM_MODEL,
                prompt_version=prompt_record.version,
                brief_version=brief.brief_version,
                data_tier=brief.twin.data_tier,
                confidence_level=brief.twin.confidence_level.value,
                latency_ms=latency_ms,
                error_type=type(e).__name__,
                error_message=str(e),
                context_budget=brief.budget_snapshot,
            )
            log_generation_event(event)
            raise