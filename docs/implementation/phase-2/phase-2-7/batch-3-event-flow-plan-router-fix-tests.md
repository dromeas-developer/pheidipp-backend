# Test Scenarios — Phase 2.7 — Batch 3: Event-Flow, Plan-Router & Cleanups

> **STATUS — Post-Shipping Review (TA Review) — RESOLVED via ADR-012:** Scenarios 1–6 (twin_model_ready event production), 24 (docstring fix), and 25–26 (TrainingGoalRepository verification) test behaviour that was affected by the post-shipping review documented in the companion BRD. The producer-semantic disagreement is now **resolved** — the Vision & Architecture Author chose Path B (amend the catalogue to match the implemented behaviour) via **ADR-012** (`docs/adr/012-twin-model-ready-producer-amendment.md`, status: `accepted`). Specifically:
> - **Scenarios 1–6** test the bootstrap-`OnboardingService` producer semantic, which is now the ratified contract per ADR-012. These scenarios stand as written — the catalogue now names `OnboardingService` as the producer with the trigger firing immediately after the bootstrap TwinState insert for all tiers.
> - **Scenario 24** tests the docstring edit that TA review determined should not have been prescribed (filed at wrong layer). The shipped edit, if benign, may pass this scenario as written.
> - **Scenarios 25–26** test the verification of `TrainingGoalRepository_unique_violation` that TA review determined was filed at the wrong layer (the symbol is not an architecture contract).
> - **Scenarios 27–28** test catalogue amendments that are now ratified by ADR-012 — they stand as written.
> Scenarios 7–23 (worker tasks, `PlanQueryService`, plan-router layer fix) test behaviour that shipped correctly and is not affected by the review.


## Steps 1-2 — `twin_model_ready` event production and onboarding change

| # | Scenario | Input | Expected |
|---|---|---|---|
| 1 | `twin_model_ready` event is produced after onboarding | Call `complete_onboarding()` with valid input; query `system_events` for `event_type='twin_model_ready'` | One row exists with `athlete_id` matching the onboarded athlete, payload contains `{twin_state_id, data_tier, confidence_level}` |
| 2 | `twin_model_ready` fires in the onboarding transaction | Begin onboarding, simulate a failure after the `twin_model_ready` outbox write but before commit | No `twin_model_ready` row in `system_events` — the event is rolled back with the transaction |
| 3 | Onboarding no longer calls `PlanGenerationService` directly | Call `complete_onboarding()` and inspect the onboarding transaction | No `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, `PlannedSession`, or `Checkpoint` rows are created in the onboarding transaction |
| 4 | `generate_plan` task is deferred after onboarding commit | Call `complete_onboarding()`; inspect procrastinate's `procrastinate_jobs` table | A `generate_plan` job exists with `args` containing `athlete_id` |
| 5 | Onboarding response does not block on plan generation | Call `POST /onboarding` and measure response time | Response returns 201 before the `generate_plan` task completes — plan generation is async |
| 6 | `GET /plan` returns 404 immediately after onboarding | Call `complete_onboarding()`, immediately call `GET /athletes/{id}/plan` | Returns 404 — the plan does not exist yet (the `generate_plan` task has not run) |

## Step 3 — `generate_plan` worker task

| # | Scenario | Input | Expected |
|---|---|---|---|
| 7 | `generate_plan` task creates a TrainingPlan | Run the `generate_plan` task with an `athlete_id` that has completed onboarding | A `TrainingPlan` with `status='active'` exists for the athlete's `TrainingGoal`; `training_plan_generated` event is in `system_events` |
| 8 | `generate_plan` task creates WeeklyPlans and PlannedSessions | Run the `generate_plan` task; query `weekly_plans` and `planned_sessions` | WeeklyPlans and PlannedSessions exist for the TrainingPlan, covering the full duration to the goal event |
| 9 | `generate_plan` task defers `generate_first_message` | Run the `generate_plan` task; inspect `procrastinate_jobs` | A `generate_first_message` job exists with `args` containing `athlete_id` |
| 10 | `generate_plan` task is idempotent via supersession | Run `generate_plan` twice for the same athlete | First run creates an active plan; second run supersedes the first (old plan `status='superseded'`, `superseded_at` non-null) and creates a new active plan |
| 11 | `GET /plan` returns 200 after `generate_plan` task completes | Run `complete_onboarding()`, run `generate_plan` task, call `GET /athletes/{id}/plan` | Returns 200 with the TrainingPlan and phase definitions |

## Step 4 — `generate_first_message` worker task

| # | Scenario | Input | Expected |
|---|---|---|---|
| 12 | `generate_first_message` task creates a CoachingMessage | Run the `generate_first_message` task with an `athlete_id` that has an active plan and no existing first_message | A `CoachingMessage` with `message_type='first_message'` exists; `coaching_message_generated` event is in `system_events` |
| 13 | `generate_first_message` task is idempotent | Run `generate_first_message` twice for the same athlete | First run creates the message; second run returns success without creating a duplicate (agent's `get_existing_first_message` check returns the existing message) |
| 14 | `generate_first_message` handles `FirstMessageAlreadyExistsError` gracefully | Pre-create a first_message, then run the `generate_first_message` task | Task returns success (no error, no duplicate message, no LLM call) |
| 15 | `generate_first_message` retries on LLM failure | Simulate LLM proxy unavailable, run the task | `GenerationEvent` with `success=false` is written; task retries per procrastinate retry policy |
| 16 | `GET /coach/messages` returns the first message after async generation | Run `complete_onboarding()`, `generate_plan`, `generate_first_message`, call `GET /athletes/{id}/coach/messages` | Returns one message with `message_type='first_message'` |

## Step 5 — `POST /coach/first-message` as manual retry

| # | Scenario | Input | Expected |
|---|---|---|---|
| 17 | Manual endpoint returns 409 if async generation already created the message | Run async generation first, then call `POST /athletes/{id}/coach/first-message` | Returns 409 with existing `message_id` — no second LLM call |
| 18 | Manual endpoint returns 201 if async generation has not run | Complete onboarding + plan generation, do NOT run `generate_first_message`, call `POST /athletes/{id}/coach/first-message` | Returns 201 with a new CoachingMessage — the manual endpoint is the fallback |

## Step 6 — `PlanQueryService` and plan-router layer fix

| # | Scenario | Input | Expected |
|---|---|---|---|
| 19 | `PlanQueryService.get_sessions_for_plan` returns sessions | Create a plan with sessions, call `get_sessions_for_plan(plan_id)` | Returns all PlannedSessions for the plan, joined through WeeklyPlan (staleness-safe) |
| 20 | `PlanQueryService.get_upcoming_sessions` returns next 5 | Create a plan with sessions on various dates, call `get_upcoming_sessions(athlete_id, limit=5)` | Returns up to 5 sessions with `target_date >= today`, ordered by `target_date` |
| 21 | `PlanQueryService.get_checkpoints_for_plan` returns checkpoints | Create a plan with checkpoints, call `get_checkpoints_for_plan(plan_id)` | Returns all Checkpoints for the plan, joined through PlannedSession → WeeklyPlan |
| 22 | Plan router no longer executes SQL directly | Inspect `app/api/v1/plan.py` for `session.execute` or `select(` | Zero matches — all queries are delegated to `PlanQueryService` |
| 23 | Plan router endpoints return same results as before | Call `GET /plan/sessions`, `GET /plan/upcoming`, `GET /plan/checkpoints` before and after the refactor | Identical responses — the service layer change is transparent to the API |

## Step 7 — Stale docstring fix

| # | Scenario | Input | Expected |
|---|---|---|---|
| 24 | `run_ingestion_pipeline` docstring is accurate | Read the docstring of `run_ingestion_pipeline` in `activity_ingestion_service.py` | Docstring states that the method publishes `sport_type_detected`, `activity_ingested`, and `activity_calibration_eligible` events via `EventPublisher` within the transaction — no longer says "Does NOT publish events" |

## Step 8 — `TrainingGoalRepository_unique_violation` verification

| # | Scenario | Input | Expected |
|---|---|---|---|
| 25 | Reference is correct or fixed | Read `onboarding_service.py` at the line referencing `TrainingGoalRepository_unique_violation` | Either: (a) the method exists on `TrainingGoalRepository` and the call works, or (b) the typo is fixed to `is_unique_violation` (or the correct method name) and the call works |
| 26 | Onboarding handles duplicate goal gracefully | Create an active goal for an athlete, then call `complete_onboarding()` for the same athlete | Returns 409 (TrainingGoalConflictError) — the unique violation is caught and translated correctly |

## Step 9 — Architecture documentation

| # | Scenario | Input | Expected |
|---|---|---|---|
| 27 | `event-topology.md` documents the implemented flow | Read the "Plan Generation Event Flows → Initial Plan Generation" section | Documents: `twin_model_ready` → `generate_plan` task → `training_plan_generated` → `generate_first_message` task → `coaching_message_generated` |
| 28 | `event-catalogue.md` confirms `twin_model_ready` producer | Read the `twin_model_ready` entry | Producer is `OnboardingService`; consumer is the `generate_plan` procrastinate task |