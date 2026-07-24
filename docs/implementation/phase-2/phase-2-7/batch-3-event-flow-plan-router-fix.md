# Batch BRD: Phase 2.7 — Batch 3 — Event-Flow, Plan-Router & Cleanups
## Source: docs/implementation/phase-2/phase-2-7/overview.md

> **STATUS — Post-Shipping Review (TA Review):** This BRD's code has been implemented. A subsequent review by `p-technical-advisor` surfaced three issues that affect how this BRD should be read retrospectively. The steps below are preserved verbatim because they record what the coder actually built; they are NOT to be re-executed.
>
> 1. **Steps 1–4, 10–11 (`twin_model_ready` producer) — shipped against the original catalogue's producer, now ratified by ADR-012.** The original catalogue named `TwinRecalibrationService` as the producer with the trigger "fires once after onboarding when twin has sufficient data." Steps 1–4 instructed the coder to fire from `OnboardingService` at the bootstrap TwinState (`confidence_level='low'`), which was not "sufficient data" against the original catalogue. Steps 10–11 instructed the coder to amend `event-catalogue.md` and `event-topology.md` to confirm `OnboardingService` as the producer. The plan-vs-architecture drift was routed to `p-vision-and-architect-author` via **Architecture Delta Proposal:** `reports/phase-2-7_architecture-delta_twin-model-ready-producer.md`. **The Vision & Architecture Author chose Path B — amend the catalogue to match the implemented behaviour.** The decision is recorded in **ADR-012** (`docs/adr/012-twin-model-ready-producer-amendment.md`, status: `accepted`). The catalogue's `twin_model_ready` producer is now `OnboardingService`, the trigger fires immediately after the bootstrap TwinState insert for all tiers, and the Tier-1 historical-ingestion language has been removed. **Steps 10–11's catalogue amendments are ratified by ADR-012 — they are no longer provisional.** The shipped Batch 3 code is the target end-state; no Batch 4 coder work is required. The Architecture Author also amended `twin-state.md`, `first-message-agent.md`, and `phase-1-5a-first-coach-message.md` for consistency.
>
> 2. **Step 8 (`run_ingestion_pipeline` docstring fix) — filed at the wrong layer; the prescribed edit would invert an intentional contract.** `_run_ingestion_pipeline` is the architecture's intentional internal caller-responsibility helper inside a deliberate two-method design. The public wrappers `ingest`/`ingest_async` own the published-events documentation and already list `sport_type_detected`, `activity_ingested`, `activity_calibration_eligible`. The Step 8 edit landed (the code shipped), but per TA review it should not have been in the plan; the finding G-09 has been retracted at the gap-analysis layer as "filed at wrong layer — not an implementation task." The shipped edit is benign if it did not change the helper docstring's contract framing; revert is a coder judgement at implementation-validation time, not a plan step.
>
> 3. **Step 9 (`TrainingGoalRepository_unique_violation` verification) — filed at the wrong layer; the symbol is a test-level error-detection helper, not a documented architecture or vision contract.** The Step 9 verification landed (the code shipped), but per TA review the finding G-13 has been retracted at the gap-analysis layer as "filed at wrong layer — not an implementation task." No further action.
>
> The remaining steps (5–7: `PlanQueryService` creation, route-handler delegation, layer-skip fix for G-07) shipped correctly and are not affected by this review. The `POST /coach/first-message` manual retry endpoint behaviour is also not affected.
>
> See `docs/implementation/gap-analysis-phase-1-2.md` §5 G-03, §5 G-09, §5 G-13 for the updated finding text and §6 for the reclassification.

## Batch Objective
Implement the `twin_model_ready` event flow as the architecture specifies (closing G-03): onboarding fires the event, a worker generates the plan asynchronously, and the first coach message is generated automatically after the plan. Also fix the plan-router layer-skip by introducing a `PlanQueryService` (closing G-07), fix the stale `run_ingestion_pipeline` docstring (closing G-09), and verify the `TrainingGoalRepository_unique_violation` reference in `onboarding_service.py` (closing G-13).

## Preconditions
Batch 1 is complete; its Batch Success Criteria hold. Specifically, agent relocation is done (`WorkoutGenerationAgent` and `FirstMessageAgent` are in `app/agents/`) and the test suite passes.

Batch 2 is not a precondition for this batch. Batch 2 (outbox publisher) and Batch 3 (event flow + plan router) touch disjoint subsystems and are independent. The order in the phase is nominal; both can proceed in parallel after Batch 1. The original Batch 3 preconditions referenced Batch 2's hypertable conversion, which has been retracted per the G-02 retraction (see `docs/implementation/gap-analysis-phase-1-2.md` §5 G-02).

## Scope
- **G-03 — `twin_model_ready` event flow:**
  - `OnboardingService.complete_onboarding()` fires `twin_model_ready` after the TwinState insert (instead of calling `PlanGenerationService.generate_plan()` directly)
  - Remove the direct `PlanGenerationService.generate_plan()` call from `OnboardingService`
  - Create a `generate_plan` procrastinate worker task that consumes `twin_model_ready` (via task deferral, not outbox polling) and calls `PlanGenerationService.generate()`
  - `PlanGenerationService.generate()` fires `training_plan_generated` (already does) and defers a `generate_first_message` procrastinate task
  - Create a `generate_first_message` procrastinate worker task that calls `FirstMessageAgent.generate()`
  - The `POST /coach/first-message` endpoint remains as a manual retry (returns 409 if the async generation already created the message)
  - Update `event-catalogue.md` and `event-topology.md` to document the implemented flow (the `twin_model_ready` event already exists in the catalogue — the update confirms the producer and consumer wiring)
- **G-07 — Plan-router layer fix:**
  - Create `PlanQueryService` in `app/services/` that owns the three read queries currently executed directly in `app/api/v1/plan.py` (`get_plan_sessions`, `get_upcoming_sessions`, `get_plan_checkpoints`)
  - Update `app/api/v1/plan.py` route handlers to delegate to `PlanQueryService` instead of executing `session.execute(select(...))` directly
- **G-09 — Stale docstring fix:**
  - Update the `run_ingestion_pipeline` docstring in `ActivityIngestionService` to match the implementation (it publishes `sport_type_detected`, `activity_ingested`, `activity_calibration_eligible`)
- **G-13 — Verify `TrainingGoalRepository_unique_violation` reference:**
  - Read `app/services/onboarding_service.py` at the referenced line; if it's a typo (should be `is_unique_violation`), fix it; if it's correct, no change

## Out Of Scope
- **No changes to the `twin_model_ready` event schema.** The event is already defined in `event-catalogue.md` with the correct payload. This batch implements the production and consumption wiring, not the schema.
- **No changes to `PlanGenerationService` generation logic.** The service already generates plans correctly. This batch changes how it is triggered (event-driven vs direct call), not what it generates.
- **No changes to `FirstMessageAgent` generation logic.** The agent already generates messages correctly. This batch changes how it is triggered (event-driven vs manual API call), not what it generates.
- **No removal of the `POST /coach/first-message` endpoint.** It stays as a manual retry. The async generation is the primary path; the manual endpoint is the fallback.
- **No `PreWeekReviewAgent` or `WeeklySynthesisAgent` implementation.** Those are Phase 2-4. This batch only wires the `twin_model_ready → plan → first_message` chain.
- **No changes to the onboarding transaction's entity creation.** The onboarding transaction still creates `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `AthletePhysiology`, `AthleteFitness`, `TwinState`, and fires `onboarding_completed`. The only change is: it no longer calls `PlanGenerationService.generate_plan()` directly, and it additionally fires `twin_model_ready`.
- **No hypertable or outbox changes.** Hypertables are out of scope for Phase 2.7 entirely (G-02 retracted). The outbox publisher is Batch 2's scope; this batch does not modify the outbox state machine or the publisher task.

## Steps

### Step 1 — Fire `twin_model_ready` from onboarding and remove direct plan-gen call

1. [OWNER: Coder] In `OnboardingService.complete_onboarding()`, after the TwinState insert and before the commit:
   - Fire `twin_model_ready` via `EventPublisher.publish()` with the payload defined in `event-catalogue.md`: `{twin_state_id, data_tier, confidence_level}`. The `athlete_id` is the event scope (already handled by `EventPublisher`).
   - Remove the direct `self.plan_service.generate_plan(athlete_id)` call (currently at line ~471 of `app/services/onboarding_service.py`).
   - Remove the `PlanGenerationService` constructor injection from `OnboardingService` (the `plan_service` optional dependency is no longer needed — plan generation is now triggered by the `twin_model_ready` event via a worker task).
   - The onboarding transaction still commits with `onboarding_completed` + `twin_model_ready` events in the outbox. The `onboarding_complete` flag is set to `true`. The plan is NOT in this transaction — it is generated asynchronously.

2. [OWNER: Coder] After the onboarding commit, defer a `generate_plan` procrastinate task. The deferral happens in `OnboardingService.complete_onboarding()` after the commit (same pattern as `ActivityIngestionService._run_ingestion_pipeline()` deferring `signal_clean`). The task receives `athlete_id` as its argument. Swallow defer failures after logging (the event is in the outbox; a future publisher pass or manual retry can trigger the task).

### Step 2 — Create the `generate_plan` worker task

3. [OWNER: Coder] Create a `generate_plan` procrastinate task in `app/worker/app.py`. The task:
   - Opens its own `AsyncSession`
   - Constructs `PlanGenerationService` with the session and its dependencies
   - Calls `PlanGenerationService.generate(athlete_id=...)` — the service generates the plan, persists it, fires `training_plan_generated` via outbox, and commits
   - After the plan is generated and committed, defers a `generate_first_message` procrastinate task with `athlete_id` as its argument
   - Returns `{training_plan_id, athlete_id}`
   - The task is idempotent in the sense that `PlanGenerationService.generate()` supersedes any existing active plan (the existing supersession logic handles re-generation)

### Step 3 — Create the `generate_first_message` worker task

4. [OWNER: Coder] Create a `generate_first_message` procrastinate task in `app/worker/app.py`. The task:
   - Opens its own `AsyncSession`
   - Constructs `FirstMessageAgent` with its dependencies (repositories, `ContextBudgetService`, `PromptRegistry`, `EventPublisher`)
   - Calls `FirstMessageAgent.generate(athlete_id=...)` — the agent checks idempotency (returns existing if first_message already exists), assembles context, calls the LLM, writes `CoachingMessage` + `GenerationEvent`, fires `coaching_message_generated`
   - Commits
   - Returns `{coaching_message_id, athlete_id}`
   - If the agent raises `FirstMessageAlreadyExistsError`, the task returns successfully (the message was already generated — this is not an error)
   - If the agent raises `LLMServiceUnavailableError` (LLM failure), the task should retry per procrastinate's retry policy. The `GenerationEvent` with `success=false` is already written by the agent.

### Step 4 — Update `PlanGenerationService` to defer first-message generation

5. [OWNER: Coder] In `PlanGenerationService.generate()` (or in the `generate_plan` worker task after the service call — the coder chooses the cleaner location), after the plan is committed and `training_plan_generated` is fired, defer the `generate_first_message` procrastinate task with `athlete_id`. This wires the event chain: `twin_model_ready → generate_plan task → training_plan_generated → generate_first_message task → coaching_message_generated`.

### Step 5 — Create `PlanQueryService` and fix plan-router layer-skip (G-07)

6. [OWNER: Coder] Create `PlanQueryService` in `app/services/plan_query_service.py`. The service owns the three read queries currently executed directly in `app/api/v1/plan.py`:
   - `get_sessions_for_plan(plan_id) -> list[PlannedSession]` — joins `PlannedSession → WeeklyPlan` on `weekly_plan_id`, filters by `WeeklyPlan.training_plan_id == plan_id` (the staleness-safe join pattern documented in Phase 1-4 Coder Notes)
   - `get_upcoming_sessions(athlete_id, limit=5) -> list[PlannedSession]` — resolves the active plan for the athlete, then queries sessions with `target_date >= today`, ordered by `target_date`, limited to `limit`
   - `get_checkpoints_for_plan(plan_id) -> list[Checkpoint]` — joins `Checkpoint → PlannedSession → WeeklyPlan`, filters by `WeeklyPlan.training_plan_id == plan_id`
   - The service takes `AsyncSession` via constructor and uses it for queries. It does not commit (read-only).
   - Register in `app/services/__init__.py`.

7. [OWNER: Coder] Update `app/api/v1/plan.py` route handlers to delegate to `PlanQueryService`:
   - `get_plan_sessions()` — remove the direct `session.execute(select(PlannedSession)...)` call; call `PlanQueryService.get_sessions_for_plan(plan_id)` instead
   - `get_upcoming_sessions()` — remove the direct `session.execute(...)` call; call `PlanQueryService.get_upcoming_sessions(athlete_id, limit=5)` instead
   - `get_plan_checkpoints()` — remove the direct `session.execute(select(Checkpoint)...)` call; call `PlanQueryService.get_checkpoints_for_plan(plan_id)` instead
   - Add a `build_plan_query_service()` dependency factory in `app/api/deps.py`
   - The route handlers no longer import `select`, `PlannedSession`, `Checkpoint`, or `WeeklyPlan` directly — they receive the results from the service

### Step 6 — Fix stale docstring (G-09)

8. [OWNER: Coder] Update the `run_ingestion_pipeline` docstring in `app/services/activity_ingestion_service.py` to accurately describe that the method publishes `sport_type_detected`, `activity_ingested`, and `activity_calibration_eligible` events via `EventPublisher` within the transaction. The current docstring incorrectly says it "Does NOT publish events."

### Step 7 — Verify `TrainingGoalRepository_unique_violation` reference (G-13)

9. [OWNER: Coder] Read `app/services/onboarding_service.py` at the line referencing `TrainingGoalRepository_unique_violation`. If this is a typo (the method should be `is_unique_violation` as on other repositories, or it should be a static method call on the repository class), fix it. If the reference is correct (e.g., it's a valid static method that exists on `TrainingGoalRepository`), no change is needed — add a code comment clarifying the call. The fix is a one-line correction if the method name is wrong.

### Step 8 — Update architecture documentation for the event flow

10. [OWNER: Coder] Update `docs/architecture/04-platform/event-topology.md` "Plan Generation Event Flows → Initial Plan Generation" section to document the implemented flow:
    - `onboarding_completed` + `twin_model_ready` fire in the onboarding transaction
    - `twin_model_ready` defers the `generate_plan` worker task (via procrastinate deferral, not outbox polling)
    - `generate_plan` task calls `PlanGenerationService.generate()`, which fires `training_plan_generated`
    - `training_plan_generated` defers the `generate_first_message` worker task
    - `generate_first_message` task calls `FirstMessageAgent.generate()`, which fires `coaching_message_generated`
    - The `POST /coach/first-message` endpoint remains as a manual retry

11. [OWNER: Coder] Update `docs/architecture/00-foundations/event-catalogue.md` `twin_model_ready` entry to confirm the producer is `OnboardingService` (fires after TwinState insert in the onboarding transaction) and the consumer is the `generate_plan` procrastinate task (triggered by task deferral). The event schema does not change.

## Context Needed
Step 1 (Steps 1-2):
  Primary:    `app/services/onboarding_service.py` (the `complete_onboarding` method, the `plan_service` injection at line ~234, the direct call at line ~471), `app/services/event_publisher.py` (the `publish` method signature)
  Secondary:  `docs/architecture/00-foundations/event-catalogue.md` (`twin_model_ready` payload schema), `app/services/activity_ingestion_service.py` (the `_defer_signal_clean` pattern for post-commit task deferral)
  Fallback:   `docs/architecture/04-platform/event-topology.md` (the intended event flow diagram)
  Forbidden:  Do not modify `PlanGenerationService.generate()` generation logic — only its trigger mechanism changes
Step 2 (Step 3):
  Primary:    `app/worker/app.py` (existing task registration pattern — `fit_ingest`, `signal_clean`, `threshold_detection`), `app/services/plan_generation_service.py` (the `generate` method signature and commit boundary)
  Secondary:  `app/api/deps.py` (dependency factory pattern for constructing services with sessions)
  Fallback:   —
  Forbidden:  —
Step 3 (Step 4):
  Primary:    `app/agents/first_message_agent.py` (the `generate` method, idempotency check, error classes), `app/worker/app.py` (task pattern)
  Secondary:  `app/services/first_message_agent.py` — wait, this was relocated in Batch 1. The path is now `app/agents/first_message_agent.py`. (If Batch 1 is complete, the file is in `app/agents/`.)
  Fallback:   —
  Forbidden:  —
Step 4 (Step 5):
  Primary:    `app/services/plan_generation_service.py` (the `generate` method — where to add the deferral), `app/worker/app.py` (the `generate_first_message` task from Step 4)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 5 (Steps 6-7):
  Primary:    `app/api/v1/plan.py` (the three route handlers with direct `session.execute` calls at lines ~90, ~120, ~155), `app/repositories/training_plan_repository.py` (`get_active_for_athlete` method), `app/repositories/planned_session_repository.py` (existing query patterns)
  Secondary:  `app/services/plan_generation_service.py` (existing service pattern for the new `PlanQueryService` to follow)
  Fallback:   —
  Forbidden:  Do not move the read queries to `PlanGenerationService` — that service owns generation, not reads. The new `PlanQueryService` is a separate read-only service.
Step 6 (Step 8):
  Primary:    `app/services/activity_ingestion_service.py` (the `run_ingestion_pipeline` docstring)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 7 (Step 9):
  Primary:    `app/services/onboarding_service.py` (the line referencing `TrainingGoalRepository_unique_violation`), `app/repositories/training_goal_repository.py` (to verify whether the method exists)
  Secondary:  `app/repositories/athlete_repository.py` (the `is_unique_violation` static method — the correct pattern if the onboarding reference is a typo)
  Fallback:   —
  Forbidden:  —
Step 8 (Steps 10-11):
  Primary:    `docs/architecture/04-platform/event-topology.md` (the "Plan Generation Event Flows" section), `docs/architecture/00-foundations/event-catalogue.md` (the `twin_model_ready` entry)
  Secondary:  —
  Fallback:   —
  Forbidden:  Do not change the `twin_model_ready` event schema — only the producer/consumer documentation

(This is everything relevant to the steps above. Primary items are fetched together in Pre-Flight Step 3; Secondary and Fallback are requested only on demand.)

## Batch Success Criteria
Batch 3 complete when:
- `OnboardingService.complete_onboarding()` fires `twin_model_ready` via `EventPublisher.publish()` with payload `{twin_state_id, data_tier, confidence_level}` after the TwinState insert
- `OnboardingService.complete_onboarding()` no longer calls `PlanGenerationService.generate_plan()` directly
- `OnboardingService` no longer accepts `PlanGenerationService` as a constructor dependency
- After `complete_onboarding()` commits, a `generate_plan` procrastinate task is deferred with `athlete_id`
- The `generate_plan` worker task exists in `app/worker/app.py`, calls `PlanGenerationService.generate()`, and defers `generate_first_message` after the plan is committed
- The `generate_first_message` worker task exists in `app/worker/app.py`, calls `FirstMessageAgent.generate()`, and handles `FirstMessageAlreadyExistsError` gracefully (returns success, no retry)
- After onboarding, the plan is generated asynchronously (not in the onboarding transaction) — `GET /athletes/{id}/plan` returns 404 until the `generate_plan` task completes, then returns the plan
- After plan generation, the first coach message is generated asynchronously — `GET /athletes/{id}/coach/messages` returns empty until the `generate_first_message` task completes, then returns the first message
- `POST /athletes/{id}/coach/first-message` still works as a manual retry — returns 409 if the async generation already created the message, returns 201 if the async generation has not yet run
- `PlanQueryService` exists in `app/services/plan_query_service.py` with `get_sessions_for_plan`, `get_upcoming_sessions`, `get_checkpoints_for_plan` methods
- `app/api/v1/plan.py` route handlers delegate to `PlanQueryService` — no direct `session.execute(select(...))` calls remain in the route handlers
- `app/api/v1/plan.py` no longer imports `select` from SQLAlchemy or model classes directly for query construction
- The `run_ingestion_pipeline` docstring in `ActivityIngestionService` accurately describes that it publishes `sport_type_detected`, `activity_ingested`, and `activity_calibration_eligible` events
- The `TrainingGoalRepository_unique_violation` reference in `onboarding_service.py` is either fixed (if it was a typo) or verified (if it was correct, with a clarifying comment added)
- `event-topology.md` "Plan Generation Event Flows" section documents the implemented `twin_model_ready → generate_plan task → training_plan_generated → generate_first_message task` chain
- `event-catalogue.md` `twin_model_ready` entry confirms the producer is `OnboardingService` and the consumer is the `generate_plan` procrastinate task
- The full existing test suite passes (test files may need updates for the async plan generation timing, but the test logic should not change — tests that assumed plan generation was synchronous need to either await the task or poll for the plan)

## Relevant Architecture Contracts
- `00-foundations/event-catalogue.md` → `twin_model_ready` — IMPLEMENTS: produces the event from `OnboardingService`, consumed by the `generate_plan` worker task
- `00-foundations/event-catalogue.md` → `training_plan_generated` — DEPENDS ON: already produced by `PlanGenerationService`; this batch adds the `generate_first_message` consumer
- `04-platform/event-topology.md` → "Plan Generation Event Flows → Initial Plan Generation" — IMPLEMENTS: the event chain `twin_model_ready → plan → first_message`
- Stack-truth instruction `001-stack-truth.md` → "No direct repository access outside services" and "Route handlers MUST NOT execute SQLAlchemy queries directly" — IMPLEMENTS: `PlanQueryService` owns plan read queries

## Relevant Invariants
- **Transactional outbox atomicity:** `twin_model_ready` is written to the outbox in the same transaction as the onboarding state change. The `generate_plan` task deferral happens after the commit (post-commit deferral, same pattern as `signal_clean`). The plan generation is a separate transaction — if it fails, the onboarding is still complete.
- **Layer architecture (non-negotiable):** `api → services → repositories → models`. No direct repository access outside services. No layer skipping. — `PlanQueryService` enforces this for plan read queries.
- **First message idempotency:** One first_message per athlete per active goal. 409 on second call. — The async `generate_first_message` task and the manual `POST /coach/first-message` endpoint both check for existing messages before calling the LLM. Whichever runs first creates the message; the second one gets a 409 (manual) or graceful return (async task).

## Relevant Notes
**Implementation Clarifications** — The `generate_plan` and `generate_first_message` tasks are triggered by procrastinate task deferral, not by outbox polling. The `twin_model_ready` and `training_plan_generated` events are still written to the outbox (for audit and future external consumers), but the in-process consumers are triggered by `task.defer(...)` calls, not by reading the outbox. This is the same pattern used by `signal_clean` (deferred by `ActivityIngestionService` after the ingestion commit) and `threshold_detection` (deferred by `signal_clean` after its commit).

**Known Risks** — The onboarding flow changes from synchronous plan generation to asynchronous. The `POST /onboarding` response no longer includes a plan — the plan is generated by a worker task after the response is sent. Clients that currently expect the plan to be available immediately after onboarding will see a 404 from `GET /plan` until the worker completes. The client should poll `GET /plan` (returns 404 → eventually returns 200) or wait for a `training_plan_generated` event (if the client subscribes to events). This is the intended architecture — the separation enables Tier 1 onboarding (historical import → plan later) without conditional logic.

**Known Risks** — If the `generate_plan` worker task fails (e.g. LLM proxy down, validation error), the athlete has no plan. The onboarding is complete (`onboarding_complete = true`), but `GET /plan` returns 404. The `twin_model_ready` event is in the outbox; a manual retry (re-deferring the task or calling `POST /coach/first-message` after the plan is manually generated) is the recovery path. The system should log the failure clearly. A future enhancement could add a "plan generation pending" status to the onboarding response, but that is out of scope for this batch.

## Files Expected To Change
- `[EXISTING — modified] app/services/onboarding_service.py` — fire `twin_model_ready`, remove direct `PlanGenerationService` call, remove `plan_service` dependency, defer `generate_plan` task
- `[EXISTING — modified] app/worker/app.py` — add `generate_plan` and `generate_first_message` tasks
- `[EXISTING — modified] app/services/plan_generation_service.py` — defer `generate_first_message` task after plan generation (or the deferral happens in the worker task — coder's choice)
- `[NEW] app/services/plan_query_service.py` — read-only service for plan queries
- `[EXISTING — modified] app/api/v1/plan.py` — delegate to `PlanQueryService`, remove direct SQL
- `[EXISTING — modified] app/api/deps.py` — add `build_plan_query_service` factory
- `[EXISTING — modified] app/services/__init__.py` — register `PlanQueryService`
- `[EXISTING — modified] app/services/activity_ingestion_service.py` — fix `run_ingestion_pipeline` docstring
- `[EXISTING — modified] app/services/onboarding_service.py` — verify/fix `TrainingGoalRepository_unique_violation` reference (Step 9)
- `[EXISTING — modified] docs/architecture/04-platform/event-topology.md` — document implemented event flow
- `[EXISTING — modified] docs/architecture/00-foundations/event-catalogue.md` — confirm `twin_model_ready` producer/consumer

## Coder Notes
- **The onboarding transaction becomes lighter.** Previously, the onboarding transaction included plan generation (TrainingPlan + WeeklyPlans + WeeklySessions + PlannedSessions + Checkpoints). Now it includes only profile, preferences, goal, physiology, fitness, twin state, and events. The plan is generated in a separate transaction by the `generate_plan` worker task. This is the intended architecture — the `onboarding_completed` and `twin_model_ready` events are in the same transaction; the plan is not.
- **`PlanGenerationService` commit boundary.** Currently, `PlanGenerationService._persist_full_plan()` calls `session.commit()`. When called from the `generate_plan` worker task, the worker creates the session and passes it to the service. The service still commits — this is the same pattern as when it was called from `OnboardingService`. The worker does not commit again after the service returns.
- **`FirstMessageAgent` location.** After Batch 1, `FirstMessageAgent` is in `app/agents/first_message_agent.py`. The `generate_first_message` worker task imports it from there. If Batch 1 has not been applied yet, the import is from `app/services/first_message_agent.py` — but Batch 3's precondition is that Batch 1 is complete.
- **Test timing.** Tests that currently assume the plan is available immediately after `complete_onboarding()` will fail — the plan is now async. These tests need to either: (a) await the `generate_plan` task directly (call the task function in-process), or (b) call `PlanGenerationService.generate()` directly after onboarding in the test setup, or (c) poll `GET /plan` until it returns 200. The coder should update tests to use approach (a) or (b) — polling in tests is fragile.
- **`POST /coach/first-message` as manual retry.** The endpoint stays. If the async `generate_first_message` task fails (LLM proxy down), the athlete can manually trigger generation via the endpoint. The endpoint's idempotency check (409 if message exists) handles the case where the async task already succeeded.
- **`PlanQueryService` is read-only.** It does not commit, does not call `EventPublisher`, does not modify state. It takes `AsyncSession` and runs queries. The route handlers construct it via `build_plan_query_service()` and pass the session.