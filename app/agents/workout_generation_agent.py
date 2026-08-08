"""Generate day-of workout for a PlannedSession."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from typing import Any, List, Optional, cast

from sqlalchemy.ext.asyncio import AsyncSession

from openai import (
    AsyncOpenAI,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
)
from openai.types.chat import (
    ChatCompletionMessageParam,
    ChatCompletionSystemMessageParam,
    ChatCompletionUserMessageParam,
)

from app.config import settings
from app.core.logging_utils import log_event
from app.core.prompt_registry import PromptNotFoundError, PromptRegistry
from app.models.enums import (
    PhysiologicalIntent,
    SessionType,
    StepType,
)
from app.models.generated_workout import GeneratedWorkout
from app.models.generation_event import GenerationEvent
from app.models.planned_session import PlannedSession
from app.models.workout_step import WorkoutStep
from app.repositories.generated_workout_repository import (
    GeneratedWorkoutRepository,
)
from app.repositories.generation_event_repository import (
    GenerationEventRepository,
)
from app.repositories.planned_session_repository import (
    PlannedSessionRepository,
)
from app.repositories.twin_state_repository import TwinStateRepository
from app.repositories.workout_step_repository import WorkoutStepRepository
from app.services.context_budget_service import (
    ContextBudgetService,
    WorkoutGenerationContext,
)
from app.services.event_publisher import EventPublisher
from app.services.workout_generation_errors import (
    LLMServiceUnavailableError,
    PlannedSessionNotFoundError,
    WorkoutAlreadyGeneratedError,
    WorkoutGenerationContractError,
)
from app.services.workout_target_types import (
    get_step_physiological_intent,
)

# ---------------------------------------------------------------------------
# Internal helpers — pure functions kept module-level so unit tests can
# import them without instantiating the agent.
# ---------------------------------------------------------------------------


#: Numeric signal types the LLM is allowed to populate. HR is excluded
#: at this phase per the architecture contract — the workout agent
#: emits power / gap / description targets only.
_NON_NULL_NUMERIC_FIELDS_BY_TARGET_TYPE: dict[str, set[str]] = {
    "power": {"target_power_watts"},
    "gap": {"target_gap_sec_per_km"},
    "description": set(),
}


def _coerce_int(value: Any) -> Optional[int]:
    """Coerce an LLM-emitted value to ``Optional[int]`` for ``step_order`` /
    ``target_duration_seconds``.

    ``None`` and ``""`` map to ``None`` so the validator can compare
    against absent fields. Floats are truncated via ``int`` (the LLM
    occasionally emits ``900.0`` for an integer second count).
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return int(float(s))
        except ValueError:
            return None
    return None


def _coerce_optional_int(value: Any) -> Optional[int]:
    """Coerce a target value to ``Optional[int]``.

    Same semantics as :func:`_coerce_int` but kept separate so the
    intent at the call site is unambiguous.
    """
    return _coerce_int(value)


def _coerce_int_range(value: Any) -> dict[str, Optional[int]]:
    """Coerce a range-shaped LLM value into ``{"min": int|None, "max": int|None}``.

    Accepts either a flat numeric (treated as ``max``, ``min`` null —
    not used in v1 prompt output but kept for forward-compat) or a
    dict with ``min``/``max`` keys. ``None`` when the LLM emits
    ``null`` or an unparseable value; the validator then enforces
    that numeric targets may be null per ``target_type``.
    """
    if value is None:
        return {"min": None, "max": None}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Single-value range — treat as max, min null. The prompt
        # instructs range emission; this branch exists for legacy
        # outputs that emit a point estimate.
        return {"min": None, "max": _coerce_int(value)}
    if isinstance(value, dict):
        d: dict[str, Any] = cast(dict[str, Any], value)
        return {
            "min": _coerce_int(d.get("min")),
            "max": _coerce_int(d.get("max")),
        }
    return {"min": None, "max": None}


# ---------------------------------------------------------------------------
# WorkoutGenerationAgent.
# ---------------------------------------------------------------------------


class WorkoutGenerationAgent:
    """Generate a day-of workout for an athlete's PlannedSession.

    Idempotent by design: :meth:`generate` checks for an existing
    ``GeneratedWorkout`` row for ``(planned_session_id, generation_date)``
    before invoking the LLM. The behaviour depends on ``allow_existing``:

    * ``True`` (default — used by ``GET /athletes/{id}/today``) —
      existing workouts are returned without re-invoking the LLM.
    * ``False`` (used by ``POST /athletes/{id}/sessions/{sid}/generate-workout``) —
      existing workouts raise :class:`WorkoutAlreadyGeneratedError` so
      the API can surface HTTP 409.

    Transaction ownership: the agent does NOT commit the session. All
    writes are flushed inside the caller's transaction; the route
    handler owns the commit boundary.
    """

    PROMPT_VERSION = "v1"
    AGENT_NAME = "WorkoutGenerationAgent"

    def __init__(
        self,
        session: AsyncSession,
        generated_workouts: GeneratedWorkoutRepository,
        workout_steps: WorkoutStepRepository,
        generation_events: GenerationEventRepository,
        planned_sessions: PlannedSessionRepository,
        twin_states: TwinStateRepository,
        context_budget: ContextBudgetService,
        prompt_registry: PromptRegistry,
        events: Optional[EventPublisher] = None,
    ) -> None:
        self._session = session
        self._generated_workouts = generated_workouts
        self._workout_steps = workout_steps
        self._generation_events = generation_events
        self._planned_sessions = planned_sessions
        self._twin_states = twin_states
        self._context_budget = context_budget
        self._prompt_registry = prompt_registry
        if events is None:
            from app.repositories.system_event_outbox_repository import (
                SystemEventOutboxRepository,
            )
            from app.repositories.system_event_repository import (
                SystemEventRepository,
            )

            self._events = EventPublisher(
                SystemEventRepository(session),
                SystemEventOutboxRepository(session),
            )
        else:
            self._events = events

    # ------------------------------------------------------------------
    # Public API.
    # ------------------------------------------------------------------

    async def generate(
        self,
        athlete_id: uuid.UUID,
        planned_session_id: uuid.UUID,
        generation_date: date,
        *,
        allow_existing: bool = True,
    ) -> GeneratedWorkout:
        """Generate (or return) the day-of workout.

        Parameters
        ----------
        athlete_id:
            Path athlete — used for TwinState lookup and FK writes.
        planned_session_id:
            Target ``PlannedSession`` id.
        generation_date:
            ``generation_date`` value stored on the workout row; typically
            ``date.today()`` for on-demand generation.
        allow_existing:
            ``True`` — return the existing workout if one is present for
            ``(planned_session_id, generation_date)`` without calling
            the LLM. ``False`` — raise :class:`WorkoutAlreadyGeneratedError`
            when a workout already exists for that key.

        Returns
        -------
        GeneratedWorkout
            The freshly created (or returned) workout. ``WorkoutStep[]``
            are loaded via :meth:`_load_steps` for the API response.

        Raises
        ------
        PlannedSessionNotFoundError
            ``planned_session_id`` does not exist.
        LLMServiceUnavailableError
            LLM call failed (proxy unavailable, timeout, status error,
            contract violation, or missing prompt file).
        WorkoutAlreadyGeneratedError
            ``allow_existing=False`` and a workout already exists for
            the idempotency key.
        """
        # -----------------------------------------------------------------
        # Idempotency gate — short-circuit on existing workout.
        # -----------------------------------------------------------------
        existing = await self._generated_workouts.get_by_session_and_date(
            planned_session_id=planned_session_id,
            generation_date=generation_date,
        )
        if existing is not None:
            if not allow_existing:
                raise WorkoutAlreadyGeneratedError(existing_workout_id=existing.id)
            return existing

        # -----------------------------------------------------------------
        # Pre-condition: TwinState exists. Without it the readiness
        # digest is empty and the prompt receives no threshold anchor.
        # -----------------------------------------------------------------
        twin_state = await self._twin_states.get_latest(athlete_id)
        if twin_state is None:
            raise LLMServiceUnavailableError(
                "twin state not available; athlete must complete onboarding "
                "before workout generation"
            )

        # -----------------------------------------------------------------
        # Pre-condition: PlannedSession exists.
        # -----------------------------------------------------------------
        planned_session = await self._planned_sessions.get_by_id(planned_session_id)
        if planned_session is None:
            raise PlannedSessionNotFoundError(planned_session_id=planned_session_id)

        # -----------------------------------------------------------------
        # Assemble context (token-budget enforced).
        # -----------------------------------------------------------------
        context = await self._context_budget.build_workout_context(
            athlete_id=athlete_id,
            planned_session_id=planned_session_id,
        )
        context_dict = context.to_dict()

        # -----------------------------------------------------------------
        # Load prompt.
        # -----------------------------------------------------------------
        prompt_version = self.PROMPT_VERSION
        try:
            prompt = self._prompt_registry.get_prompt("workout_gen", prompt_version)
        except PromptNotFoundError as exc:
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=self._context_budget.estimate_tokens(
                    {"messages": [{"role": "user", "content": ""}]}
                ),
                latency_ms=0,
                failure_reason="prompt_not_found",
            )
            raise LLMServiceUnavailableError(
                "workout generation prompt not deployed"
            ) from exc

        # -----------------------------------------------------------------
        # Call LLM via proxy.
        # -----------------------------------------------------------------
        llm_client = self._build_llm_client()
        start_time = datetime.now(timezone.utc)

        messages: list[ChatCompletionMessageParam] = [
            ChatCompletionSystemMessageParam(role="system", content=prompt),
            ChatCompletionUserMessageParam(
                role="user", content=json.dumps(context_dict)
            ),
        ]

        input_tokens = self._context_budget.estimate_tokens({"messages": messages})

        try:
            response = await llm_client.chat.completions.create(
                model=settings.LLM_MODEL or "cohere/command-a-plus",
                messages=messages,
                max_tokens=1500,
            )
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )

            usage = response.usage
            if usage:
                output_tokens = usage.total_tokens or 0
            else:
                output_tokens = self._context_budget.estimate_tokens(
                    {"content": response.choices[0].message.content or ""}
                )

            generated_content = response.choices[0].message.content or ""

            # Validate + parse the LLM output into step records.
            parsed_steps = self._parse_and_validate_output(
                generated_content=generated_content,
                planned_session=planned_session,
                context=context,
            )

            # Build the TargetSet payloads (theoretical == adjusted at
            # this phase). Both columns always written.
            target_set = self._build_target_set(parsed_steps)

            # -----------------------------------------------------------------
            # Persist GeneratedWorkout + WorkoutStep[] in one transaction.
            # -----------------------------------------------------------------
            generated_workout = GeneratedWorkout(
                planned_session_id=planned_session_id,
                twin_state_id=twin_state.id,
                theoretical_targets=target_set,
                adjusted_targets=target_set,
                recovery_modifier_level=twin_state.readiness_level,
                recovery_modifier_reason=None,
                generation_date=generation_date,
            )
            await self._generated_workouts.insert(generated_workout)

            step_records = [
                WorkoutStep(
                    generated_workout_id=generated_workout.id,
                    step_order=parsed["step_order"],
                    step_type=parsed["step_type"],
                    session_type=planned_session.session_type,
                    physiological_intent=parsed["physiological_intent"],
                    session_purpose=parsed["session_purpose"],
                    target=parsed["target"],
                    duration_seconds=parsed["target_duration_seconds"],
                    description=parsed["description"],
                )
                for parsed in parsed_steps
            ]
            await self._workout_steps.insert_many(step_records)

            # -----------------------------------------------------------------
            # GenerationEvent (success) + workout_generated SystemEvent.
            # -----------------------------------------------------------------
            generation_event = GenerationEvent(
                athlete_id=athlete_id,
                agent_name=self.AGENT_NAME,
                prompt_version=prompt_version,
                trigger_context="manual_api_call",
                input_token_count=input_tokens,
                output_token_count=output_tokens,
                latency_ms=latency_ms,
                success=True,
                failure_reason=None,
            )
            await self._generation_events.insert(generation_event)

            await self._events.publish(
                event_type="workout_generated",
                athlete_id=athlete_id,
                payload={
                    "generated_workout_id": str(generated_workout.id),
                    "planned_session_id": str(planned_session_id),
                    "recovery_modifier_level": (
                        generated_workout.recovery_modifier_level.value
                    ),
                    "generation_event_id": str(generation_event.id),
                    "prompt_version": prompt_version,
                },
            )

            log_event(
                event="workout.generated",
                athlete_id=str(athlete_id),
                planned_session_id=str(planned_session_id),
                generated_workout_id=str(generated_workout.id),
                recovery_modifier_level=(
                    generated_workout.recovery_modifier_level.value
                ),
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                outcome="success",
            )

            return generated_workout

        except WorkoutGenerationContractError:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason="invalid_output_format",
            )
            raise LLMServiceUnavailableError(
                "workout generation response format invalid"
            )

        except (APITimeoutError, APIConnectionError) as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            failure_reason = (
                "timeout" if isinstance(exc, APITimeoutError) else "proxy_unavailable"
            )
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason=failure_reason,
            )
            raise LLMServiceUnavailableError(
                f"LLM call failed: {failure_reason}"
            ) from exc

        except APIStatusError as exc:
            latency_ms = int(
                (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            )
            failure_reason = "rate_limit" if exc.status_code == 429 else "api_error"
            await self._write_generation_event_failure(
                athlete_id=athlete_id,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                latency_ms=latency_ms,
                failure_reason=failure_reason,
            )
            raise LLMServiceUnavailableError(
                f"LLM API error: {exc.message or 'unknown'}"
            ) from exc

    # ------------------------------------------------------------------
    # Public helpers used by the API layer.
    # ------------------------------------------------------------------

    async def load_steps(self, generated_workout_id: uuid.UUID) -> List[WorkoutStep]:
        """Return the ordered ``WorkoutStep[]`` for a generated workout.

        Convenience wrapper around
        :meth:`WorkoutStepRepository.get_by_workout` so the API layer
        can avoid a second repository dependency.
        """
        return await self._workout_steps.get_by_workout(generated_workout_id)

    # ------------------------------------------------------------------
    # Internals.
    # ------------------------------------------------------------------

    def _build_llm_client(self) -> AsyncOpenAI:
        """Build the OpenAI-compatible client for LiteLLM proxy."""
        return AsyncOpenAI(
            base_url=settings.LITELLM_BASE_URL,
            api_key=settings.LITELLM_API_KEY,
        )

    def _parse_and_validate_output(
        self,
        *,
        generated_content: str,
        planned_session: PlannedSession,
        context: WorkoutGenerationContext,
    ) -> List[dict[str, Any]]:
        """Parse LLM JSON output into per-step records and validate structure.

        Returns a list of dicts in execution order ready to be turned
        into ``WorkoutStep`` rows. Raises
        :class:`WorkoutGenerationContractError` on any structural
        violation so the caller can map to ``GenerationEvent(success=False)``
        + ``LLMServiceUnavailableError``.

        Validation enforces:

        * Output is JSON with a top-level ``steps`` array.
        * Steps are strictly sequential from ``step_order = 1``.
        * First step is ``warmup``; last step is ``cooldown``.
        * Every step has a non-null ``physiological_intent``.
        * ``work`` steps' intent matches ``SESSION_INTENT_MAP[session_type]``.
        * Numeric discipline per ``target_type``: only the
          ``target_type``-specific field may be populated; all other
          numeric fields must be null.
        * ``description`` is non-empty for every step.
        """
        raw = generated_content.strip()
        if not raw:
            raise WorkoutGenerationContractError("LLM returned empty output")

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise WorkoutGenerationContractError(
                f"LLM output is not valid JSON: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise WorkoutGenerationContractError(
                "LLM output top-level must be a JSON object"
            )

        payload_dict: dict[str, Any] = cast(dict[str, Any], payload)
        steps_raw = payload_dict.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            raise WorkoutGenerationContractError(
                "LLM output must include a non-empty 'steps' array"
            )

        steps_list: list[dict[str, Any]] = cast(list[dict[str, Any]], steps_raw)

        target_type = (context.target_type or "description").lower()
        allowed_numeric_fields = _NON_NULL_NUMERIC_FIELDS_BY_TARGET_TYPE.get(
            target_type,
            set(),
        )
        session_type: SessionType = planned_session.session_type

        parsed: List[dict[str, Any]] = []
        expected_order = 1
        for index, step_raw in enumerate(steps_list):
            step_order = _coerce_int(step_raw.get("step_order"))
            if step_order != expected_order:
                raise WorkoutGenerationContractError(
                    f"step at index {index} has step_order="
                    f"{step_order!r}, expected {expected_order}"
                )

            step_type_value = step_raw.get("step_type")
            try:
                step_type = StepType(step_type_value)
            except ValueError as exc:
                raise WorkoutGenerationContractError(
                    f"step {step_order} has invalid step_type={step_type_value!r}"
                ) from exc

            intent_value = step_raw.get("physiological_intent")
            if intent_value is None:
                raise WorkoutGenerationContractError(
                    f"step {step_order} has null physiological_intent"
                )
            try:
                physiological_intent = PhysiologicalIntent(intent_value)
            except ValueError as exc:
                raise WorkoutGenerationContractError(
                    f"step {step_order} has invalid physiological_intent="
                    f"{intent_value!r}"
                ) from exc

            # Validate intent derivation rule:
            # warmup / cooldown / recovery -> 'recovery'
            # work -> matches SESSION_INTENT_MAP[session_type]
            expected_intent = get_step_physiological_intent(
                step_type=step_type, session_type=session_type
            )
            if physiological_intent != expected_intent:
                raise WorkoutGenerationContractError(
                    f"step {step_order} physiological_intent="
                    f"{physiological_intent.value!r} contradicts "
                    f"step_type={step_type.value!r} and "
                    f"session_type={session_type.value!r} "
                    f"(expected {expected_intent.value!r})"
                )

            duration_seconds = _coerce_optional_int(
                step_raw.get("target_duration_seconds")
            )
            target_hr_zone = _coerce_optional_int(step_raw.get("target_hr_zone"))
            target_power_watts = step_raw.get("target_power_watts")
            target_gap_sec_per_km = step_raw.get("target_gap_sec_per_km")
            description = step_raw.get("description")

            if step_order is None:
                raise WorkoutGenerationContractError(
                    f"step at index {index} has null step_order"
                )

            if not isinstance(description, str) or not description.strip():
                raise WorkoutGenerationContractError(
                    f"step {step_order} description must be a non-empty string"
                )
            description = description.strip()

            # target_type-driven numeric discipline: only the
            # target_type's field may be populated.
            actual_numeric_fields = {
                "target_power_watts": target_power_watts,
                "target_gap_sec_per_km": target_gap_sec_per_km,
                "target_hr_zone": target_hr_zone,
            }
            for field_name, value in actual_numeric_fields.items():
                if value is not None and field_name not in allowed_numeric_fields:
                    raise WorkoutGenerationContractError(
                        f"step {step_order} populated {field_name} "
                        f"but target_type={target_type!r} forbids it"
                    )
                if (
                    value is None
                    and field_name in allowed_numeric_fields
                    and step_type == StepType.WORK
                    and target_type in {"power", "gap"}
                ):
                    raise WorkoutGenerationContractError(
                        f"step {step_order} target_type="
                        f"{target_type!r} requires "
                        f"{field_name} but LLM emitted null"
                    )

            # Normalize the kept numeric field into the WorkoutTarget
            # shape used in ``WorkoutStep.target``.
            target_payload = self._build_step_target(
                step_type=step_type,
                step_order=step_order,
                target_type=target_type,
                target_power_watts=target_power_watts,
                target_gap_sec_per_km=target_gap_sec_per_km,
                target_hr_zone=target_hr_zone,
                description=description,
            )

            parsed.append(
                {
                    "step_order": step_order,
                    "step_type": step_type,
                    "physiological_intent": physiological_intent,
                    "session_purpose": (
                        # Phase 1.5b default — ``calibration`` for
                        # test sessions, ``general`` otherwise.
                        "calibration"
                        if session_type == SessionType.TEST_SESSION
                        else "general"
                    ),
                    "target": target_payload,
                    "target_duration_seconds": duration_seconds,
                    "description": description,
                }
            )
            expected_order += 1

        # First-step = warmup invariant.
        if parsed[0]["step_type"] != StepType.WARMUP:
            raise WorkoutGenerationContractError(
                f"first step must be warmup, got {parsed[0]['step_type'].value!r}"
            )

        # Last-step = cooldown invariant.
        if parsed[-1]["step_type"] != StepType.COOLDOWN:
            raise WorkoutGenerationContractError(
                f"last step must be cooldown, got {parsed[-1]['step_type'].value!r}"
            )

        return parsed

    def _build_step_target(
        self,
        *,
        step_type: StepType,
        step_order: int,
        target_type: str,
        target_power_watts: Any,
        target_gap_sec_per_km: Any,
        target_hr_zone: Any,
        description: str,
    ) -> dict[str, Any]:
        """Build the ``WorkoutTarget`` JSONB payload for one step.

        The shape mirrors ``docs/architecture/01-entities/workout-step.md``:

        * ``signal_type`` — closed union ``power | gap | hr | description``.
        * ``primary`` — ``{min, max, unit}`` for numeric targets; ``null``
          for ``description`` signal_type.
        * ``fallback`` — ``null`` at this phase; populated in Phase 1.6
          when ``ExecutionAnalysisService`` projects an alternative
          signal channel from raw sensor data.
        * ``description`` — plain English; non-empty.
        """
        description_text = (
            description.strip() if description.strip() else f"{step_type.value} step"
        )

        if target_type == "power":
            primary = _coerce_int_range(target_power_watts)
            unit = "watts"
            return {
                "signal_type": "power",
                "primary": {
                    "min": primary["min"],
                    "max": primary["max"],
                    "unit": unit,
                },
                "fallback": None,
                "description": description_text,
            }
        if target_type == "gap":
            # ``target_gap_sec_per_km`` MUST be GAP, never raw pace.
            # The prompt enforces this; we do not re-check here
            # because we cannot distinguish raw pace from GAP after
            # the fact. The contract error path catches format
            # problems earlier in the prompt; numeric range below
            # preserves whatever the LLM emitted.
            primary = _coerce_int_range(target_gap_sec_per_km)
            return {
                "signal_type": "gap",
                "primary": {
                    "min": primary["min"],
                    "max": primary["max"],
                    "unit": "sec_per_km",
                },
                "fallback": None,
                "description": description_text,
            }
        # description-only signal.
        return {
            "signal_type": "description",
            "primary": None,
            "fallback": None,
            "description": description_text,
        }

    def _build_target_set(self, parsed_steps: List[dict[str, Any]]) -> dict[str, Any]:
        """Build the ``TargetSet`` JSONB shape for ``theoretical_targets``
        and ``adjusted_targets``.

        Phase 1.5b simplification: this aggregates every step's
        ``WorkoutTarget`` into a single ``targets`` array and emits a
        plain-English description that summarises the session intent.
        ``adjusted_targets`` is byte-equal to ``theoretical_targets``
        — no modifier services are wired up yet. When
        ``WellnessModifierService`` / ``WeatherAdjustmentService`` land
        (Phase 1.6 / later), ``adjusted_targets`` will be recomputed by
        scaling ``primary.min/max`` per the modifier chain; this
        function will accept an optional ``adjusted_steps`` parameter
        at that point.
        """
        targets = [step["target"] for step in parsed_steps]
        step_count = len(parsed_steps)
        work_steps = [s for s in parsed_steps if s["step_type"] == StepType.WORK]
        work_count = len(work_steps)
        summary = (
            f"{step_count} steps total"
            + (
                f", {work_count} work segment{'s' if work_count != 1 else ''}"
                if work_count
                else ""
            )
            + "."
        )
        return {
            "targets": targets,
            "description": summary,
        }

    async def _write_generation_event_failure(
        self,
        *,
        athlete_id: uuid.UUID,
        prompt_version: str,
        input_tokens: int,
        latency_ms: int,
        failure_reason: str,
    ) -> None:
        """Write a ``GenerationEvent`` with ``success=False`` for any
        LLM failure path.

        Mirrors :meth:`FirstMessageAgent._write_generation_event_failure`
        so audit logs read consistently across agents.
        """
        generation_event = GenerationEvent(
            athlete_id=athlete_id,
            agent_name=self.AGENT_NAME,
            prompt_version=prompt_version,
            trigger_context="manual_api_call",
            input_token_count=input_tokens,
            output_token_count=0,
            latency_ms=latency_ms,
            success=False,
            failure_reason=failure_reason,
        )
        await self._generation_events.insert(generation_event)
        log_event(
            event="workout.generation.failed",
            athlete_id=str(athlete_id),
            prompt_version=prompt_version,
            failure_reason=failure_reason,
            outcome="failed",
        )


__all__ = ["WorkoutGenerationAgent"]
