> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-4-p1-plan-generation.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-4, verified against the current codebase on 2026-07-19.

## Batch Objective

Generate a complete training plan from the bootstrapped twin and defined goal using a pure Python service — no LLM, no external API calls. The service produces the full plan hierarchy atomically: `TrainingPlan` → `WeeklyPlan[]` → `WeeklySession[]` → `PlannedSession[]`, plus `Checkpoint` records. The plan skeleton gives the coaching agents in Phase 1-5a/b the phase context they need to generate meaningful messages and workouts. Only `race_event` and `target_performance` goal types are supported in Phase 1.

## Preconditions

- TrainingGoal exists (from onboarding, phase-1-3)
- TwinState exists (from onboarding, phase-1-3)
- AthletePreferences exist (from phase-1-2a)
- `training_plans`, `weekly_plans`, `weekly_sessions`, `planned_sessions`, `checkpoints` tables exist (from phase-1-2b migration)

## Scope

- `TrainingPlanRepository` — insert plan, supersede existing active plan atomically, query active plan
- `WeeklyPlanRepository` — bulk-insert weekly plans with their weekly sessions
- `WeeklySessionRepository` — bulk-insert weekly sessions
- `CheckpointRepository` — insert checkpoint records
- `PlanGenerationService` — deterministic plan generation from templates:
  - Training length gate validation
  - Phase definition generation (race_event: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week)
  - Weekly session synthesis respecting structural rules
  - Checkpoint scheduling algorithm
  - Atomic persistence of full hierarchy in one transaction
  - Supersession of existing active plan within the same transaction
  - `training_plan_generated` event via transactional outbox
- `plan_router` with four read-only endpoints
- Response schemas: `TrainingPlanResponse`, `PlannedSessionResponse`, `CheckpointResponse`
- Onboarding integration: trigger plan generation at end of onboarding transaction

## Out Of Scope

- `fitness_improvement`, `maintenance`, `recovery` goal types
- LLM-driven hypothesis generation (Phase 1.4 uses deterministic templates only)
- Plan regeneration on confidence upgrade
- Session lifecycle management (skip, miss, redistribute)
- Workout library and workout generation
- Pre-week review and redistribution logic

## Steps

1. [OWNER: Coder] Create `TrainingPlanRepository` (insert, get active for goal, get active for athlete, supersede), `WeeklyPlanRepository` (bulk-insert with WeeklySessions, get by plan, get by plan+week), `CheckpointRepository` (bulk-insert, get by plan). All take `AsyncSession`, flush but no commit. Register in `app/repositories/__init__.py`.

2. [OWNER: Coder] Create `PlanGenerationService` in `app/services/plan_generation_service.py`. Pure Python — no LLM, no external APIs. Validates goal type (`race_event` or `target_performance`), loads latest TwinState + TrainingGoal + AthletePreferences, dispatches to mode-specific generation, computes phase definitions, synthesizes weekly sessions respecting structural rules, creates PlannedSessions with checkpoint flags, creates Checkpoint records, supersedes any existing active plan for the same goal atomically, inserts the full hierarchy in one transaction, publishes `training_plan_generated` via outbox.

3. [OWNER: Coder] Create `app/services/plan_generation_templates.py` with deterministic phase templates and constants. Race event proportions: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week. Session distribution rules: 4-6 sessions/week, one rest day minimum, long run on preferred day, no consecutive quality sessions unless block, threshold/vo2max sandwiched between easy/rest. Checkpoint scheduling: calibration at phase transitions, benchmark at 4-week mark, progress review every 3-4 weeks, race simulation in race-specific phase. Training length gate: validates weeks-to-goal against fitness and event type.

4. [OWNER: Coder] Create Pydantic response schemas in `app/schemas/plan.py`: `PhaseDescriptorResponse`, `TrainingPlanResponse`, `PlannedSessionResponse`, `CheckpointResponse`, `UpcomingSessionsResponse`. All with `from_attributes = True`. Register in `app/schemas/__init__.py`.

5. [OWNER: Coder] Create `plan_router` in `app/api/v1/plan.py` with four read-only endpoints (all behind `require_self`): `GET /athletes/{id}/plan`, `GET /athletes/{id}/plan/sessions`, `GET /athletes/{id}/plan/upcoming`, `GET /athletes/{id}/plan/checkpoints`. All return 404 if no active plan.

6. [OWNER: Coder] Wire `PlanGenerationService` into dependency injection. Add to `app/services/__init__.py`. Register `plan_router` in `app/api/v1/__init__.py`.

7. [OWNER: Coder] Modify `OnboardingService.complete_onboarding` to invoke `PlanGenerationService.generate_plan()` after TrainingGoal and TwinState are flushed but before commit. If plan generation fails, onboarding rolls back — `onboarding_complete` remains `False`. Inject `PlanGenerationService` as optional dependency.

8. [OWNER: Coder] Verify database migration status. Tables exist from phase-1-2b migration. Generate migration only if schema changes are needed.

## Context Needed

- `01-entities/training-plan.md` — TrainingPlan model and event contract
- `01-entities/weekly-plan.md` — WeeklyPlan, WeeklySession structure
- `01-entities/planned-session.md` — PlannedSession model
- `01-entities/checkpoint.md` — Checkpoint model
- `01-entities/training-goal.md` — goal types, event types
- `01-entities/twin-state.md` — latest twin state for fitness baseline
- `02-computations/plan-generation.md` — shared types, persistence rules
- `02-computations/plan-generation-race.md` — race event phase proportions, training length gate
- `02-computations/plan-generation-target-performance.md` — gap analysis, trajectory validation
- `00-foundations/event-catalogue.md` — `training_plan_generated` event contract
- `04-platform/event-topology.md` — transactional outbox pattern (ADR-004)

## Batch Success Criteria

- After `complete_onboarding` with `goal_type = race_event`, `GET /athletes/{id}/plan` returns a `TrainingPlan` with phases ending in taper + race-week
- Phase definitions cover the full duration from today to `goal_event_date` without gaps or overlaps
- Race event phases have correct proportions: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week
- No two consecutive quality sessions (threshold, vo2max, tempo, interval, race_pace) on consecutive dates unless they share a `block_id`
- Long run session is followed by `rest` or `recovery_run` in every week
- Threshold and vo2max sessions have `easy_run`, `recovery_run`, or `rest` on the day before and after
- All `PlannedSession` records have `status = 'scheduled'`
- All `Checkpoint` records have `status = 'scheduled'`
- `GET /athletes/{id}/plan/checkpoints` returns at least one calibration, benchmark, and progress_review checkpoint for a 16+ week plan
- `GET /athletes/{id}/plan/upcoming` returns 5 or fewer sessions with `target_date >= today`
- Generating a plan for the same `TrainingGoal` twice: first plan's `status` → `superseded`, `superseded_at` is non-null
- Old plans are never deleted
- All plan endpoints return 404 when no active plan exists
- All plan endpoints return 403 for mismatched `athlete_id`
- `training_plan_generated` event published via outbox in the same transaction
- Plan generation is pure Python — no LLM calls, no external APIs
- `OnboardingService.complete_onboarding` triggers plan generation atomically — if plan fails, onboarding rolls back

## Files Expected To Change

- `app/repositories/training_plan_repository.py` — new repository
- `app/repositories/weekly_plan_repository.py` — new repository (includes WeeklySessionRepository)
- `app/repositories/planned_session_repository.py` — new repository
- `app/repositories/checkpoint_repository.py` — new repository
- `app/services/plan_generation_service.py` — new service
- `app/services/plan_generation_templates.py` — new templates module
- `app/services/plan_generation_errors.py` — new error types
- `app/schemas/plan.py` — new response schemas
- `app/api/v1/plan.py` — new plan routes
- `app/api/v1/__init__.py` — register `plan_router`
- `app/repositories/__init__.py` — register new repositories
- `app/services/__init__.py` — register new services
- `app/services/onboarding_service.py` — add PlanGenerationService integration

## Coder Notes

- **Pure Python, no LLM**: `PlanGenerationService` is entirely deterministic. Do not introduce any LLM call, external API, or agent invocation.
- **Atomic plan generation**: The entire plan hierarchy (TrainingPlan + WeeklyPlans + WeeklySessions + PlannedSessions + Checkpoints) must be created in a single database transaction. `PlanGenerationService._persist_full_plan()` calls `session.commit()`.
- **Supersession atomicity**: When generating a plan for a goal that already has an active plan, mark the old plan as `superseded` and insert the new plan in the same transaction.
- **Denormalized `training_plan_id` on PlannedSession**: Copy `weekly_plan.training_plan_id` into `planned_session.training_plan_id`. This is intentionally denormalized. Document the staleness risk.
- **Correct query pattern**: `GET /plan/sessions` and `GET /plan/upcoming` MUST join through `WeeklyPlan.training_plan_id`, not filter `PlannedSession.training_plan_id` directly (which may be stale after supersession).
- **Structural rules are hard constraints**: No consecutive quality sessions without `block_id`, long run followed by rest/recovery, threshold/vo2max sandwiched between easy/rest.
- **`strategic_rationale` is populated**: For supported goal types, contains `primary_driver`, `methodology_summary`, and `risk_notes` — short deterministic strings, not LLM-generated.
- **Checkpoint-PlannedSession one-to-one**: Every Checkpoint points to exactly one PlannedSession via `planned_session_id`. Create PlannedSession first, then Checkpoint. PlannedSession's `checkpoint_type` and `checkpoint_metric` fields must also be set.
- **Onboarding integration**: `PlanGenerationService` is injected into `OnboardingService` as an optional dependency (defaults to `None` for test backward compatibility). Plan generation runs after TrainingGoal and TwinState are flushed, before commit. Failure rolls back the entire onboarding transaction.
- **Event outbox**: `training_plan_generated` published via `EventPublisher.publish()` in the same transaction, following ADR-004.
