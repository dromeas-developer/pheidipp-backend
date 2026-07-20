> **Baseline — test companion for** `batch-1-plan-sessions.md`, migrated from `docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md` + `phase-1-2b-p2-test-contract-alignment.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements. Schema-only plan — tests focus on migration, model metadata, and constraint enforcement.

### Migration
- Given `alembic upgrade head` succeeds from Phase 1-2a head `e7ffc8764335` on a fresh database
- Given `alembic downgrade e7ffc8764335` succeeds and leaves Phase 1-2a schema intact
- Given upgrade creates all 8 new tables with correct columns and types
- Given downgrade drops all 8 tables without affecting Phase 1-2a tables

### TrainingGoal
- Given `training_goals` has partial unique index on `(athlete_id) WHERE status = 'active'`
- Given inserting two active goals for same athlete raises uniqueness violation
- Given inserting active goal and superseded goal for same athlete succeeds (only one active)
- Given required fields present: `goal_type`, `goal_event_type`, `goal_event_date`, `fitness_level`, `weekly_volume_hours`, `status`, `created_at`
- Given `goal_type` is enum type (`GoalType`) not raw string
- Given `status` defaults to `'active'`

### TrainingPlan
- Given `training_plans` has FK to `training_goals.id`
- Given `twin_state_id` column exists as nullable UUID — but no FK constraint yet (deferred to 1-2c)
- Given `phases_summary`, `phase_definitions`, `weekly_distributions` are JSONB columns
- Given `status` defaults to `'active'`
- Given `superseded_at` is nullable datetime

### WeeklyPlan
- Given `weekly_plans` has FK to `training_plans.id`
- Given unique constraint `uq_weekly_plans_plan_week` on `(training_plan_id, week_number)`
- Given inserting two weeks with same `(plan_id, week_number)` raises uniqueness violation
- Given `adjusted_intent` is JSONB column
- Given `sessions_completed`, `sessions_missed`, `sessions_skipped` are integer defaults
- Given `doubles_days_count` is integer column

### WeeklySession
- Given `weekly_sessions` has FK to `weekly_plans.id`
- Given `planned_session_id` is nullable and unique when non-null
- Given `session_type` is `SessionType` enum
- Given `is_checkpoint` is boolean
- Given `block_id`, `block_position`, `block_session_count` are nullable

### PlannedSession
- Given `planned_sessions` has FK to `weekly_plans.id`
- Given denormalized FK to `training_plans.id`
- Given unique constraint `uq_planned_sessions_plan_date_slot` on `(weekly_plan_id, target_date, session_slot)`
- Given inserting two sessions for same `(weekly_plan_id, target_date, session_slot)` raises uniqueness violation
- Given `session_slot` nullable — multiple sessions per day allowed when slots differ or slots are null
- Given `status` defaults to `'scheduled'`
- Given `session_priority` is `SessionPriority` enum with default

### Checkpoint
- Given `checkpoints` has one-to-one FK to `planned_sessions.id` (non-null, unique)
- Given inserting two checkpoints for same `planned_session_id` raises uniqueness violation
- Given `checkpoints` has NO redundant `training_plan_id` column (verify by schema inspection)
- Given `type` is `CheckpointType` enum
- Given `status` defaults to `'scheduled'`
- Given completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) are nullable

### Supporting Tables
- Given `secondary_events` has FK to `training_goals.id`
- Given `secondary_events` has indexes for goal/date lookup
- Given `regeneration_tasks` has FK to `training_goals.id`
- Given `regeneration_tasks` has nullable FK to `training_plans.id` with `ON DELETE SET NULL`
- Given `regeneration_tasks` has index for pending proposals by training_goal

### Activity FK
- Given `activities.planned_session_id` has FK to `planned_sessions.id` with named constraint `fk_activities_planned_session`
- Given `activities.planned_session_id` remains nullable
- Given existing Phase 1-2a Activity columns are preserved (no `avg_hr`, `avg_pace`, etc.)

### Enum Values
- Given `GoalType`: `race_event`, `target_performance`, `fitness_improvement`, `maintenance`, `recovery`
- Given `SessionType`: 16 values including `rest`, `recovery_run`, `easy_run`, `long_run`, `threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`, etc.
- Given `CheckpointType`: `calibration`, `benchmark`, `race_simulation`, `secondary_race`, `progress_review`
- Given `PhaseLabel`: 17 primary + 3 legacy aliases
- Given all enum values match `00-foundations/terminology.md`

### Phase 1-2a Backward Compatibility
- Given existing `Activity` model tests pass (no regression)
- Given existing `AthleteProfile` / `AthletePreferences` registrations still work
- Given existing auth registration journey still creates minimal profile

### Remediation: Schema-Scoped Catalog Queries (Phase 1-2a/1-2b interaction)
- Given `test_planned_session_id_is_nullable_uuid_no_fk` is phase-scoped to 1-2a baseline OR updated to 1-2b FK expectation
- Given FK catalog queries filter by isolated test schema namespace (not picking up public schema constraints)

### Remediation: Catalog Query Isolation
- Given `test_weekly_plans_plan_week_unique_constraint` asserts exactly one `uq_weekly_plans_plan_week` in isolated schema
- Given `test_planned_sessions_slot_date_unique_constraint` asserts exactly one `uq_planned_sessions_plan_date_slot` in isolated schema
- Given `test_checkpoints_planned_session_unique_constraint` asserts unique constraint directly without ambiguous correlated subqueries

### Remediation: Partial Index Predicate
- Given `test_training_goals_partial_unique_index_in_pg_catalog` accepts both raw `status = 'active'` and casted `((status)::text = 'active'::text)` predicate forms

### Remediation: FK Assertions
- Given `test_activities_planned_session_fk_in_pg_catalog` asserts `fk_activities_planned_session` with `confdeltype='n'` in isolated schema
- Given `test_downgrade_returns_schema_to_phase_1_2a_baseline` confirms zero FK rows in isolated schema after downgrade

### Remediation: ON DELETE SET NULL
- Given `test_set_null_on_plan_deletion` observes `regeneration_tasks.training_plan_id IS NULL` after training plan deletion in same schema-scoped transaction where FK is defined
