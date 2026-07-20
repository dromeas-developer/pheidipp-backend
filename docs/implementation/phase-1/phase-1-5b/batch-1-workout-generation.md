> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-5b-p1-workout-generation.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-5b, verified against the current codebase on 2026-07-19.

## Batch Objective

Enable the athlete to see their workout for the day, generated on-demand from the planned session and current twin state. The `WorkoutGenerationAgent` produces a `GeneratedWorkout` with linked `WorkoutStep` records, each carrying a `physiological_intent`. Targets are calibrated to the athlete's data tier: power for Tier 1-2, GAP for Tier 3-4, description-only for Tier 5-6. Generation is idempotent for `(planned_session_id, date)`. At this phase, `adjusted_targets` equals `theoretical_targets` because wellness and weather modifiers do not yet exist.

## Preconditions

- `generated_workouts` and `workout_steps` tables exist (from phase-1-2c migration)
- TwinState, PlannedSession, TrainingPlan exist (from phases 1-3 through 1-4)
- `ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler` exist (from phase-1-5a)
- LiteLLM proxy is deployed (ADR-007)

## Scope

- `GeneratedWorkoutRepository` — append-only insert, idempotent lookup by `(planned_session_id, date)`
- `WorkoutStepRepository` — batch insert, ordered retrieval by `step_order`
- `PlannedSessionRepository` — lookup by ID and today's session for an athlete (staleness join through WeeklyPlan → TrainingPlan)
- `WorkoutGenerationAgent` — LLM agent following `FirstMessageAgent` pattern (constructor DI, no commit, `GenerationEvent` on every call)
- `ContextBudgetService.build_workout_context()` — assemble and budget-enforce context (3000 token budget)
- Target type inference — static mapping from `DataTier` to primary target modality
- `SESSION_INTENT_MAP` — static mapping from `SessionType` to `PhysiologicalIntent` for work steps
- Two-column `TargetSet` — workout-level `theoretical_targets` and `adjusted_targets` (identical at this phase)
- API schemas — `WorkoutStepResponse`, `GeneratedWorkoutResponse`, `TodayResponse`
- `GET /athletes/{id}/today` — returns today's `PlannedSession` + `GeneratedWorkout` + `WorkoutStep[]`
- `POST /athletes/{id}/sessions/{sid}/generate-workout` — explicit generation trigger
- Prompt template — `app/core/prompts/workout_gen_v1.md`
- `workout_generated` event via `EventPublisher`

## Out Of Scope

- Recovery modifier computation on `adjusted_targets` — deferred to Phase 3
- Weather modifier computation — deferred to Phase 3
- Cycle phase adjustment — deferred to Phase 3
- Workout segmentation (`PlannedSegment` / `PhysiologicalSegment`) — deferred to Phase 5
- Objectives annotation on workout — deferred to Phase 4
- Workout library entries — separate subsystem
- Migration creation — tables already exist from Phase 1-2c
- Priority-weighted truncation implementation — deferred per ADR-001

## Steps

1. [OWNER: Coder] Create `GeneratedWorkoutRepository`. Implement append-only `insert()` (flush, no commit). Implement `get_by_session_and_date(planned_session_id, generation_date)` for idempotency lookup. Implement `get_by_planned_session(planned_session_id)` for retrieval. Register in `app/repositories/__init__.py`.

2. [OWNER: Coder] Create `WorkoutStepRepository`. Implement batch `insert_many(steps)` that adds all steps and flushes. Implement `get_by_workout(generated_workout_id)` ordered by `step_order ASC`. Register in `app/repositories/__init__.py`.

3. [OWNER: Coder] Create `PlannedSessionRepository`. Implement `get_by_id()` and `get_today_for_athlete(athlete_id, target_date)` with staleness join (PlannedSession → WeeklyPlan → TrainingPlan where `status = 'active'`). Register in `app/repositories/__init__.py`.

4. [OWNER: Coder] Create `app/services/workout_target_types.py` with `SESSION_INTENT_MAP` (SessionType → PhysiologicalIntent), `DATA_TIER_TARGET_TYPE` (DataTier → target modality string), and `get_step_physiological_intent(step_type, session_type)` helper that returns `RECOVERY` for warmup/cooldown/recovery steps.

5. [OWNER: Coder] Add `build_workout_context()` to `ContextBudgetService`. Assembles `WorkoutGenerationContext` with: session summary (type, phase, week, intent, duration), readiness digest, data tier, target type, objectives placeholder (empty list). 3000 token budget. Log warning on overflow but return full context.

6. [OWNER: Coder] Create `WorkoutGenerationAgent`. Constructor receives repos + `ContextBudgetService` + `PromptRegistry` + `EventPublisher`. Does NOT commit. `generate(planned_session_id, athlete_id)` flow:
   a. Idempotency: query existing by `(planned_session_id, date)`. Return existing if found.
   b. Assemble context via `build_workout_context()`.
   c. Load prompt `"workout_gen_v1"`.
   d. Call LiteLLM proxy with structured JSON output.
   e. Parse steps (step_order, step_type, physiological_intent, duration, targets, description).
   f. Validate: all intents non-null, sequential orders, warmup first, cooldown last.
   g. Build `TargetSet` for `theoretical_targets` and `adjusted_targets` (identical).
   h. Create `GeneratedWorkout` + `WorkoutStep[]` via repos.
   i. Write `GenerationEvent` (success or failure).
   j. Publish `workout_generated` via outbox.
   Register in `app/services/__init__.py`.

7. [OWNER: Coder] Create prompt template `app/core/prompts/workout_gen_v1.md`. Encode: `SESSION_INTENT_MAP` rules, data tier target rules, step structure rules (warmup first, cooldown last, recovery between work steps), JSON output schema, GAP-only pace, `description` always non-empty, `numeric targets = null` for Tier 5-6.

8. [OWNER: Coder] Create API schemas: `WorkoutStepResponse` (from_attributes, all WorkoutStep fields), `GeneratedWorkoutResponse` (with nested steps, theoretical/adjusted targets), `TodayResponse` (planned_session + generated_workout). Register in `app/schemas/__init__.py`.

9. [OWNER: Coder] Create `GET /athletes/{id}/today` endpoint. Resolves active plan → today's `PlannedSession` via staleness join. Queries existing workout. If no session today → 404. If session exists but no workout → trigger generation inline. Returns `TodayResponse`.

10. [OWNER: Coder] Create `POST /athletes/{sid}/sessions/{sid}/generate-workout` endpoint. Validates session belongs to athlete's active plan. Calls `WorkoutGenerationAgent.generate()`. Returns 201 if new, 409 if existing. On LLM failure → 502.

11. [OWNER: Coder] Create `workout_router` in `app/api/v1/workout.py`. Create `build_workout_generation_agent()` dependency factory. Register router in `app/api/v1/__init__.py`.

## Context Needed

- `01-entities/generated-workout.md` — model and idempotency contract
- `01-entities/workout-step.md` — step structure, physiological intent, data-tier targets
- `01-entities/twin-state.md` — twin state read, threshold estimates, data tier, confidence
- `01-entities/planned-session.md` — session lookup, intent description, session type
- `00-foundations/data-tiers.md` — data tier definitions, target type per tier
- `03-agents/workout-generation-agent.md` — context contract, output contract, idempotency, failure semantics
- `03-agents/context-budget-service.md` — `build_workout_context` method, 3000 token budget
- `04-platform/event-topology.md` — transactional outbox pattern for `workout_generated`

## Batch Success Criteria

- `GET /athletes/{id}/today` returns session + generated workout with steps when session exists
- `GET /athletes/{id}/today` returns 404 when no session exists for today
- `POST /sessions/{sid}/generate-workout` returns 201 with `GeneratedWorkoutResponse` on first call
- Calling `POST /generate-workout` twice returns 409 on second call with existing workout
- `GeneratedWorkout` is idempotent for `(planned_session_id, date)` — second call skips LLM
- `WorkoutStep.physiological_intent` is never null — warmup/cooldown→recovery, work→derived from session type
- `WorkoutStep.step_order` is unique within a `generated_workout_id`
- For Tier 1-2 athlete: `WorkoutStep.target` contains non-null `target_power_watts`
- For Tier 3-4 athlete: `target_gap_sec_per_km` is populated
- For Tier 5-6 athlete: all numeric targets are null, `description` carries full intent
- Both `theoretical_targets` and `adjusted_targets` are always written as non-null JSONB (identical at this phase)
- `twin_state_id` links to the latest TwinState at generation time (not retroactively updated)
- All pace values use GAP, never raw pace
- Every LLM call writes `GenerationEvent` with `agent_name="WorkoutGenerationAgent"`
- On LLM failure: `GenerationEvent` written with `success=false`, no `GeneratedWorkout` created, returns 502
- Cross-athlete access returns 403
- `workout_generated` event published via outbox after successful generation

## Files Expected To Change

- `app/repositories/generated_workout_repository.py` — new repository
- `app/repositories/workout_step_repository.py` — new repository
- `app/repositories/planned_session_repository.py` — new repository
- `app/services/workout_target_types.py` — new constants module
- `app/services/workout_generation_agent.py` — new agent service
- `app/services/context_budget_service.py` — add `build_workout_context()`
- `app/core/prompts/workout_gen_v1.md` — new prompt template
- `app/schemas/workout.py` — new response schemas
- `app/api/v1/workout.py` — new workout routes
- `app/api/v1/__init__.py` — register `workout_router`
- `app/repositories/__init__.py` — register new repositories
- `app/services/__init__.py` — register new services

## Coder Notes

- **Idempotency**: `GeneratedWorkoutRepository.get_by_session_and_date()` uses the `uq_generated_workouts_planned_session_generation_date` unique constraint. `WorkoutGenerationAgent` checks this before any LLM call.
- **Step validation before DB writes**: Validate all step orders, physiological_intents, and structural rules (warmup first, cooldown last) BEFORE inserting any records. Build all domain objects in memory, validate, then insert.
- **Transaction ownership**: `WorkoutGenerationAgent` does NOT commit. All repository writes are flushed inside the same transaction. The route handler calls `session.commit()` after the agent returns.
- **Target type by data tier**: Tier 1-2 → `target_power_watts` primary, `target_gap_sec_per_km` secondary. Tier 3-4 → `target_gap_sec_per_km` primary, `target_hr_zone` secondary. Tier 5-6 → `description` only, numeric targets null.
- **GAP enforcement is prompt-level**: Pace values use GAP only — enforced by the prompt template, not application-level validation at insert time.
- **`adjusted_targets = theoretical_targets`**: At this phase, no wellness or weather modifiers exist. Both columns are set to the same `TargetSet`. When Phase 3 adds modifiers, only `adjusted_targets` changes.
- **Objectives placeholder**: `relevant_objectives` is an empty list (objectives deferred to Phase 4). The prompt handles the empty case gracefully.
- **Recovery modifier defaults**: `recovery_modifier_level = GREEN`, `recovery_modifier_reason = None`. Set directly in the service.
- **HTTP status codes**: GET /today → 404 when no session today. POST /generate-workout → 502 on LLM failure (distinguished from 503 for workout-specific LLM outages).
- **Steps are never updated**: A regenerated workout creates a new `GeneratedWorkout` with new steps. Steps are never modified after creation.
