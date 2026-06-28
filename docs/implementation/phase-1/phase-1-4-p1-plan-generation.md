# Implementation Plan: Phase-1.4 — Plan Generation
## Plan ID: Phase-1.4-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.4
Sub-Phase Title: Plan Generation

## Objective
Generate a complete training plan from the bootstrapped twin and defined goal using a pure Python service — no LLM, no external API calls. The service produces the full plan hierarchy atomically: `TrainingPlan` → `WeeklyPlan[]` → `WeeklySession[]` → `PlannedSession[]`, plus `Checkpoint` records. The plan skeleton gives the coaching agents in Phase-1.5a/b the phase context they need to generate meaningful messages and workouts. Only `race_event` and `target_performance` goal types are supported in Phase 1.

This plan delivers both the `PlanGenerationService` and the four read-only endpoints that expose the generated plan. Because the exit gate requires `GET /athletes/{id}/plan` to return a valid plan, the service and endpoints must ship together.

## Scope
- `TrainingPlanRepository` — insert plan, supersede existing active plan atomically, get active plan for goal
- `WeeklyPlanRepository` — bulk-insert weekly plans with their weekly sessions
- `CheckpointRepository` — insert checkpoint records
- `PlanGenerationService` — deterministic plan generation from templates:
  - Training length gate validation
  - Phase definition generation from `goal_type` templates (race_event: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week; target_performance: similar proportions with gap-analysis-driven timeline)
  - Weekly session synthesis respecting structural rules (no consecutive quality sessions unless block, long run followed by rest, threshold sandwiched between easy days)
  - Checkpoint scheduling algorithm (confidence gaps, phase transitions, regular intervals)
  - Atomic persistence of full hierarchy in one transaction
  - Supersession of existing active plan within the same transaction
  - `training_plan_generated` event via transactional outbox
- Response schemas: `TrainingPlanResponse`, `PlannedSessionResponse`, `CheckpointResponse`
- `plan_router` with four endpoints: `GET /plan`, `GET /plan/sessions`, `GET /plan/upcoming`, `GET /plan/checkpoints`
- Router registration and dependency injection wiring
- Test manifest and test data factories for plan fixtures

## Out Of Scope
- `fitness_improvement`, `maintenance`, `recovery` goal types — deferred per sub-phase document
- LLM-driven hypothesis generation for race_event mode — Phase 1.4 uses deterministic templates
- Plan regeneration on confidence upgrade — deferred to Phase 2
- Session lifecycle management (skip, miss, redistribute) — deferred to Phase 4
- Workout library and workout generation — deferred to Phase 4
- Plan regeneration on goal date change > 7 days — keep minimal per sub-phase document
- Weekly synthesis via LLM — Phase 1.4 generates all weeks deterministically upfront
- `weekly_plan_created` / `week_completed` events — deferred to the asynchronous weekly rhythm (Phase 2+)
- Pre-week review and session redistribution logic

## Architecture Contracts
- `01-entities/training-goal.md` — DEPENDS ON (must exist before plan generation)
- `01-entities/twin-state.md` — DEPENDS ON (latest twin state feeds plan generation)
- `01-entities/training-plan.md` — IMPLEMENTS (creates TrainingPlan, produces `training_plan_generated` event)
- `01-entities/weekly-plan.md` — IMPLEMENTS (creates WeeklyPlan + WeeklySession records)
- `01-entities/planned-session.md` — IMPLEMENTS (creates PlannedSession records with checkpoint flags)
- `01-entities/checkpoint.md` — IMPLEMENTS (creates Checkpoint records atomically with PlannedSession)
- `02-computations/plan-generation.md` — IMPLEMENTS (shared types, persistence rules, persistence function)
- `02-computations/plan-generation-race.md` — IMPLEMENTS (training length gate, phase proportions for race_event)
- `02-computations/plan-generation-target-performance.md` — IMPLEMENTS (gap analysis, target date computation, trajectory validation)
- `00-foundations/event-catalogue.md` → `training_plan_generated` — PRODUCES

## Invariants
- **PlanGenerationService is pure Python — no LLM, no external API calls.** Deterministic templates only.
- **One active plan per TrainingGoal at any time.** When a new plan is generated for a goal, the previous plan's `status` → `superseded` and `superseded_at` is set, atomically with the new plan's creation.
- **Old plans are never deleted.** `superseded_at` is the only mutation on an inactive plan.
- **`phases` is a non-overlapping, ordered array.** The combined date range covers from the plan start date to `TrainingGoal.goal_event_date` without gaps.
- **Phases have correct proportional duration** (race_event: 40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week).
- **`PlannedSession` records cover the full duration to the goal event with no gaps.**
- **No two consecutive quality sessions appear in generated schedule** unless they share a `block_id`.
- **Long runs are always followed by a rest or recovery_run session.**
- **Threshold and vo2max sessions are sandwiched between easy or rest days.**
- **`WeeklyPlan` sessions array is immutable once `status = active`.** For Phase 1.4, all WeeklyPlans are created with `status = 'synthesised'`.
- **One WeeklyPlan per week per TrainingPlan.** Cannot create two plans for the same `(training_plan_id, week_number)`.
- **`PlannedSession.training_plan_id` is denormalized and can be stale.** Queries for "current plan sessions" MUST join through `WeeklyPlan`, not filter `PlannedSession.training_plan_id` directly.
- **One checkpoint per PlannedSession.** A PlannedSession may be flagged as a checkpoint, but a checkpoint cannot exist without a corresponding PlannedSession.
- **Checkpoint cannot be created retroactively.** Checkpoints are scheduled during plan synthesis, not after session completion.
- **`strategic_rationale` is set only for `race_event` and `target_performance` mode plans.** Internal hypothesis exploration names are not persisted.
- **`training_plan_generated` event fires via transactional outbox** inside the same DB transaction as the producing domain state.

## Implementation Steps

### Step 1 — Plan Repositories
[OWNER: Coder]

Introduce three new repositories under `app/repositories/`:

**`TrainingPlanRepository`** — persistence abstraction for TrainingPlan supporting:
- Insert a new TrainingPlan within the calling session (flush, no commit)
- Get the active TrainingPlan for a given `training_goal_id`
- Supersede an existing active plan: set `status = 'superseded'`, `superseded_at = now()` (flush, no commit)
- Get the active TrainingPlan for an athlete (joins through TrainingGoal)

**`WeeklyPlanRepository`** — persistence abstraction for WeeklyPlan supporting:
- Bulk-insert WeeklyPlan records with their WeeklySession children (flush, no commit)
- Get all WeeklyPlans for a TrainingPlan
- Get a WeeklyPlan by `(training_plan_id, week_number)`

**`CheckpointRepository`** — persistence abstraction for Checkpoint supporting:
- Bulk-insert Checkpoint records (flush, no commit)
- Get all Checkpoints for a TrainingPlan (joins through PlannedSession → WeeklyPlan → TrainingPlan)

All repositories take `AsyncSession` in their constructor, expose no commit calls (commit ownership stays with the service), and register in `app/repositories/__init__.py`.

### Step 2 — Plan Generation Service
[OWNER: Coder]

Introduce `app/services/plan_generation_service.py` implementing `PlanGenerationService`.

The service is the single owner of plan generation. It:
1. Retrieves the latest `TwinState` for the athlete via `TwinStateRepository`
2. Retrieves the active `TrainingGoal` via `TrainingGoalRepository`
3. Retrieves `AthletePreferences` via `AthletePreferencesRepository`
4. Validates inputs (goal type restricted to `race_event` / `target_performance`)
5. Dispatches to mode-specific generation:
   - **race_event mode**: evaluate training length gate → compute phase proportions from fixed template (40% base, 30% threshold, 15% race-specific, 2 weeks taper, 1 week race-week) → assign phase labels, distributions, specificity, approach, recovery cycle per phase → schedule checkpoints
   - **target_performance mode**: estimate current performance from twin state → compute gap percentage → classify gap → compute estimated weeks to target → set system-determined target date → use same phase template with gap-driven timeline → schedule checkpoints with trajectory tracking
6. Generates phase definitions (`PhaseDefinition[]`) per the architecture schema
7. Computes weekly distributions from phase definitions (deterministic expansion)
8. For each week, synthesises `WeeklySession[]` respecting:
   - Athlete's `weekly_schedule` availability
   - Session count from phase template + athlete max availability
   - Structural rules: no consecutive quality sessions unless block, long run rest recovery, threshold sandwiching
   - Checkpoint placement from checkpoint schedule
9. Creates `PlannedSession` records mirroring the `WeeklySession` schedule with:
   - `weekly_plan_id` → parent WeeklyPlan
   - `training_plan_id` → denormalized (copied from WeeklyPlan.training_plan_id)
   - `checkpoint_type` / `checkpoint_metric` set for checkpoint sessions
   - `status = 'scheduled'`
   - `session_slot` and `session_priority` assigned per day
10. Creates `Checkpoint` records for each checkpoint session:
    - `planned_session_id` → the PlannedSession flagged as checkpoint
    - `status = 'scheduled'`
    - `type`, `target_metric`, `secondary_metrics` from checkpoint schedule
11. Supersedes any existing active plan for the same TrainingGoal atomically
12. Inserts TrainingPlan, all WeeklyPlans, all WeeklySessions, all PlannedSessions, all Checkpoints in a single transaction
13. Publishes `training_plan_generated` event via the transactional outbox (same transaction)
14. Commits

The service raises domain exceptions for invalid inputs:
- `PlanGenerationError` — base class for plan generation failures
- `TrainingLengthGateError` — training length gate fails (goal too far or fitness insufficient)
- `InvalidGoalTypeError` — unsupported goal type (reused from onboarding)

### Step 3 — Plan Generation Templates (Internal)
[OWNER: Coder]

The deterministic templates live inside `PlanGenerationService` as private methods or a dedicated internal module `app/services/plan_generation_templates.py`.

**Race Event Phase Template:**

| Phase | Proportion | Min Weeks | Session Types |
|-------|-----------|-----------|---------------|
| Base | 40% | 4 | easy_run, recovery_run, long_run, tempo |
| Build (Threshold) | 30% | 3 | easy_run, threshold, long_run, interval |
| Race Specific | 15% | 2 | race_pace, tempo, interval, long_run |
| Taper | 2 weeks (fixed) | 2 | easy_run, strides, race_pace |
| Race Week | 1 week (fixed) | 1 | easy_run, rest, race |

**Session Distribution Rules:**
- 4–6 sessions per week based on athlete `weekly_schedule.available` days
- One rest day per week minimum
- Long run on the day marked `long_workout` in preferences
- No quality session (threshold, interval, race_pace, tempo) on consecutive dates unless they form a block
- Threshold / vo2max sessions always have an easy or rest day before and after
- Recovery or rest day immediately after long run

**Checkpoint Scheduling Algorithm:**
- **Calibration**: at phase transitions and when `TwinState.metric_confidence` is LOW for a key metric (LT1, LT2, cp, vo2max)
- **Benchmark**: at the 4-week mark and at the start of each new phase after base
- **Progress review**: every 3–4 weeks at regular intervals
- **Race simulation**: in the race-specific phase, 2–3 weeks before the goal event
- No two checkpoints in the same week
- No checkpoint on the first or last day of a phase (buffer days)

**Target Performance Additions:**
- Phase proportions follow the same template; only the timeline computation differs (gap-driven vs date-driven)
- Checkpoint descriptors include `trajectory_status` and `proposal` fields (initially null, populated at checkpoint completion)

### Step 4 — Plan Response Schemas
[OWNER: Coder]

Introduce Pydantic response schemas in a new file `app/schemas/plan.py`:

- **`PhaseDescriptorResponse`** — label, start_date, end_date, weeks, primary_focus, weekly_session_count
- **`TrainingPlanResponse`** — id, training_goal_id, twin_state_id, phases (PhaseDescriptorResponse[]), phase_definitions, weekly_distributions, status, strategic_rationale, checkpoint_schedule, created_at
- **`PlannedSessionResponse`** — id, weekly_plan_id, training_plan_id, target_date, week_number, phase_label, session_type, intent_description, approximate_duration_minutes, checkpoint_type, checkpoint_metric, status, session_slot, session_priority, is_suggested
- **`CheckpointResponse`** — id, planned_session_id, type, target_metric, secondary_metrics, twin_update_expected, replan_trigger, status, trajectory_status, proposal, created_at
- **`UpcomingSessionsResponse`** — sessions (PlannedSessionResponse[]), limited to next 5

All schemas with `from_attributes = True` for direct ORM-to-response mapping. Register in `app/schemas/__init__.py`.

### Step 5 — Plan Router + Endpoints
[OWNER: Coder]

Create `app/api/v1/plan.py` with a new `plan_router` (prefix=`/athletes`, tags=`["plan"]`).

Four read-only endpoints, all behind `require_self` and `get_current_athlete_id`:

1. **`GET /athletes/{athlete_id}/plan`** → `TrainingPlanResponse`
   - Queries the active TrainingPlan for the athlete's active TrainingGoal
   - Returns 404 if no active goal or no active plan
   - Auth: Bearer JWT, require_self

2. **`GET /athletes/{athlete_id}/plan/sessions`** → `list[PlannedSessionResponse]`
   - Returns all PlannedSessions for the active TrainingPlan (joins through WeeklyPlan)
   - Returns 404 if no active plan
   - Auth: Bearer JWT, require_self

3. **`GET /athletes/{athlete_id}/plan/upcoming`** → `list[PlannedSessionResponse]`
   - Returns the next 5 PlannedSessions from today onwards, ordered by target_date, session_slot
   - Returns 404 if no active plan
   - Auth: Bearer JWT, require_self

4. **`GET /athletes/{athlete_id}/plan/checkpoints`** → `list[CheckpointResponse]`
   - Returns all Checkpoints for the active TrainingPlan (joins through PlannedSession → WeeklyPlan)
   - Returns 404 if no active plan
   - Auth: Bearer JWT, require_self

All endpoints map `PlanGenerationError` subtypes to appropriate HTTP status codes. No mutations — read-only.

### Step 6 — Wire Plan Service + Router
[OWNER: Coder]

Extend the existing service-wiring and dependency-injection layer:

- Add `PlanGenerationService` to `app/services/__init__.py` exports
- Add a `build_plan_service` factory in `app/api/deps.py` following the `build_onboarding_service` pattern (injects session, all required repositories, EventPublisher)
- Register `plan_router` in `app/api/v1/__init__.py` (include alongside existing auth_router, onboarding_router, health_router)
- Export `plan_router` from `app/api/v1/__init__.py`

The `PlanGenerationService` is also called from `OnboardingService.complete_onboarding` at the end of the onboarding transaction — after the TrainingGoal and TwinState are committed — to generate the initial plan within the same transaction. This requires `OnboardingService` to accept a `PlanGenerationService` dependency.

### Step 7 — Trigger Plan Generation at Onboarding
[OWNER: Coder]

Modify `OnboardingService.complete_onboarding` to invoke `PlanGenerationService.generate_plan()` at the end of the onboarding transaction, after the `TrainingGoal` and `TwinState` have been flushed but before the commit. This ensures:
- The plan generation has access to the committed `TrainingGoal` and `TwinState` (via their IDs)
- The plan and onboarding are atomic — if plan generation fails, onboarding rolls back and `onboarding_complete` remains `False`
- The `training_plan_generated` event is persisted in the same transaction as `onboarding_completed`

The `PlanGenerationService` is injected as an optional dependency (defaults to `None` for backward compatibility with existing tests). When `None`, plan generation is skipped (graceful degradation for unit tests that don't exercise the plan path).

### Step 8 — Migration
[OWNER: Coder]

Generate an Alembic revision for any schema changes required by this sub-phase. The existing `training_plans`, `weekly_plans`, `weekly_sessions`, `planned_sessions`, and `checkpoints` tables were created in Phase-1.2b. Verify that:
- All JSONB columns have appropriate defaults
- All indexes support the query patterns (active plan lookup, weekly plan by plan+week, checkpoint by planned_session)
- The `training_plans.training_goal_id` FK supports the active-plan lookup path

If the existing tables are sufficient, this step is a no-op (no new migration needed). If any index or column is missing, generate the revision.

**[OWNER: DevOps]** Review the Alembic revision after the coder generates it. Augment for hypertable or extension requirements if needed. Apply to the test database.

### Step 9 — Tests
[OWNER: Test Architect]

Create test manifest `tests/test-manifest/phase-1-4.yaml` covering:

**Plan Generation Service tests (unit):**
- Race event plan generates correct phase proportions (40/30/15 + 2 weeks taper + 1 week race)
- Target performance plan computes correct timeline from gap analysis
- Training length gate rejects goals too far in the future
- Training length gate rejects goals with insufficient fitness for distance
- No two consecutive quality sessions in any generated week
- Long run always followed by rest or recovery_run in any week
- Threshold/vo2max sessions always sandwiched between easy/rest days
- Phase date ranges are non-overlapping and contiguous
- Checkpoints scheduled at phase transitions and regular intervals
- No checkpoint on first or last day of a phase
- Supersession: generating a new plan for the same goal marks the old plan as superseded atomically
- Old plan's `superseded_at` is set; old plan is never deleted

**API endpoint tests (integration):**
- `GET /plan` returns TrainingPlan with correct phase sequence for goal_type
- `GET /plan/sessions` returns PlannedSessions covering full duration to goal event
- `GET /plan/upcoming` returns next 5 sessions from today
- `GET /plan/checkpoints` returns scheduled checkpoints
- All endpoints return 404 when no active plan exists
- All endpoints require `require_self` authorization
- All endpoints return 403 for mismatched athlete_id

**End-to-end journey test:**
- Onboarding → plan generation → GET /plan returns valid plan with phases

## Event Contracts

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `training_plan_generated` | Plan inserted atomically with full hierarchy | v1 | `{training_plan_id, training_goal_id, phase_definitions_count, total_weeks, supersedes_plan_id, trigger}` |

The event is persisted via the transactional outbox (SystemEvent + SystemEventOutbox) inside the same DB transaction as the plan inserts, per ADR-004. Publication to the message bus is not the concern of this sub-phase.

### Consumed
None in Phase 1.4. The `twin_model_ready` event is consumed in later phases when LLM-driven generation replaces the current template-based path.

### Ordering Assumptions
- `training_plan_generated` fires only after `athlete_registered` (auth) and `onboarding_completed` (onboarding), because the plan requires an onboarded athlete with a `TwinState` and `TrainingGoal`.

## Pseudocode
```
  PlanGenerationService.generate_plan(athlete_id, training_goal_id):
    → load latest TwinState for athlete
    → load active TrainingGoal by id
    → load AthletePreferences for athlete
    → validate goal_type ∈ {race_event, target_performance}

    → if goal_type == race_event:
        → evaluate training_length_gate(weeks_until_goal, fitness_level, event_type, experience)
        → if gate action ≠ proceed → raise TrainingLengthGateError
        → compute phase_definitions from race_event template (40/30/15 + taper + race-week)
        → assign start_date and end_date per phase (contiguous, non-overlapping)
        → compute weekly_distributions via deterministic expansion of phase_definitions
        → schedule checkpoints (calibration, benchmark, progress_review)

      elif goal_type == target_performance:
        → estimate current_performance from twin_state + target_distance
        → compute gap_percentage = (target_time - current_estimate) / current_estimate
        → classify gap: small / medium / large / very_large
        → estimate weeks_to_target from gap classification + fitness_level
        → set system_determined_goal_date = today + weeks_to_target
        → compute phase_definitions from target_performance template (same proportions)
        → compute weekly_distributions
        → schedule checkpoints with trajectory_status tracking fields

    → for each week 1..total_weeks:
        → derive session count from athlete availability + phase template
        → synthesize WeeklySession[] for the week:
            → place long_run on preferred long_workout day
            → distribute quality sessions (threshold, interval, race_pace) with rest buffers
            → ensure no consecutive quality sessions without block_id
            → ensure threshold/vo2max sandwiched between easy/rest
            → set checkpoint flags on checkpoint sessions
        → create WeeklyPlan record with adjusted_intent and sessions
        → create PlannedSession records for each WeeklySession
            → copy training_plan_id (denormalized)
            → set checkpoint_type/metric where applicable
            → status = 'scheduled'
        → create Checkpoint records for checkpoint sessions

    → supersede existing active plan for same TrainingGoal (if any):
        → set old_plan.status = 'superseded'
        → set old_plan.superseded_at = now()
    → insert TrainingPlan, all WeeklyPlans, all PlannedSessions, all Checkpoints
    → persist training_plan_generated event to outbox
    → commit
```

## Testing Requirements
- After `complete_onboarding` with `goal_type = race_event`, `GET /athletes/{id}/plan` returns a `TrainingPlan` with a phase sequence ending in taper + race-week, total weeks matching the goal distance and time constraint.
- Phase definitions cover the full duration from today to `goal_event_date` without gaps or overlaps.
- No two consecutive quality sessions (`threshold`, `vo2max`, `tempo`, `interval`, `race_pace`) appear on consecutive dates in any generated week, unless they share a `block_id`.
- Long run session is followed by `rest` or `recovery_run` in every week.
- Threshold and vo2max sessions have `easy_run`, `recovery_run`, or `rest` on the day before and after.
- `GET /athletes/{id}/plan/checkpoints` returns at least one `calibration` checkpoint, one `benchmark` checkpoint, and one `progress_review` checkpoint for a 16+ week plan.
- All `PlannedSession` records have `status = 'scheduled'`.
- All `Checkpoint` records have `status = 'scheduled'`.
- `GET /athletes/{id}/plan/upcoming` returns a non-empty list of 5 or fewer sessions with `target_date >= today`.
- Generating a plan for the same `TrainingGoal` twice causes the first plan's `status` to become `superseded` and `superseded_at` to be non-null.
- `GET /plan`, `GET /plan/sessions`, `GET /plan/upcoming`, `GET /plan/checkpoints` all return 404 when no active plan exists.
- All plan endpoints return 403 when `athlete_id` in the JWT does not match the path parameter.

## Coder Handoff Notes

```
## Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8  [OWNER: Coder] — includes migration generation
Skip:     Step 8 (DevOps — migration review and application),
          Step 9 (Test Architect — tests)
```

- **Pure Python, no LLM.** The sub-phase document is explicit: `PlanGenerationService` is a pure Python service. Do not introduce any LLM call, external API, or agent invocation anywhere in the plan generation path. The architecture describes LLM-driven hypothesis generation for a future phase; Phase 1.4 uses deterministic templates only.
- **Atomic plan generation.** The entire plan hierarchy (TrainingPlan + WeeklyPlans + WeeklySessions + PlannedSessions + Checkpoints) must be created in a single database transaction. Use the existing `AsyncSession` pattern — session.flush() for each insert, session.commit() once at the end.
- **Supersession atomicity.** When generating a plan for a TrainingGoal that already has an active plan, mark the old plan as superseded and insert the new plan in the same transaction. The service layer owns the transaction; repositories only flush.
- **Denormalized `training_plan_id` on PlannedSession.** When creating PlannedSession records, copy `weekly_plan.training_plan_id` into `planned_session.training_plan_id`. This is intentionally denormalized for query performance. Document the staleness risk in the repository layer.
- **Correct query pattern for current sessions.** `GET /plan/sessions` and `GET /plan/upcoming` MUST join through `WeeklyPlan.training_plan_id` to find the active plan's sessions, not filter `PlannedSession.training_plan_id` directly (which may be stale after supersession).
- **Checkpoint-PlannedSession one-to-one.** Every Checkpoint record points to exactly one PlannedSession via `planned_session_id`. Create the PlannedSession first, then create the Checkpoint pointing at it. The PlannedSession's `checkpoint_type` and `checkpoint_metric` fields must also be set.
- **Structural rules are hard constraints.** The session distribution algorithm must enforce: no consecutive quality sessions without block_id, long run followed by rest/recovery, threshold/vo2max sandwiched between easy/rest. These are not coaching preferences — they are architecture invariants.
- **`strategic_rationale` is populated.** For `race_event` and `target_performance` modes, the `strategic_rationale` field on TrainingPlan must contain `primary_driver`, `methodology_summary`, and `risk_notes`. These are short deterministic strings derived from the template, not LLM-generated content. Internal hypothesis names must not be persisted.
- **Event outbox pattern.** The `training_plan_generated` event follows the ADR-004 pattern: SystemEvent + SystemEventOutbox rows inserted in the same transaction as the plan. Use the existing `EventPublisher` infrastructure.
- **Onboarding integration.** After OnboardingService commits the TrainingGoal and TwinState (flush, before commit), invoke PlanGenerationService.generate_plan(). If plan generation fails, the onboarding transaction rolls back — `onboarding_complete` remains `False`.
- **Test manifest.** The Test Architect owns test creation (Step 9). Do not write test files — focus on the service, repositories, API endpoints, and schemas.
- **File placement.** Follow the established project conventions:
  - Repositories → `app/repositories/plan_generation_repository.py` (or split per entity if that matches existing patterns; the existing codebase has one-repo-per-entity)
  - Service → `app/services/plan_generation_service.py`
  - Schemas → `app/schemas/plan.py`
  - API → `app/api/v1/plan.py`
  - Errors → `app/services/plan_generation_errors.py` (or inline in the service file)
