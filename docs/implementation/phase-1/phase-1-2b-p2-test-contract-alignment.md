# Implementation Plan: Phase-1.2b-P2 — Schema Test Contract Alignment
## Plan ID: Phase-1.2b-P2

## Sub-Phase Reference
Sub-Phase ID: Phase-1.2b
Sub-Phase Title: Phase 1 — Core Models: Plan & Sessions

## Objective
Align the Phase-1.2b catalog inspection tests with the already-delivered schema-only implementation and the Phase-1.2b plan. The p-coder review surfaced catalog-query isolation and predicate-format issues; this plan corrects those test-contract mismatches without changing the Phase-1.2b schema, migration semantics, or architecture contracts.

## Scope
- Add schema-scoped helpers for PostgreSQL catalog assertions in the Phase-1.2b migration tests.
- Update unique-constraint, FK, and downgrade assertions to inspect only the isolated Phase-1.2b test schema.
- Normalize the partial-index predicate assertion so it accepts PostgreSQL's rendered form for `native_enum=False` enum-backed VARCHAR columns.
- Confirm legacy Phase-1.2a Activity FK expectations are phase-scoped and do not run against the Phase-1.2b model state.
- Confirm RegenerationTask `ON DELETE SET NULL` behavior is tested in the same schema and transaction context where the FK is defined.
- Run targeted schema and migration tests after the test-only updates.

## Out Of Scope
- No production schema, migration, model, service, API, or event changes.
- No Alembic revision generation or database application.
- No change to the Phase-1.2b exit gate or architecture contracts.
- No migration of scope between sub-phases.
- No plan-generation, session-lifecycle, FIT-import, or coaching-agent implementation.

## Architecture Contracts
- `01-entities/training-goal.md` — DEPENDS ON the `TrainingGoal` active-goal partial unique index contract.
- `01-entities/weekly-plan.md` — DEPENDS ON the `(training_plan_id, week_number)` uniqueness contract.
- `01-entities/planned-session.md` — DEPENDS ON the `(weekly_plan_id, target_date, session_slot)` uniqueness contract.
- `01-entities/checkpoint.md` — DEPENDS ON the one-to-one `Checkpoint.planned_session_id` contract.
- `01-entities/activity.md` — DEPENDS ON Phase-1.2b wiring of `Activity.planned_session_id` to `PlannedSession` after the planned-session table exists.
- `docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md` — DEPENDS ON the existing schema-only implementation and its test expectations.
- `docs/implementation/phase-1/phase-1-2b-p1-plan-sessions_validation.md` — DEPENDS ON the prior validation context and its assumption that no schema changes are required.

## Invariants
- `TrainingGoal`: one active per athlete (partial unique index on `(athlete_id) WHERE status = 'active'`).
- `WeeklyPlan`: one per `(training_plan_id, week_number)`.
- `PlannedSession`: **Multiple PlannedSession records per day are allowed.** Uniqueness is enforced on `(weekly_plan_id, target_date, session_slot)` where `session_slot` distinguishes AM/PM sessions.
- `Checkpoint`: **One checkpoint per PlannedSession.** A PlannedSession may be flagged as a checkpoint, but a checkpoint cannot exist without a corresponding PlannedSession. The `training_plan_id` is derived from the PlannedSession's FK — no redundant FK on Checkpoint.
- `Checkpoint` completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) are set atomically.

## Implementation Steps
1. [OWNER: Coder] Add a schema-scoped PostgreSQL catalog helper for Phase-1.2b migration tests so `pg_constraint`, `pg_indexes`, and FK assertions join `pg_namespace` or otherwise filter by `phase_1_2b_schema["schema"]`.
2. [OWNER: Coder] Update the `weekly_plans` plan-week uniqueness test to assert exactly one named `uq_weekly_plans_plan_week` constraint in the isolated schema only.
3. [OWNER: Coder] Update the `planned_sessions` slot/date uniqueness test to assert exactly one named `uq_planned_sessions_plan_date_slot` constraint in the isolated schema only.
4. [OWNER: Coder] Update the `checkpoints.planned_session_id` uniqueness test to assert the named unique constraint on `checkpoints.planned_session_id` directly, without ambiguous correlated `conkey` subqueries.
5. [OWNER: Coder] Update the `training_goals` partial-index predicate assertion to accept PostgreSQL's rendered predicate form for `native_enum=False` enum-backed VARCHAR columns, including casted forms such as `((status)::text = 'active'::text)`.
6. [OWNER: Coder] Update FK catalog assertions and the downgrade helper to filter by the isolated schema and by the named constraint `fk_activities_planned_session`; assert `confdeltype='n'` for `ON DELETE SET NULL` and zero FK rows after downgrade in that schema.
7. [OWNER: Coder] Confirm the legacy Phase-1.2a Activity FK assertion is phase-scoped: it must either run only against the Phase-1.2a baseline or be updated to the Phase-1.2b expectation that `activities.planned_session_id` references `planned_sessions.id`.
8. [OWNER: Coder] Confirm the RegenerationTask deletion test observes `training_plan_id IS NULL` within the same schema-scoped transaction context where `regeneration_tasks.training_plan_id` has `ON DELETE SET NULL`.
9. [OWNER: Test Architect] Run the targeted migration and schema tests and verify the p-coder findings are resolved by test-contract alignment rather than schema changes.
10. [OWNER: DevOps] Confirm no Alembic revision generation, review, or application is required for this plan.

## Event Contracts
This plan produces or consumes no events. It only updates test-contract alignment for schema inspection.

## Pseudocode
```text
schema_scoped_catalog_query
  bind schema = phase_1_2b_schema["schema"]

  SELECT constraint metadata
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    JOIN pg_class table_class ON table_class.oid = c.conrelid
   WHERE n.nspname = :schema
     AND table_class.relname = :table_name
     AND c.conname = :constraint_name

  assert count == 1

schema_scoped_fk_query
  bind schema = phase_1_2b_schema["schema"]

  SELECT c.conname, c.confdeltype, pg_get_constraintdef(c.oid)
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    JOIN pg_class conrelid_table ON conrelid_table.oid = c.conrelid
    JOIN pg_namespace conf_schema ON conf_schema.oid = confrelid_table.relnamespace
    JOIN pg_class confrelid_table ON confrelid_table.oid = c.confrelid
   WHERE n.nspname = :schema
     AND conrelid_table.relname = 'activities'
     AND confrelid_table.relname = 'planned_sessions'
     AND c.conname = 'fk_activities_planned_session'

  assert confdeltype == 'n'

partial_index_predicate_assertion
  read pg_indexes.indexdef for the isolated schema
  normalize indexdef to lower case
  assert predicate contains the semantic active-goal condition
    accept raw form: status = 'active'
    accept casted form: ((status)::text = 'active'::text)
```

## Testing Requirements
- `test_weekly_plans_plan_week_unique_constraint` passes with exactly one `uq_weekly_plans_plan_week` constraint in the isolated Phase-1.2b schema.
- `test_planned_sessions_slot_date_unique_constraint` passes with exactly one `uq_planned_sessions_plan_date_slot` constraint in the isolated Phase-1.2b schema.
- `test_checkpoints_planned_session_unique_constraint` passes by asserting the unique constraint on `checkpoints.planned_session_id` directly.
- `test_training_goals_partial_unique_index_in_pg_catalog` passes against PostgreSQL's actual rendered predicate form for `native_enum=False` enum-backed VARCHAR columns.
- `test_activities_planned_session_fk_in_pg_catalog` passes with the named `fk_activities_planned_session` constraint and `confdeltype='n'` in the isolated Phase-1.2b schema.
- `test_downgrade_returns_schema_to_phase_1_2a_baseline` passes with zero `activities.planned_session_id` FK rows in the isolated schema after downgrade.
- `test_planned_session_id_is_nullable_uuid_no_fk` is either phase-scoped to the Phase-1.2a baseline or updated to the Phase-1.2b FK expectation.
- `test_set_null_on_plan_deletion` passes in the same schema-scoped transaction context where the `RegenerationTask.training_plan_id` FK is defined.
- Targeted migration and schema tests pass without changing production code or Alembic revisions.

## Coder Handoff Notes
```
## Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8  [OWNER: Coder] — includes migration generation
Skip:     Step 9 (Test Architect — targeted test run),
          Step 10 (DevOps — no migration revision/application)
```

- The p-coder review findings are primarily catalog-query isolation and predicate-format issues, not production schema defects.
- Do not change the Phase-1.2b migration or model semantics to force a raw predicate string. PostgreSQL may render `native_enum=False` VARCHAR-backed enum predicates with casts.
- Do not remove the Phase-1.2b named constraints from the migration based solely on duplicate counts. If duplicate counts appear, first verify that the catalog query is schema-scoped.
- The Activity FK expectation depends on phase context: Phase-1.2a expects a free-standing nullable UUID; Phase-1.2b wires `activities.planned_session_id` to `planned_sessions.id`.
- No ADR is required; this plan only aligns test inspection with the existing architecture contracts.
