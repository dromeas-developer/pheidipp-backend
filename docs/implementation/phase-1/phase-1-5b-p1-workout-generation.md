# Implementation Plan: Phase-1.5b — Workout Generation (Updated)
## Plan ID: Phase-1.5b-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.5b
Sub-Phase Title: Workout Generation

## Objective
Enable the athlete to see their workout for the day, generated on-demand from the planned session and current twin state. The `WorkoutGenerationAgent` produces a `GeneratedWorkout` with linked `WorkoutStep` records, each carrying a `physiological_intent`. Targets are calibrated to the athlete's data tier: power for Tier 1-2, GAP for Tier 3-4, description-only for Tier 5-6. Generation is idempotent for `(planned_session_id, date)`. At this phase, `adjusted_targets` equals `theoretical_targets` because wellness and weather modifiers do not yet exist.

## Scope
- `GeneratedWorkoutRepository` — append-only insert and idempotent lookup for `GeneratedWorkout`
- `WorkoutStepRepository` — batch insert of `WorkoutStep` records
- `PlannedSessionRepository` — lookup by ID and today's session for an athlete
- `WorkoutGenerationAgent` service — LLM agent following the `FirstMessageAgent` pattern (constructor DI, no commit, `GenerationEvent` on every call)
- `ContextBudgetService.build_workout_context()` — assemble and budget-enforce context for workout generation (3000 token budget)
- Target type inference — static mapping from `DataTier` to primary target modality
- `SESSION_INTENT_MAP` — static mapping from `SessionType` to `PhysiologicalIntent` for work steps
- Two-column `TargetSet` construction — workout-level theoretical and adjusted targets (identical at this phase)
- API response schemas — `WorkoutStepResponse`, `GeneratedWorkoutResponse`, `TodayResponse`
- `GET /athletes/{id}/today` — returns today's `PlannedSession` + `GeneratedWorkout` + `WorkoutStep[]`
- `POST /athletes/{id}/sessions/{sid}/generate-workout` — explicit generation trigger
- Prompt template — `app/core/prompts/workout_gen_v1.md`
- `workout_generated` event production via `EventPublisher`
- Registration and wiring — repository/service/router exports in `__init__.py` modules

## Out Of Scope
- Recovery modifier computation on `adjusted_targets` — deferred to Phase 3
- Weather modifier computation on `adjusted_targets` — deferred to Phase 3
- Cycle phase adjustment — deferred to Phase 3
- Workout segmentation (`PlannedSegment` / `PhysiologicalSegment`) — deferred to Phase 5
- Objectives annotation on workout — deferred to Phase 4
- Workout library entries — separate subsystem
- Any migration creation — `generated_workouts` and `workout_steps` tables already exist from Phase 1.2c
- Priority-weighted truncation implementation in `ContextBudgetService` — deferred per ADR-001 tracking in Phase 1.5a

## Architecture Contracts
- `01-entities/generated-workout.md` — IMPLEMENTS (repository, service creation, invariants)
- `01-entities/workout-step.md` — IMPLEMENTS (step creation, physiological intent, data-tier targets)
- `01-entities/twin-state.md` — DEPENDS ON (twin state read, threshold estimates, data tier, confidence)
- `01-entities/planned-session.md` — DEPENDS ON (session lookup, intent description, session type)
- `00-foundations/data-tiers.md` — DEPENDS ON (data tier definitions, target type per tier)
- `03-agents/workout-generation-agent.md` — IMPLEMENTS (context contract, output contract, idempotency, failure semantics)
- `03-agents/context-budget-service.md` — IMPLEMENTS (`build_workout_context` method, 3000 token budget)
- `04-platform/event-topology.md` — IMPLEMENTS (transactional outbox pattern for `workout_generated` event)

## Invariants
- `WorkoutStep.physiological_intent` is **never null** — every step has an intent, including warmup and cooldown.
  - `step_type = 'warmup'` → `physiological_intent = 'recovery'`
  - `step_type = 'cooldown'` → `physiological_intent = 'recovery'`
  - `step_type = 'recovery'` (between intervals) → `physiological_intent = 'recovery'`
  - `step_type = 'work'` → `physiological_intent` derived from session's `SessionType` via `SESSION_INTENT_MAP`
- `WorkoutStep.step_order` is unique within a `generated_workout_id`. Enforced by unique constraint on `(generated_workout_id, step_order)`.
- `GeneratedWorkout` is idempotent for `(planned_session_id, date)`. Calling twice returns the existing workout.
- `theoretical_targets` and `adjusted_targets` are always both written, even when identical (GREEN modifier with no weather).
- `pace_sec_per_km` in both target sets uses GAP values only. Never raw pace.
- `twin_state_id` records which twin version drove target generation. If the twin is recalibrated after a workout is generated, the generated workout is not retroactively updated.
- Target type depends on data tier:
  - Tier 1-2: `target_power_watts` primary, `target_gap_sec_per_km` secondary
  - Tier 3-4: `target_gap_sec_per_km` primary, `target_hr_zone` secondary
  - Tier 5-6: `description` only, numeric targets null
- Recovery modifier defaults to `red` only when `WellnessModifierService` produces that classification; defaults to `green`, reason null (modifiers not yet available).
- Numeric targets are null for Tier 5-6 athletes. `description` is always non-null and always carries the intent in plain language.
- Steps are never updated after creation. A regenerated workout creates a new `GeneratedWorkout` with new steps.

## Implementation Steps

1. [OWNER: Coder] Create `GeneratedWorkoutRepository` in `app/repositories/generated_workout_repository.py`. Implement append-only `insert(workout: GeneratedWorkout)` that flushes without committing. Implement `get_by_session_and_date(planned_session_id, generation_date)` for idempotency lookup using the existing `uq_generated_workouts_planned_session_generation_date` unique constraint. Implement `get_by_planned_session(planned_session_id)` for retrieval. Register in `app/repositories/__init__.py`.

2. [OWNER: Coder] Create `WorkoutStepRepository` in `app/repositories/workout_step_repository.py`. Implement batch `insert_many(steps: list[WorkoutStep])` that adds all steps and flushes in one call. Implement `get_by_workout(generated_workout_id)` ordered by `step_order ASC` using the existing `ix_workout_steps_generated_workout_order` index. Register in `app/repositories/__init__.py`.

3. [OWNER: Coder] Create `PlannedSessionRepository` in `app/repositories/planned_session_repository.py`. Implement `get_by_id(session_id)` for direct lookup. Implement `get_today_for_athlete(athlete_id, target_date)` that joins `PlannedSession → WeeklyPlan → TrainingPlan` where `TrainingPlan.status = 'active'`, `PlannedSession.target_date = target_date`, ordered by `session_slot ASC`. This follows the established staleness invariant: queries MUST join through `WeeklyPlan.training_plan_id`. Register in `app/repositories/__init__.py`.

4. [OWNER: Coder] Implement the `SESSION_INTENT_MAP` and `DATA_TIER_TARGET_TYPE` constants in a new module `app/services/workout_target_types.py`. The `SESSION_INTENT_MAP` maps each `SessionType` to its `PhysiologicalIntent` per the architecture spec (`easy_run → low_aerobic`, `threshold → threshold`, `vo2max → vo2max`, etc.). The `DATA_TIER_TARGET_TYPE` maps `DataTier` to target modality string (`1,2 → 'power'`, `3,4 → 'gap'`, `5,6 → 'description'`). Include a `get_step_physiological_intent(step_type, session_type)` helper that returns `PhysiologicalIntent.RECOVERY` for warmup/cooldown/recovery steps and derives from `SESSION_INTENT_MAP` for work steps.

5. [OWNER: Coder] Add `build_workout_context()` to the existing `ContextBudgetService`. The method takes `athlete_id` and `planned_session_id`, fetches the latest `TwinState`, the `PlannedSession`, and the athlete's preferences and profile. It constructs a `WorkoutGenerationContext` dataclass with: session summary (type, phase, week, intent, duration), readiness digest (via `TwinContextAssembler`), data tier, target type (from `DATA_TIER_TARGET_TYPE`), and relevant objectives placeholder (empty list for this phase; objectives not yet available). Enforce the 3000 token budget via `estimate_tokens()`. Log a warning if the budget is exceeded but return the context anyway (matching the existing `build_first_message_context` pattern).

6. [OWNER: Coder] Create `WorkoutGenerationAgent` in `app/services/workout_generation_agent.py`. Follow the `FirstMessageAgent` pattern exactly: constructor receives repositories + `ContextBudgetService` + `PromptRegistry` + `EventPublisher`; does NOT commit the session. The `generate(planned_session_id, athlete_id)` method:
   a. Check idempotency: query `GeneratedWorkoutRepository.get_by_session_and_date(planned_session_id, today)`. If found, return existing without LLM call.
   b. Assemble context via `ContextBudgetService.build_workout_context()`.
   c. Load prompt via `PromptRegistry.load("workout_gen_v1")`.
   d. Call LiteLLM proxy with structured JSON output expectation.
   e. Parse the `WorkoutGenerationOutput` (steps array with step_order, step_type, physiological_intent, target_duration_seconds, target fields, description).
   f. Validate steps: all physiological_intents are non-null, step_orders are sequential starting at 1, exactly one warmup first, exactly one cooldown last.
   g. Construct workout-level `TargetSet` JSONB for `theoretical_targets` and `adjusted_targets` (identical at this phase) from the step targets and the readiness description.
   h. Create `GeneratedWorkout` and `WorkoutStep` records via repositories.
   i. Write `GenerationEvent` (success or failure) via `GenerationEventRepository`.
   j. Publish `workout_generated` event via `EventPublisher` (ADR-004 transactional outbox pattern - event and outbox inserted in same transaction as domain state).
   k. On LLM failure: write `GenerationEvent` with `success=false`, raise `LLMServiceUnavailableError`. No `GeneratedWorkout` created.
   Register in `app/services/__init__.py`.

7. [OWNER: Coder] Create the workout generation prompt template at `app/core/prompts/workout_gen_v1.md`. The prompt must:
   - Receive `WorkoutGenerationContext` as Jinja2 variables.
   - Encode the `SESSION_INTENT_MAP` rules so the agent assigns correct `physiological_intent`.
   - Encode data tier target type rules so the agent populates the correct target fields.
   - Encode the step structure rules (warmup first, cooldown last, recovery between work steps).
   - Specify JSON output schema matching `WorkoutGenerationOutput` from the architecture contract.
   - Include confidence-appropriate language: at LOW confidence, produce wide ranges and effort descriptions; at MEDIUM, threshold-referenced ranges; at HIGH, point estimates.
   - Enforce GAP values only for pace targets (never raw pace).
   - Require `description` on every step, always non-empty.
   - Require `numeric targets = null` for Tier 5-6 steps.

8. [OWNER: Coder] Create API response schemas in `app/schemas/workout.py`. Define `WorkoutStepResponse` (Pydantic model with `from_attributes=True`) mapping all `WorkoutStep` fields. Define `GeneratedWorkoutResponse` with `theoretical_targets`, `adjusted_targets`, `recovery_modifier_level`, `generated_at`, and nested `steps: list[WorkoutStepResponse]`. Define `TodayResponse` with `planned_session: PlannedSessionResponse` and `generated_workout: GeneratedWorkoutResponse | None`. Register in `app/schemas/__init__.py`.

9. [OWNER: Coder] Create `GET /athletes/{athlete_id}/today` endpoint. Add to a new `app/api/v1/workout.py` router module (or extend an existing router if more appropriate; follow the `coach_router` / `plan_router` pattern). The endpoint:
   a. Requires `require_self` auth.
   b. Resolves the athlete's active plan and today's `PlannedSession` via `PlannedSessionRepository.get_today_for_athlete()`.
   c. If no session today → **404 Not Found** (more appropriate than 200 with null values).
   d. Queries `GeneratedWorkoutRepository.get_by_session_and_date()` for existing workout.
   e. If exists → return 200 with the existing workout.
   f. If not exists → trigger `WorkoutGenerationAgent.generate()` inline, commit, and return 200-level content with the new workout.
   g. Response model: `TodayResponse`.

10. [OWNER: Coder] Create `POST /athletes/{athlete_id}/sessions/{session_id}/generate-workout` endpoint in the same router module. The endpoint:
    a. Requires `require_self` auth.
    b. Validates the `PlannedSession` belongs to the athlete's active plan (join through WeeklyPlan → TrainingPlan).
    c. Calls `WorkoutGenerationAgent.generate(session_id, athlete_id)`.
    d. Commits the transaction.
    e. Returns 201 if newly generated, 409 if existing workout was returned (idempotent conflict).
    f. On `LLMServiceUnavailableError` → **502 Bad Gateway** (intentional distinction from FirstMessageAgent's 503 to communicate "bad gateway upstream" vs "service unavailable").
    g. Response model: `GeneratedWorkoutResponse`.

11. [OWNER: Coder] Create `workout_router` and register it in `app/api/v1/__init__.py`. Add the `build_workout_generation_agent()` dependency factory following the `build_first_message_agent()` pattern — instantiate all required repositories, `ContextBudgetService`, `PromptRegistry`, and `EventPublisher`.

12. [OWNER: Test Architect] Create test manifest `tests/test-manifest/phase-1-5b.yaml` and test files:
    - `tests/unit/test_generated_workout_repository.py` — test idempotent lookup returns existing, insert flushes without commit.
    - `tests/unit/test_workout_step_repository.py` — test batch insert, ordered retrieval.
    - `tests/unit/test_planned_session_repository.py` — test today lookup, staleness join.
    - `tests/unit/test_workout_target_types.py` — test SESSION_INTENT_MAP completeness, DATA_TIER_TARGET_TYPE mapping, get_step_physiological_intent helper.
    - `tests/unit/test_workout_generation_agent.py` — test idempotency (existing workout returns without LLM call), test context assembly, test LLM failure writes GenerationEvent with success=false, test step validation catches invalid physiological_intent.
    - `tests/integration/test_workout_endpoints.py` — test GET /today returns workout, test POST /generate-workout creates workout, test 403 on cross-athlete access, test 502 on LLM failure, test idempotency (second POST returns 409 with same workout).

13. [OWNER: DevOps] Review any migration dependencies. Verify that the existing `generated_workouts` and `workout_steps` tables from Phase 1.2c migration are present and correct. No new migration is expected for this plan. Run `db-upgrade-test.sh` to confirm.

## Event Contracts

### Produced

| Event | Producer | Payload Fields | Ordering |
|---|---|---|---|
| `workout_generated` | `WorkoutGenerationAgent` | `generated_workout_id`, `planned_session_id`, `session_type`, `step_count` | GeneratedWorkout and WorkoutStep rows must be flushed before event insertion. Event/outbox rows are inserted in the same transaction per ADR-004. Publication occurs only after the transaction commits successfully. |

### Consumed

None. `WorkoutGenerationAgent` is the first producer in the workout lifecycle. Downstream consumers (home screen refresh, weather prefetch cancellation) subscribe to this event but are not implemented in this phase.

## Pseudocode

```
# GET /today flow:
  resolve active TrainingPlan for athlete
  find PlannedSession where target_date = today AND plan = active
  if no session → return 404 Not Found
  
  existing = GeneratedWorkoutRepository.get_by_session_and_date(session_id, today)
  if existing → return {planned_session, generated_workout: existing}
  
  result = WorkoutGenerationAgent.generate(session_id, athlete_id)
  commit()
  return {planned_session, generated_workout: result}

# POST /generate-workout flow:
  validate PlannedSession exists and belongs to athlete's active plan
  result = WorkoutGenerationAgent.generate(session_id, athlete_id)
  commit()
  return result  # 201 if new, 409 if existing (conflict)

# WorkoutGenerationAgent.generate(session_id, athlete_id):
  existing = get_by_session_and_date(session_id, today)
  if existing → return existing  # idempotency gate (for GET endpoint only)

  context = ContextBudgetService.build_workout_context(athlete_id, session_id)
  prompt = PromptRegistry.load("workout_gen_v1").render(context)
  
  try:
    response = await llm_client.chat.completions.create(
      model=proxy_model,
      messages=[system_prompt, user_prompt_with_context],
      response_format={"type": "json_object"}
    )
  except (APIConnectionError, APITimeoutError, APIStatusError):
    GenerationEventRepository.insert(success=false, failure_reason=...)
    raise LLMServiceUnavailableError

  parsed = parse_workout_output(response.content)
  validate_steps(parsed.steps)  # sequential orders, non-null intents, structure rules

  twin_state = TwinStateRepository.get_latest(athlete_id)
  
  workout_target_set = build_target_set(parsed.steps, twin_state.data_tier)
  
  workout = GeneratedWorkout(
    planned_session_id=session_id,
    twin_state_id=twin_state.id,
    theoretical_targets=workout_target_set,
    adjusted_targets=workout_target_set,  # identical at this phase
    recovery_modifier_level=RecoveryModifierLevel.GREEN,
    recovery_modifier_reason=None,
    generation_date=today
  )
  GeneratedWorkoutRepository.insert(workout)

  steps = []
  for step_data in parsed.steps:
    step = WorkoutStep(
      generated_workout_id=workout.id,
      step_order=step_data.step_order,
      step_type=step_data.step_type,
      session_type=session.session_type,
      physiological_intent=step_data.physiological_intent,
      target=build_step_target(step_data),
      duration_seconds=step_data.target_duration_seconds,
      description=step_data.description
    )
    steps.append(step)
  WorkoutStepRepository.insert_many(steps)

  GenerationEventRepository.insert(success=true, token_counts=...)

  EventPublisher.publish(
    event_type="workout_generated",
    payload={
      generated_workout_id=workout.id,
      planned_session_id=session_id,
      session_type=session.session_type,
      step_count=len(steps)
    }
  )

  return workout
```

## Testing Requirements

1. **Idempotency verification**: Calling `POST /sessions/{sid}/generate-workout` twice for the same `(planned_session_id, date)` returns HTTP 409 on the second call with the existing `GeneratedWorkout` ID. The `GenerationEvent` count increases only on the first call (second call skips the LLM entirely).

2. **Step structure validation**: A threshold session (`session_type = 'threshold'`) produces `WorkoutStep` records with: exactly one `warmup` step (order 1, intent `recovery`), N work steps (intent `threshold`), N-1 recovery steps between them (intent `recovery`), and exactly one `cooldown` step (last, intent `recovery`). Every step has a non-null `physiological_intent`.

3. **Data tier target type**: For a Tier 1 athlete, `WorkoutStep.target` contains non-null `target_power_watts` in the `primary` range. For a Tier 3 athlete, `target_gap_sec_per_km` is populated. For a Tier 5 athlete, all numeric target fields are null and `description` carries the full coaching intent.

4. **Two-column targets always written**: Every `GeneratedWorkout` has both `theoretical_targets` and `adjusted_targets` as non-null JSONB objects. At this phase, their content is identical.

5. **Twin state linkage**: `GeneratedWorkout.twin_state_id` references the latest `TwinState` at the time of generation. If the twin were to recalibrate after generation (not possible in Phase 1 but testable by inserting a newer TwinState), the generated workout's `twin_state_id` would remain unchanged.

6. **GAP-only pace**: No `target` or `TargetSet` field contains raw pace values. All pace fields use GAP (grade-adjusted pace) semantics. Verified by prompt inspection and output validation.

7. **LLM failure handling**: When the LiteLLM proxy returns an error, `GenerationEvent` is written with `success=false` and `failure_reason` populated. No `GeneratedWorkout` or `WorkoutStep` records are created. The API returns 502.

8. **GET /today behavior**: Returns 404 when no session exists for today. Returns the existing workout when one was previously generated. Triggers generation and returns a new workout when a session exists but no workout has been generated yet.

9. **Cross-athlete access denied**: JWT for athlete A attempting to access athlete B's workout returns 403.

10. **Event production**: After successful generation, a `workout_generated` `SystemEvent` and corresponding `SystemEventOutbox` row exist in the database within the same transaction as the `GeneratedWorkout`. Both are published only after the transaction commits successfully.

## Coder Handoff Notes

### Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11  [OWNER: Coder]
Skip:     Step 12 (Test Architect — tests),
          Step 13 (DevOps — migration review and application)

### Known Risks

- **LLM JSON reliability**: The agent expects structured JSON output from the LLM. Implement robust parsing with a fallback error path: if the JSON is malformed or missing required fields, write `GenerationEvent` with `success=false` and raise `LLMServiceUnavailableError`. Do NOT attempt to "fix" broken LLM output — treat it as a generation failure so the audit trail is clean.

- **Step validation must run before DB writes**: Validate all step orders, physiological_intents, and structural rules (warmup first, cooldown last) BEFORE inserting any records. A partial insert followed by validation failure would leave orphan data. Build all domain objects in memory, validate, then insert.

- **Transaction ownership follows FirstMessageAgent pattern**: The `WorkoutGenerationAgent` does NOT commit the session. All repository writes (GeneratedWorkout, WorkoutSteps, GenerationEvent, SystemEvent, Outbox) are flushed inside the same transaction. The API route handler calls `session.commit()` after the agent returns. This is Pattern B from the FirstMessageAgent and must be preserved.

### Architecture Interpretation Notes

- **`adjusted_targets = theoretical_targets` at this phase**: No wellness or weather modifiers exist. The `build_target_set()` function produces a single `TargetSet` that is assigned to both fields. This is correct per the architecture — both fields are always written. When Phase 3 adds modifiers, only `adjusted_targets` changes.

- **Objectives placeholder is empty**: The architecture contract references `relevant_objectives` in the context, but objectives are not delivered until Phase 4. Pass an empty list. The prompt should not reference objectives at this phase, or should handle the empty case gracefully.

- **Priority-weighted truncation is deferred**: `ContextBudgetService.build_workout_context()` should match the existing `build_first_message_context()` pattern — log a warning if the token budget is exceeded but return the full context. The TODO in that file (DEF-001) defers actual truncation implementation.

- **GAP enforcement is prompt-level**: The architecture invariant "pace_sec_per_km uses GAP values only" is enforced by the prompt template, not by application-level validation at insert time. The `WorkoutTarget` JSONB shape does not distinguish GAP from raw pace — trust in the prompt engineering and validate through integration tests.

- **Recovery modifier defaults**: `recovery_modifier_level = RecoveryModifierLevel.GREEN`, `recovery_modifier_reason = None`. These are set directly in the service, not via any modifier service. The `server_default` on the model also covers this but the service should be explicit.

- **Event publishing pattern is correct**: The `EventPublisher.publish()` method inserts both `SystemEvent` and `SystemEventOutbox` rows in the same database transaction as the domain state changes. This follows ADR-004 exactly. External publication occurs only after the transaction commits successfully, preventing phantom state visibility.

- **HTTP status codes are intentional**: 
  - GET /today returns 404 (not 200 with null) when no session exists - this is more RESTful and appropriate
  - POST /generate-workout returns 502 (not 503) on LLM failure - this distinguishes workout-generation LLM outages from general service unavailability, allowing different retry behaviors

### Suggested Order

1. Start with Step 4 (constants) and Step 1-3 (repositories) — these have no dependencies and are pure data access.
2. Step 5 (context budget integration) comes next — it depends on TwinContextAssembler which already exists.
3. Step 7 (prompt template) can be written in parallel with Step 6 (agent) — the prompt is a static markdown file.
4. Step 6 (agent) depends on Steps 1-5 and 7 — it is the core orchestration logic.
5. Steps 8-11 (API layer) come last — they wire everything together.
6. Verify against testing requirements before handing off to Test Architect.