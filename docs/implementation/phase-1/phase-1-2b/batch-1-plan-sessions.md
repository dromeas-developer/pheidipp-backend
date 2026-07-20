> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md` + `phase-1-2b-p2-test-contract-alignment.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-2b, including post-review test alignment, verified against the current codebase on 2026-07-19.

## Batch Objective

Implement the Phase 1-2b schema-only foundation for the training plan hierarchy: `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, `PlannedSession`, and `Checkpoint`, plus supporting tables (`SecondaryEvent`, `RegenerationTask`) and the enums required by those contracts. Wire the existing Phase 1-2a `Activity.planned_session_id` column to the new `planned_sessions` table. This plan does not implement plan generation, onboarding writes, session lifecycle, workout generation, FIT import, APIs, services, or event publication.

## Preconditions

- Phase 1-2a migration is applied (head `e7ffc8764335`): `Activity`, `AthleteProfile`, `AthletePreferences` exist
- `Activity.planned_session_id` exists as a nullable UUID but has no FK target yet
- `training_plans.twin_state_id` FK is deferred to Phase 1-2c (TwinState doesn't exist yet)

## Scope

- Add plan/session/checkpoint persistence models
- Add closed-domain enums: `GoalType`, `GoalEventType`, `TrainingGoalStatus`, `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel`, `SessionType`, `SessionSlot`, `SessionPriority`, `PlannedSessionStatus`, `WeeklyPlanStatus`, `CheckpointType`, `CheckpointStatus`, `InjurySeverity`, `ObjectiveCategory`
- Add `SecondaryEvent` and `RegenerationTask` supporting tables
- Create Alembic migration for all tables, constraints, indexes, and enums
- Add FK from `activities.planned_session_id` to `planned_sessions.id`
- Defer `training_plans.twin_state_id` FK to Phase 1-2c
- Test alignment: schema-scoped catalog query helpers, predicate format normalization for partial indexes, phase-scoped FK assertions

## Out Of Scope

- Plan generation logic, phase synthesis, weekly synthesis, checkpoint scheduling
- Onboarding writes, public APIs, repositories, services, tasks, agents
- Event production or consumption
- `training_plans.twin_state_id` FK (deferred to 1-2c)
- DB-level enforcement of `fit_file_key` or `timezone` immutability

## Steps

1. [OWNER: Coder] Add plan/session/checkpoint enums to `app/models/enums.py` with exact values from `00-foundations/terminology.md`: `GoalType` (race_event, target_performance, fitness_improvement, maintenance, recovery), `GoalEventType`, `TrainingGoalStatus`, `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel` (17 main + 3 legacy aliases), `SessionType` (16 values), `SessionSlot`, `SessionPriority`, `PlannedSessionStatus`, `WeeklyPlanStatus`, `CheckpointType`, `CheckpointStatus`, `InjurySeverity`, `ObjectiveCategory`.

2. [OWNER: Coder] Add persistence models:
   - `TrainingGoal` — athlete_id, immutable semantic fields, mutable status, partial unique index on `(athlete_id) WHERE status = 'active'`
   - `SecondaryEvent` — FK to training_goals, indexes for goal/date lookup
   - `RegenerationTask` — FK to training_goals, nullable FK to training_plans, pending-task index
   - `TrainingPlan` — FK to training_goals, nullable `twin_state_id` (no FK yet), JSONB phase/weekly fields, status/supersession
   - `WeeklyPlan` — FK to training_plans, unique `(training_plan_id, week_number)`, JSONB adjusted_intent, execution counters
   - `WeeklySession` — FK to weekly_plans, nullable unique `planned_session_id`, date/session/block fields
   - `PlannedSession` — FK to weekly_plans, denormalized FK to training_plans, unique `(weekly_plan_id, target_date, session_slot)`, lifecycle/activity/slot/priority/block fields
   - `Checkpoint` — one-to-one FK to planned_sessions (non-null, unique), no redundant training_plan_id, status/completion/trajectory fields

3. [OWNER: Coder] Extend `Activity` model: add FK from `planned_session_id` to `planned_sessions.id`. Keep nullable semantics.

4. [OWNER: Coder] Register all new models and enums in `app/models/__init__.py`.

5. [OWNER: Coder] Create Alembic migration from head `e7ffc8764335`: create all 8 tables with constraints and indexes, add `activities.planned_session_id` FK, defer `training_plans.twin_state_id` FK. Verify downgrade path.

### Remediation: Test Contract Alignment

R1. [OWNER: Coder] Add schema-scoped PostgreSQL catalog helpers for migration tests — filter `pg_constraint`, `pg_indexes`, and FK assertions by `pg_namespace` bound to the isolated test schema.

R2. [OWNER: Coder] Update unique-constraint tests (`uq_weekly_plans_plan_week`, `uq_planned_sessions_plan_date_slot`, `checkpoints.planned_session_id`) to assert exactly one constraint in the isolated schema.

R3. [OWNER: Coder] Update `training_goals` partial-index predicate assertion to accept PostgreSQL's rendered form for `native_enum=False` enum-backed VARCHAR columns (both raw `status = 'active'` and casted `((status)::text = 'active'::text)`).

R4. [OWNER: Coder] Update FK catalog assertions for `fk_activities_planned_session` — filter by isolated schema, assert `confdeltype='n'` (NO ACTION), verify zero FK rows after downgrade.

R5. [OWNER: Coder] Phase-scope the legacy Phase 1-2a Activity FK assertion: it must either run against the 1-2a baseline only or be updated to the 1-2b FK expectation.

R6. [OWNER: Coder] Confirm `RegenerationTask` deletion test observes `training_plan_id IS NULL` in the same schema-scoped transaction where `ON DELETE SET NULL` is defined.

## Context Needed

- `01-entities/training-goal.md` — goal schema, active-goal invariant
- `01-entities/training-plan.md` — plan schema, supersession, twin linkage
- `01-entities/weekly-plan.md` — weekly plan + WeeklySession schemas
- `01-entities/planned-session.md` — planned session schema, denormalized training_plan_id
- `01-entities/checkpoint.md` — checkpoint schema, one-to-one with planned_session
- `01-entities/activity.md` — existing Activity model (FK target)
- `00-foundations/terminology.md` — exact enum values
- `docs/vision/product/plan-generation.md` — phase arc vs weekly/session detail
- `docs/vision/product/training-plan-checkpoints.md` — checkpoint hierarchy
- `docs/implementation/implemented-state.md` — Phase 1-2a state

## Batch Success Criteria

- `alembic upgrade head` succeeds from Phase 1-2a head
- `alembic downgrade e7ffc8764335` succeeds and leaves Phase 1-2a schema intact
- `training_goals` has partial unique index on `(athlete_id) WHERE status = 'active'`
- `weekly_plans` has unique `(training_plan_id, week_number)`
- `planned_sessions` has unique `(weekly_plan_id, target_date, session_slot)`
- `checkpoints.planned_session_id` is non-null and unique
- `checkpoints` has no redundant `training_plan_id` column
- `weekly_sessions.planned_session_id` is unique when non-null
- `activities.planned_session_id` has FK to `planned_sessions.id` and remains nullable
- `training_plans.twin_state_id` exists as nullable column with no FK yet
- All enum values match terminology.md and architecture contracts
- No public APIs, services, repositories, or event publishers added
- Placeholder `intent_description` column present on `PlannedSession` (not `coach_note`)
- All test catalog queries are schema-scoped (remediation)
- Partial index predicate accepts PostgreSQL's rendered form (remediation)
- FK `confdeltype` assertions filter by isolated schema (remediation)

## Files Expected To Change

- `app/models/enums.py` — add 15 new enums
- `app/models/training_goal.py` — new model
- `app/models/training_plan.py` — new model
- `app/models/weekly_plan.py` — new model (includes WeeklySession)
- `app/models/planned_session.py` — new model
- `app/models/checkpoint.py` — new model
- `app/models/secondary_event.py` — new supporting model
- `app/models/regeneration_task.py` — new supporting model
- `app/models/activity.py` — add FK to planned_sessions
- `app/models/__init__.py` — register new models + enums
- `migrations/versions/<rev>_phase_1_2b_plan_sessions.py` — new migration
- `tests/integration/test_phase_1_2b_schema.py` — new schema tests (remediation alignment)

## Coder Notes

- **Schema-only**. No plan generation, services, repositories, APIs, or events.
- **`training_plans.twin_state_id` FK is deferred**. Column exists but FK must wait for `twin_states` (Phase 1-2c). Add a docstring marker noting the deferral.
- **Denormalised `PlannedSession.training_plan_id`**. Future queries for current-plan sessions must join through `WeeklyPlan.training_plan_id`, not filter `PlannedSession.training_plan_id` directly.
- **`Checkpoint` has no `training_plan_id`**. Derive through `PlannedSession → WeeklyPlan → TrainingPlan`. Do not add a redundant FK.
- **`weekly_sessions.planned_session_id` is lazy-linked**. Nullable unique column — populated when the planned session is created later by plan generation.
- **Active-goal partial index predicate**. PostgreSQL may render `native_enum=False` VARCHAR-backed enum predicates with casts. Tests must accept both forms (remediation R3).
- **Test catalog isolation**. Tests querying `pg_constraint`/`pg_indexes` must filter by the test schema namespace to avoid picking up constraints from other test schemas or the public schema (remediation).
