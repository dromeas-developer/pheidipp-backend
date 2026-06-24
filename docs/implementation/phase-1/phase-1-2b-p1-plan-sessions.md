# Implementation Plan: Phase-1.2b — Training Plan and Session Schema
## Plan ID: Phase-1.2b-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.2b
Sub-Phase Title: Phase 1 — Core Models: Plan & Sessions

## Objective
Implement the Phase-1.2b schema-only foundation for the training plan hierarchy: `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, `PlannedSession`, and `Checkpoint`, plus the schema support required by those contracts. This plan wires the existing Phase-1.2a `Activity.planned_session_id` column to the new `planned_sessions` table, but does not implement plan generation, onboarding writes, session lifecycle, workout generation, FIT import, APIs, services, or event publication.

## Scope
- Add plan/session/checkpoint persistence models and register them through the existing model package.
- Add the closed-domain enums required by the plan/session/checkpoint schemas, including `GoalType`, `GoalEventType`, `TrainingGoalStatus`, `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel`, `SessionType`, `SessionSlot`, `SessionPriority`, `PlannedSessionStatus`, `WeeklyPlanStatus`, `CheckpointType`, and `CheckpointStatus`.
- Add schema support for `SecondaryEvent` and `RegenerationTask` where required by the `TrainingGoal` storage model, without implementing secondary-event or regeneration services.
- Create the Alembic migration from current Phase-1.2a head `e7ffc8764335` to add the plan/session/checkpoint tables, constraints, indexes, and enums.
- Add the foreign key from existing `activities.planned_session_id` to `planned_sessions.id`, preserving the nullable column semantics.
- Add schema and migration tests proving the Phase-1.2b exit gate and preserving Phase-1.2a behaviour.

## Out Of Scope
- Plan generation logic, including phase synthesis, weekly synthesis, checkpoint scheduling, or deterministic expansion.
- Onboarding writes that create `TrainingGoal`, `TwinState`, or `AthleteProfile` enrichment fields.
- Public API routes or response schemas for goals, plans, sessions, or checkpoints.
- Services, repositories, tasks, or agents for plan generation, session lifecycle, workout generation, missed-session sweeps, FIT import, or checkpoint completion.
- Event production or consumption.
- DB-level enforcement of `Activity.fit_file_key` for non-`manual_entry` sources; this remains a Phase-1.6 service-layer invariant.
- DB-level immutability or requiredness for `AthleteProfile.timezone`; this remains a Phase-1.3 onboarding-write invariant.
- Adding a `training_plans.twin_state_id` foreign key before the `twin_states` table exists in Phase-1.2c.

## Architecture Contracts
- `01-entities/training-goal.md` — IMPLEMENTS the `TrainingGoal` schema, supporting `SecondaryEvent` and `RegenerationTask` storage tables, enums, indexes, and constraints.
- `01-entities/training-plan.md` — IMPLEMENTS the `TrainingPlan` schema and depends on `TrainingGoal`; `twin_state_id` column is present but its FK is deferred until `TwinState` exists.
- `01-entities/weekly-plan.md` — IMPLEMENTS the `WeeklyPlan` and `WeeklySession` schemas, including weekly-plan uniqueness and lazy `planned_session_id` linkage.
- `01-entities/planned-session.md` — IMPLEMENTS the `PlannedSession` schema, denormalized `training_plan_id`, checkpoint metadata fields, slot/priority/block fields, and indexes.
- `01-entities/checkpoint.md` — IMPLEMENTS the `Checkpoint` schema and one-to-one `planned_session_id` constraint.
- `01-entities/activity.md` — DEPENDS ON existing `Activity` and extends it by adding the `planned_sessions` FK to the existing nullable `planned_session_id` column.
- `00-foundations/terminology.md` — DEPENDS ON exact enum values for `GoalType`, `GoalEventType`, `PhaseLabel`, `SessionType`, `SessionSlot`, `SessionPriority`, `CheckpointType`, `ObjectiveCategory`, and related closed ontologies.
- `docs/vision/product/plan-generation.md` — DEPENDS ON the strategic roadmap concept and the separation between phase arc and weekly/session detail.
- `docs/vision/product/training-plan-checkpoints.md` — DEPENDS ON checkpoint hierarchy, scheduling rationale, and completion semantics.
- `docs/vision/coach/plan-visibility.md` — DEPENDS ON what the plan/session/checkpoint schema must make visible to the athlete later.
- `docs/implementation/implemented-state.md` — DEPENDS ON Phase-1.2a having created `Activity`, `AthleteProfile`, `AthletePreferences`, current model registrations, and migration head `e7ffc8764335`.
- `docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity_validation.md` — DEPENDS ON the two minor findings that remain deferred and must not be silently reinterpreted here.

## Invariants
- `TrainingGoal`: one active per athlete (partial unique index on `athlete_id WHERE status = 'active'`).
- `TrainingGoal` fields `goal_type`, `goal_event_type`, `fitness_level`, etc. are immutable after creation.
- `TrainingPlan` is never deleted — `superseded_at` is set when replaced.
- `WeeklyPlan`: one per `(training_plan_id, week_number)`. Sessions array is immutable once `status = active`.
- `PlannedSession` records for a superseded `TrainingPlan` retain the old `training_plan_id` — queries for "current plan sessions" must join through `WeeklyPlan`.
- `Checkpoint` cannot be created retroactively — scheduled during plan synthesis.
- `Checkpoint` completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) are set atomically.
- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.
- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields do not exist on `Activity`. They are never added.

## Implementation Steps
1. Add the plan/session/checkpoint enums to the existing enum module, using the exact values from `00-foundations/terminology.md` and the architecture schemas:
   - Goal and plan enums: `GoalType`, `GoalEventType`, `TrainingGoalStatus`, `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel`, and `InjurySeverity`.
   - Session enums: `SessionType`, `SessionSlot`, `SessionPriority`, `PlannedSessionStatus`.
   - Weekly/checkpoint enums: `WeeklyPlanStatus`, `CheckpointType`, `CheckpointStatus`.
   - Shared plan-generation enum: `ObjectiveCategory`.
   - Do not add non-canonical aliases or legacy enum values except where `PhaseLabel` explicitly defines legacy aliases and their expansion meaning.

2. Add persistence models for the plan/session/checkpoint hierarchy:
   - `TrainingGoal` with athlete ownership, immutable semantic fields, mutable status fields, and the active-goal partial uniqueness contract.
   - `SecondaryEvent` as the supporting table named by the `TrainingGoal` storage model.
   - `RegenerationTask` as the supporting table named by the `TrainingGoal` storage model, with schema and indexes only.
   - `TrainingPlan` with `training_goal_id`, nullable `twin_state_id`, phase/weekly distribution JSONB fields, status/supersession fields, strategic rationale, and checkpoint schedule.
   - `WeeklyPlan` with `training_plan_id`, `week_number`, adjusted intent JSONB, status, execution counters, fatigue delta, doubles count, and date bounds.
   - `WeeklySession` with `weekly_plan_id`, target date/type/intent/duration, checkpoint flags, status, nullable `planned_session_id`, and block membership fields.
   - `PlannedSession` with `weekly_plan_id`, denormalized `training_plan_id`, target date, week/phase/session fields, checkpoint metadata, lifecycle fields, activity linkage, slot/priority, and block membership fields.
   - `Checkpoint` with one-to-one `planned_session_id`, type, target metric, expected outcome flags, status, completion fields, trajectory fields, and timestamps.

3. Extend the existing `Activity` model to reference `PlannedSession` once the model exists:
   - Keep `planned_session_id` nullable.
   - Add the relationship/FK metadata to `planned_sessions.id` without changing the column name or adding placeholder session tables.
   - Preserve all Phase-1.2a Activity invariants, including the absence of workout-summary fields.

4. Register all new models and enums through the existing model package so Alembic metadata discovery includes the new tables and enum types without changing auth/profile/activity registrations from Phase-1.2a.

5. Create the Phase-1.2b Alembic migration from head `e7ffc8764335`:
   - Create `training_goals` with active-goal partial unique index and schema checks for non-negative volume fields, `fitness_level` range, and positive target/custom distance/time fields where applicable.
   - Create `secondary_events` with FK to `training_goals` and indexes for goal/date lookup.
   - Create `regeneration_tasks` with FK to `training_goals`, nullable FK to `training_plans` for confirmed regeneration, and pending-task index.
   - Create `training_plans` with FK to `training_goals`, nullable `twin_state_id` column, status/superseded fields, JSONB phase and weekly distribution fields, and indexes for active/current plan queries.
   - Create `weekly_plans` with FK to `training_plans`, unique `(training_plan_id, week_number)`, status/execution fields, and indexes for plan-week lookup.
   - Create `weekly_sessions` with FK to `weekly_plans`, nullable unique `planned_session_id` when non-null, date/session fields, and indexes for weekly session lookup.
   - Create `planned_sessions` with FK to `weekly_plans`, denormalized FK to `training_plans`, uniqueness for `(weekly_plan_id, target_date, session_slot)` including the single-session null-slot case, and indexes for plan/session retrieval.
   - Create `checkpoints` with one-to-one FK to `planned_sessions`, no redundant `training_plan_id`, status/completion fields, and indexes for planned-session and type/status lookup.
   - Add the existing `activities.planned_session_id` FK to `planned_sessions.id` while preserving nullable semantics.
   - Do not add a FK from `training_plans.twin_state_id` to `twin_states.id`; add that FK in Phase-1.2c after `TwinState` exists.

6. Add schema and migration tests that directly inspect database objects and model metadata:
   - Fresh `alembic upgrade head` succeeds from the Phase-1.2a head.
   - Downgrade from the new head to `e7ffc8764335` succeeds without orphaned constraints or indexes.
   - `training_goals` has the active-goal partial unique index and required schema checks.
   - `weekly_plans` has unique `(training_plan_id, week_number)`.
   - `checkpoints.planned_session_id` is unique and non-null.
   - `weekly_sessions.planned_session_id` is unique when non-null.
   - `planned_sessions` enforces the intended slot/date uniqueness semantics.
   - `activities.planned_session_id` has a FK to `planned_sessions.id` and remains nullable.
   - `training_plans.twin_state_id` exists as a nullable column but has no FK until Phase-1.2c.
   - Enum values match the architecture/terminology contracts, including `InjurySeverity` for `TrainingGoal.injury_severity`.
   - No plan/session/checkpoint APIs, services, repositories, tasks, agents, or event publishers are added.

## Event Contracts
This schema-only plan produces or consumes no events. The following event contracts remain architecture references for later implementation:

| Event | Relationship | Payload / Ordering Notes |
|---|---|---|
| `training_goal_created` | NOT PRODUCED | Would be produced when a goal is inserted with `status='active'`; no goal creation service exists in this plan. |
| `training_goal_closed` | NOT PRODUCED | Would be produced on goal closure; closure service is out of scope. |
| `secondary_event_registered` | NOT PRODUCED | Secondary event schema may exist, but registration service is out of scope. |
| `secondary_event_removed` | NOT PRODUCED | Removal service is out of scope. |
| `regeneration_task_proposed` | NOT PRODUCED | Regeneration service is out of scope. |
| `regeneration_task_confirmed` | NOT PRODUCED | Regeneration confirmation service is out of scope. |
| `training_plan_generated` | NOT PRODUCED | Plan generation service is Phase-1.4. |
| `weekly_plan_created` | NOT PRODUCED | Weekly synthesis is out of scope. |
| `week_completed` | NOT PRODUCED | Week completion detection is out of scope. |
| `planned_session_generated` | NOT PRODUCED | Workout generation is Phase-1.5b or later. |
| `session_completed` | NOT CONSUMED / NOT PRODUCED | Session lifecycle is Phase 4; schema only prepares linkage fields. |
| `session_skipped` | NOT PRODUCED | Session lifecycle is Phase 4. |
| `session_missed` | NOT PRODUCED | Missed-session sweep is out of scope. |
| `checkpoint_completed` | NOT PRODUCED / NOT CONSUMED | Checkpoint completion handling is out of scope. |
| `activity_ingested` | NOT CONSUMED | Existing `Activity` schema is linked by FK only; ingestion remains Phase-1.6. |
| `workout_generated` | NOT CONSUMED | Workout generation remains out of scope. |

## Pseudocode
```text
Phase-1.2b migration
  start from Phase-1.2a head e7ffc8764335
  create plan/session/checkpoint enums

  create training_goals
    enforce one active goal per athlete with partial unique index
    add schema checks for volume, fitness level, and target/custom distance/time

  create secondary_events
    FK to training_goals
    index by goal and event date

  create regeneration_tasks
    FK to training_goals
    nullable FK to training_plans
    index pending proposals by training_goal

  create training_plans
    FK to training_goals
    nullable twin_state_id column, no FK yet
    status/superseded fields
    JSONB phase and weekly distribution fields

  create weekly_plans
    FK to training_plans
    unique (training_plan_id, week_number)
    adjusted_intent JSONB and execution summary fields

  create weekly_sessions
    FK to weekly_plans
    nullable unique planned_session_id when non-null
    session date/type/intent/checkpoint/block fields

  create planned_sessions
    FK to weekly_plans
    denormalized FK to training_plans
    uniqueness for (weekly_plan_id, target_date, session_slot)
    lifecycle, activity, slot, priority, block fields

  create checkpoints
    one-to-one FK to planned_sessions
    no redundant training_plan_id
    status and completion fields

  alter activities
    add FK from planned_session_id to planned_sessions.id
    keep planned_session_id nullable

  register models/enums
```

## Testing Requirements
- `alembic upgrade head` succeeds on a fresh database starting from Phase-1.2a head `e7ffc8764335`.
- `alembic downgrade e7ffc8764335` succeeds and leaves the Phase-1.2a schema intact.
- Schema inspection confirms `training_goals.athlete_id` has a partial unique index where `status = 'active'`.
- Schema inspection confirms `training_goals` includes the required immutable semantic fields and mutable status/closure fields, with no goal creation API or service.
- Schema inspection confirms `weekly_plans` has a unique constraint/index on `(training_plan_id, week_number)`.
- Schema inspection confirms `weekly_sessions.planned_session_id` is unique when non-null and nullable by design.
- Schema inspection confirms `checkpoints.planned_session_id` is non-null and unique.
- Schema inspection confirms `checkpoints` has no redundant `training_plan_id` column.
- Schema inspection confirms `planned_sessions` has the denormalized `training_plan_id`, FK to `weekly_plans`, and slot/date uniqueness semantics.
- Schema inspection confirms `activities.planned_session_id` now references `planned_sessions.id` and remains nullable.
- Schema inspection confirms `training_plans.twin_state_id` exists as a nullable column but has no FK yet.
- Enum inspection confirms exact values for `GoalType`, `GoalEventType`, `TrainingGoalStatus`, `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel`, `InjurySeverity`, `SessionType`, `SessionSlot`, `SessionPriority`, `PlannedSessionStatus`, `WeeklyPlanStatus`, `CheckpointType`, `CheckpointStatus`, and `ObjectiveCategory`.
- Tests confirm `Activity` still has no `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns.
- Tests confirm no public API routes, services, repositories, tasks, agents, or event publishers were added for plan/session/checkpoint behaviour.
- Existing Phase-1.2a tests for `Activity`, `AthleteProfile`, `AthletePreferences`, and auth/profile registrations continue to pass.

## Coder Handoff Notes
- No implementation ADR is required; this plan follows the schema contracts directly.
- This is schema-only. Do not implement plan generation, onboarding writes, session lifecycle, workout generation, FIT import, public APIs, repositories, services, tasks, agents, or event publication.
- The Phase-1.2a validation minors are carried forward as deferred DB-level enforcement, not implementation errors:
  - `fit_file_key` remains nullable for non-`manual_entry` sources in the DB schema. The invariant is still true at the service boundary, but enforcement belongs to Phase-1.6 FIT import. Do not add a DB CHECK or trigger here.
  - `AthleteProfile.timezone` remains nullable and mutable at the DB layer. The invariant is enforced by onboarding writes in Phase-1.3. Do not add a DB immutability trigger or make the column non-null in this plan.
- `training_plans.twin_state_id` must be present now because `TrainingPlan` records which twin version generated the plan, but its FK must wait for Phase-1.2c because `TwinState` does not exist yet.
- Do not create a placeholder `planned_sessions` table in any future Activity migration; this plan owns that table and the FK from `activities.planned_session_id`.
- Do not add a redundant FK from `checkpoints` to `training_plans`; `Checkpoint.training_plan_id` is derived through `PlannedSession → WeeklyPlan → TrainingPlan`.
- The `Checkpoint` / `PlannedSession` circular-reference risk is resolved by schema shape: `PlannedSession` stores checkpoint metadata, and `Checkpoint` is created atomically with the planned session later by plan generation.
- Preserve the denormalisation warning: `PlannedSession.training_plan_id` can be stale after plan supersession. Future queries for current-plan sessions must join through `WeeklyPlan.training_plan_id`.
- Ownership remains singular: this plan owns schema/migration/model registration only. Later phases own services, agents, APIs, and event orchestration.
