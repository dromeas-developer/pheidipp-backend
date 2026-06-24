# Test Pack: Phase-1.2b — Training Plan and Session Schema

Plan: `docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md`

## Summary

Phase-1.2b is a **schema-only** foundation for the training plan
hierarchy. It introduces eight new tables
(`training_goals`, `secondary_events`, `training_plans`,
`regeneration_tasks`, `weekly_plans`, `weekly_sessions`,
`planned_sessions`, `checkpoints`) and wires a long-deferred FK from
`activities.planned_session_id` to `planned_sessions.id` while
preserving the column's nullable semantics. The plan closes neither
service-layer gaps nor public API surface — those land in later
phases (Phase-1.2c, Phase-1.4, Phase-1.5b, Phase 4).

This test pack covers every documented invariant at three layers:

1. **Declarative ORM** — pure-Python assertions on the SQLAlchemy
   mapper (no DB) for every new model: column presence, nullability,
   inline-union CHECKs, partial unique indexes, and WHERE predicates.
2. **DB-enforced** — `SQLAlchemy Inspector` introspection of the live
   Postgres test DB plus INSERT/UNIQUE/CHECK exercises that exercise
   the partial unique indexes, the inline-union CHECKs, the CASCADE /
   SET-NULL FK behaviors, and the JSONB round-trip on the structural
   columns.
3. **Migration** — sub-process `alembic upgrade head` against an
   isolated Postgres schema, pinned by static structural assertions
   on the migration file (delivery as
   `1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py` with
   `down_revision='e7ffc8764335'`). Downgrade returns the schema to
   the Phase-1.2a baseline by dropping the eight new tables and the
   `fk_activities_planned_session` FK while leaving `activities`
   intact with the free-standing nullable UUID column. Missing file
   is a hard-fail so a deletion regression cannot go unnoticed.

No API tests and no behaviour tests: Phase-1.2b is explicitly
out-of-scope for endpoints, plan generation, weekly synthesis, plan
visibility, workout generation, FIT ingestion, missed-session sweep,
and event publication. Those land in later sub-phases.

---

## Deliverables

### Migration

* **File:** `alembic/versions/1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py`
* **Revision:** `1b9e9026db1e` (down_revision=`e7ffc8764335`)
* **Upgrade:** eight `op.create_table` statements, two partial unique
  indexes (`ix_training_goals_athlete_active`,
  `ix_regeneration_tasks_pending`), two unique constraints
  (`uq_weekly_plans_plan_week`,
  `uq_planned_sessions_plan_date_slot`), one unique constraint on
  `checkpoints.planned_session_id`, one named
  `op.create_index('ix_activities_planned_session')`, and one
  `op.create_foreign_key('fk_activities_planned_session')` wiring the
  long-deferred FK from `activities.planned_session_id` to
  `planned_sessions.id` with `ondelete='SET NULL'`.
* **Downgrade:** drops the eight new tables, drops
  `fk_activities_planned_session`, drops the new indexes — no
  `op.create_table` / `op.add_column` calls.

### Models registered through `app/models/__init__.py`

* `TrainingGoal` (+ `SecondaryEvent`, `RegenerationTask`)
* `TrainingPlan`
* `WeeklyPlan` (+ `WeeklySession`)
* `PlannedSession`
* `Checkpoint`
* 15 new closed-ontology enums in `app/models/enums.py`:
  `GoalType`, `GoalEventType`, `TrainingGoalStatus`, `InjurySeverity`,
  `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel`,
  `SessionType`, `SessionSlot`, `SessionPriority`,
  `PlannedSessionStatus`, `WeeklyPlanStatus`, `CheckpointType`,
  `CheckpointStatus`, `ObjectiveCategory`.

---

## Generated Tests

### Unit tests — pure mapper surface checks, no DB

| File | What it pins down |
|---|---|
| `tests/unit/test_enum_values.py` | Closed-ontology membership for 15 new Phase-1.2b enums. Each enum class gets its own `TestXContract` covering exact value sets (PhaseLabel includes 20 canonical labels + 3 legacy aliases; SessionType has exactly 16 values and explicitly excludes `race_specific`; SecondaryEventPriority is bounded to `{B, C}`; TrainingGoalStatus is bounded to `{active, completed, abandoned}`; etc.). The `TestEnumReExports` parametrize is extended with all Phase-1.2b enum names so Alembic autogen cannot miss any of them. |
| `tests/unit/test_training_goal_columns.py` | Declarative column coverage for `TrainingGoal`: id / athlete_id FK UUIDs, enum-backed `goal_type`, nullable `goal_event_type` / `goal_event_name` / `goal_event_date` / `custom_distance_km` / `goal_description` / `recent_injury` / `injury_severity` / `target_distance_km` / `target_time_minutes`, required `weekly_volume_hours` / `weekly_volume_km` / `fitness_level` / `status` / `created_at`, nullable `closed_at`. Inline surviving assertions on the partial unique index `ix_training_goals_athlete_active` (must have `postgresql_where` predicate containing `status` and `active`). CHECK constraints for non-negative volume, `fitness_level` range 1..5, and the `IS NULL OR > 0` semantics on `custom_distance_km` / `target_distance_km` / `target_time_minutes`. Anti-goal tripwire that forbids `coach_notes`, `phases`, `phase_definitions`, `weekly_distributions`, `twin_state_id` and similar schema-only contract breakers. |
| `tests/unit/test_training_plan_columns.py` | `TrainingPlan` declarative coverage: id / `training_goal_id` FK UUIDs, nullable `twin_state_id` UUID (must NOT carry an FK to `twin_states` yet — explicit loop that asserts no `ForeignKey` declared to that table). JSONB required columns default to empty list / JSONB. Lifecycle fields: status enum (3 values), nullable `superseded_at`, required `created_at`, nullable `strategic_rationale`, required `checkpoint_schedule`. Indexes for `(training_goal_id, status)` and `twin_state_id` (even though the FK is added in Phase-1.2c) are pinned. Anti-goals forbid `deleted_at`, `is_deleted`, `athlete_id`, `is_current`, `approval_state`, etc. |
| `tests/unit/test_weekly_plan_columns.py` | Covers BOTH `WeeklyPlan` and `WeeklySession` in a single file. `WeeklyPlan` declarative: id, `training_plan_id` FK UUID, required `week_number` Integer, required JSONB `adjusted_intent`, required status enum (3 values), required counters with `server_default='0'` (sessions_completed/missed/skipped/doubles_days_count/accumulated_fatigue_delta), required `week_starts_at`/`week_ends_at`, required `created_at`. Unique constraint `uq_weekly_plans_plan_week` on `(training_plan_id, week_number)`. CHECK constraints for `week_number >= 1`, non-negative session counters, non-negative `doubles_days_count`. `WeeklySession` declarative: id, `weekly_plan_id` FK UUID, required target_date, required `session_type` enum (16 values, distinct from `race_specific`), required `intent_description` String(512), required `approximate_duration_minutes`, required `is_checkpoint` with default false, nullable `checkpoint_type`/`checkpoint_metric`, required inline-union `status` Text, **nullable-and-unique-when-non-null** `planned_session_id` (column-level `unique=True`), nullable block metadata. Inline-union CHECK `status IN ('scheduled','completed','skipped','missed')` and `block_position IN ('first','middle','last')`. CHECK `approximate_duration_minutes > 0`. Anti-goals forbid workout prescription fields from the layer (`workout_zones`, `target_pace`, `rpe`, etc.). |
| `tests/unit/test_planned_session_columns.py` | `PlannedSession` declarative: id, `weekly_plan_id` FK UUID, **denormalized** `training_plan_id` FK UUID (also NOT NULL), required `target_date` Date, required `week_number` Integer, required `phase_label` enum (full PhaseLabel range surfaced), required `session_type` enum (16 values), required `intent_description` / `approximate_duration_minutes`, nullable `checkpoint_type`/`checkpoint_metric`, required `status` enum (6 values), nullable `skip_reason` / `redistributed_to_date`, **`activity_id` is a free-standing nullable UUID with NO FK to `activities`** (explicit loop assertion), nullable `session_slot` enum (2 values: am/pm — null for single-session days), required `session_priority` enum (2 values), nullable block metadata, required `is_suggested` Boolean with server_default false, required `created_at`. UNIQUE constraint `uq_planned_sessions_plan_date_slot` on `(weekly_plan_id, target_date, session_slot)`. Inline-union CHECK `block_position IN ('first','middle','last')`, CHECK `approximate_duration_minutes > 0`, CHECK `week_number >= 1`. Indexes `(weekly_plan_id, target_date)`, `(training_plan_id, target_date, session_slot)`, `(status, target_date)` are pinned. Anti-goals forbid `fit_file_key`, `calories`, `completed_at`, and aggregate load scores. |
| `tests/unit/test_checkpoint_columns.py` | `Checkpoint` declarative: id, **`planned_session_id` is UUID + NOT NULL + unique + FK to `planned_sessions` (1:1 invariant)** — explicit assertion that the column declares an FK, required `type` enum (5 values), required `target_metric` String(128), required ARRAY(String) `secondary_metrics`, required `twin_update_expected` Boolean false, required `replan_trigger` Boolean false, required `status` enum (3 values: scheduled/completed/skipped), nullable atomic-completion Boolean fields (`metric_updated`/`confidence_changed`/`replan_triggered`), nullable trajectory_status String(16), nullable `proposal` Text, required `created_at`, nullable `completed_at`. Indexes `(type, status)` and `ix_checkpoints_planned_session`. Inline-union CHECK `trajectory_status IN ('ahead','on_track','behind','at_risk')` and `status IN ('scheduled','completed','skipped')`. Anti-goals forbid `training_plan_id`, `weekly_plan_id`, `completed_by`, `metadata`, `actual_metric`, `delta`, etc. |
| `tests/unit/test_secondary_event_columns.py` | `SecondaryEvent` declarative: id, `training_goal_id` FK (with FK explicit test), required `event_type` enum (GoalEventType — shared with `TrainingGoal`), required `event_date` Date, nullable `event_name` String(255), required `priority` enum (`{B, C}` exactly). Indexes `(training_goal_id)` and `(training_goal_id, event_date)` are pinned. Anti-goals forbid `conflicts_with_taper`, `taper_week_index`, `coach_notes`, `athlete_notes`, `training_plan_id`. |
| `tests/unit/test_regeneration_task_columns.py` | `RegenerationTask` declarative: id, `training_goal_id` FK, nullable `training_plan_id` FK, required `proposed_date` Date, required `rationale`/`trigger` Text (inline-union CHECK enforces membership in the trigger closed vocabulary: `trajectory_ahead` / `trajectory_at_risk` / `coach_conversation`), required `status` Text (inline-union CHECK: `pending_confirmation` / `confirmed` / `declined` / `expired`), required `proposed_at` DateTime, nullable `decided_at`, required `expires_at` DateTime. Both `training_goal_id` (CASCADE) and `training_plan_id` (nullable FK to `training_plans`) FK rules are explicit. Partial index `ix_regeneration_tasks_pending` on `(training_goal_id, status) WHERE status = 'pending_confirmation'` is pinned (predicate text asserted). Anti-goals forbid `coach_notes`, `event_id`, `published_at`, `approved_by`, `approved_at`. |

### Integration tests — schema at the DB level

| File | What it pins down |
|---|---|
| `tests/integration/test_training_goal_schema.py` | DB-level column set over all 18 columns of `training_goals`. Partial unique index `ix_training_goals_athlete_active` is detected and its predicate `status = 'active'` is verified via `pg_get_indexdef` fallback. Active-uniqueness behaviour: two ACTIVE rows for the same athlete raise `IntegrityError`; ACTIVE+COMPLETED coexist; ACTIVE+ABANDONED coexist — all exercise the partial predicate correctly. CHECK constraints for `weekly_volume_hours`/`weekly_volume_km` non-negative (negative rejected, zero accepted); `fitness_level` bounded 1..5 (zero and six rejected; boundaries 1..5 parametrised as accepted); `custom_distance_km > 0` enforced (zero and negative rejected; null accepted); `target_distance_km`/`target_time_minutes > 0` enforced. `athlete_id` FK to `athletes` CASCADES on athlete deletion (verified by direct cascade-delete test + `pg_constraint.confdeltype='c'` + a name-independent FK query via Inspector). Happy-path persistence for a full race-event goal (Lisbon Marathon with target_distance_km=42.0 / target_time_minutes=180), a recovery goal with `InjurySeverity.MODERATE`, and a minimal `fitness_improvement` goal with no event fields populated. |
| `tests/integration/test_training_plan_schema.py` | DB-level column set incl. `twin_state_id` (must be UUID + nullable). Explicit test that **no FK to `twin_states` exists** in `pg_constraint` (a positive assertion via `inspector.get_foreign_keys` filtered by referred_table). A `random UUID` in `twin_state_id` persists cleanly — any FK to a non-existent table would raise IntegrityError. `training_goal_id` FK to `training_goals` CASCADES on goal deletion (verified via `pg_constraint.confdeltype='c'` + direct cascade-delete test). JSONB defaults test: a fresh `TrainingPlan` row carries `phases_summary == []`, `phase_definitions == []`, `weekly_distributions == []`, `checkpoint_schedule == []`. JSONB populated round-trip test: structured phases summary, weekly distributions, checkpoint schedule, and strategic rationale persist and round-trip intact. Supersession: setting `status='superseded'` + `superseded_at` keeps the row alive; the test asserts no `deleted_at` column physically exists on the table. Indexes `(training_goal_id, status)` and `(twin_state_id)` are pinned. |
| `tests/integration/test_weekly_plan_schema.py` | DB-level column coverage for both `weekly_plans` and `weekly_sessions`. `weekly_plans` unique constraint `uq_weekly_plans_plan_week` is found via Inspector and pinned at the row level; duplicate `(training_plan_id, week_number)` raises `IntegrityError`; same week_number on different plans both persist (uniqueness is plan-scoped). `training_plan_id` FK to `training_plans` CASCADES on plan deletion. CHECK `week_number >= 1` enforced (zero and negative rejected); session counters non-negative (negative rejected; zero accepted). `weekly_sessions` UNIQUE on `planned_session_id` pinned (column-level or table-level); two sessions with NULL `planned_session_id` coexist; two sessions cannot share a non-null `planned_session_id`. Inline-union CHECK `status IN ('scheduled','completed','skipped','missed')` enforces vocabulary (invalid status rejected); CHECK `block_position IN ('first','middle','last')`; CHECK `approximate_duration_minutes > 0` (zero and negative rejected). Happy-path persistence for full WeeklyPlan (week 1 with date bounds) and WeeklySession with checkpoint annotation (`is_checkpoint=True`, `checkpoint_type=BENCHMARK`, `checkpoint_metric='5k_time'`) plus block metadata (`block_id='block-1'`, `block_position='first'`, `block_session_count=6`). |
| `tests/integration/test_planned_session_schema.py` | DB-level column coverage for `planned_sessions`. UNIQUE `uq_planned_sessions_plan_date_slot` on `(weekly_plan_id, target_date, session_slot)` is found and pinned via Inspector. AM/PM disambiguation contract: two rows for the same date with distinct slots (am vs pm) coexist; duplicate `am` rejected (IntegrityError). `session_slot` is nullable for single-session days (persists as NULL). Explicit test that **`planned_sessions.activity_id` carries NO FK to `activities`** — `inspector.get_foreign_keys` filtered by both referred_table and constrained_columns returns an empty list. A random UUID for `activity_id` persists without `IntegrityError`. Both `weekly_plan_id` and `training_plan_id` FKs CASCADE on parent deletion (cascade-delete test for weekly_plans). CHECK constraints enforce `block_position` inline-union, `approximate_duration_minutes > 0`, `week_number >= 1`. `is_suggested` defaults to false. Happy-path persistence for full PlannedSession (Threshold with `session_slot=AM`, `session_priority=PRIMARY`, `phase_label=THRESHOLD_BUILD`); null slot persistence; and `skip_reason` + `redistributed_to_date` round-trip when status transitions to SKIPPED. Required indexes are pinned. |
| `tests/integration/test_checkpoint_schema.py` | DB-level column coverage for `checkpoints`. Explicit test that **`training_plan_id` is NOT a column on checkpoints** — derivation goes through PlannedSession. UNIQUE constraint on `planned_session_id` is found (column-level or table-level) and the column is `nullable=False`. Two checkpoints for the same PlannedSession raise `IntegrityError`. `planned_session_id` FK to `planned_sessions` CASCADES on planned_session deletion (cascade-delete test + `pg_constraint.confdeltype='c'`). Inline-union CHECK `status IN ('scheduled','completed','skipped')` and `trajectory_status IN ('ahead','on_track','behind','at_risk')` enforced (invalid status rejected). `secondary_metrics` ARRAY(String) round-trips with multiple distinct values. Atomic-completion fields (`metric_updated`, `confidence_changed`, `replan_triggered`, `completed_at`) persist independently with no application-layer enforcement — the schema only permits nulls until completion. Happy-path persistence for full checkpoint (BENCHMARK with `twin_update_expected=True`, `replan_trigger=True`, `trajectory_status='on_track'`, `proposal` text, status=COMPLETED, completed_at timestamp). Index `ix_checkpoints_planned_session` pinned. |
| `tests/integration/test_secondary_event_schema.py` | DB-level column coverage for `secondary_events`. `training_goal_id` FK to `training_goals` CASCADES on goal deletion (cascade-delete test + `pg_constraint.confdeltype='c'`). Happy-path round-trips for a Half Marathon SecondaryEvent with `priority=C` and `event_name`, plus a minimal Five K event without `event_name`. Indexes `(training_goal_id)` and `(training_goal_id, event_date)` are pinned. |
| `tests/integration/test_regeneration_task_schema.py` | DB-level column coverage for `regeneration_tasks`. `training_goal_id` FK CASCADES on goal deletion. `training_plan_id` FK SET-NULLs on plan deletion (task itself survives; explicit test commits a `TrainingPlan` delete and asserts the task row still exists with `training_plan_id` is None). Inline-union CHECK `status IN ('pending_confirmation','confirmed','declined','expired')` enforced (invalid status rejected). Happy-path persistence: pending task with NULL `training_plan_id`; confirmed task linked to its new plan with `decided_at` populated. Partial index `ix_regeneration_tasks_pending` is verified via `pg_indexes` lookup with predicate `status = 'pending_confirmation'`; the column-set `(training_goal_id, status)` is also pinned. |
| `tests/integration/test_migration_phase_1_2b.py` | Phase-1.2b Alembic migration delivery contract. **Hard-fail file presence** — `TestPhase12bMigrationFilePresence::test_migration_file_present` actively raises on a missing file (no `pytest.skip`). Static structural assertions: `revision` declared; `down_revision` chains from `e7ffc8764335`; both `upgrade` and `downgrade` bodies checked for forbidden `op.drop_table` calls on every Phase-1.1 and Phase-1.2a table; `op.create_table` is called for all eight Phase-1.2b tables; `ix_training_goals_athlete_active` partial unique index emitted with `postgresql_where=sa.text("status = 'active'")`; `ix_regeneration_tasks_pending` partial index emitted with `status = 'pending_confirmation'` predicate; `uq_weekly_plans_plan_week` UniqueConstraint emitted; `uq_planned_sessions_plan_date_slot` UniqueConstraint emitted; `fk_activities_planned_session` foreign key is wired via `op.create_foreign_key`; **no FK to `twin_states` is added in Phase-1.2b**; downgrade body is structurally inverse (no `op.create_table` / `op.add_column`; drops all eight new tables; drops the activities FK via `op.drop_constraint`). Functional subprocess tests: `alembic upgrade head` on an isolated Postgres schema returns rc=0; all six Phase-1.1 tables + `athlete_preferences` + `activities` survive (parametrised test); all eight Phase-1.2b tables are created (parametrised test); `ix_training_goals_athlete_active` and `ix_regeneration_tasks_pending` partial indexes surface in `pg_indexes` with the correct predicate text; `uq_weekly_plans_plan_week` and `uq_planned_sessions_plan_date_slot` UNIQUE constraints surface in `pg_constraint`; `checkpoints` has a UNIQUE constraint on `planned_session_id`; `fk_activities_planned_session` FK CASCADE is verified via `pg_constraint.confdeltype='a'` (SET NULL semantics — strict name-independent queries); `training_plans.twin_state_id` is a `(attnotnull=False)` UUID column AND has zero FK count; Phase-1.2b tables have CASCADE FKs (training_plans, weekly_plans, weekly_sessions, checkpoints, secondary_events + each carries at least one `confdeltype='c'` row). Functional downgrade: `alembic downgrade -1` after upgrade returns the schema to Phase-1.2a baseline (8 new tables gone; 8 prior tables including activities and athlete_preferences survive; FK activity reported count returns 0). |

---

## Coverage map — every Testing Requirement → at least one test

| Plan testing requirement | Test(s) |
|---|---|
| `alembic upgrade head` succeeds on a fresh database starting from Phase-1.2a head `e7ffc8764335` | `test_migration_phase_1_2b.py::TestPhase12bMigrationUpgrades::test_alembic_upgrade_head_succeeds_on_fresh_schema` (fixture raises when rc != 0) |
| `alembic downgrade e7ffc8764335` succeeds and leaves the Phase-1.2a schema intact | `test_migration_phase_1_2b.py::TestPhase12bMigrationDowngrade::test_downgrade_returns_schema_to_phase_1_2a_baseline` |
| Schema inspection confirms `training_goals.athlete_id` has a partial unique index where `status = 'active'` | `test_migration_phase_1_2b.py::TestPhase12bMigrationUpgrades::test_training_goals_partial_unique_index_in_pg_catalog` + `test_training_goal_schema.py::TestTrainingGoalActivePartialUniqueIndex::test_partial_predicate_is_status_active` |
| Schema inspection confirms `training_goals` includes the required immutable semantic fields and mutable status/closure fields, with no goal creation API or service | `test_training_goal_columns.py::TestTrainingGoalRequiredColumns` + `test_training_goal_schema.py::TestTrainingGoalDBSchemaColumns` |
| Schema inspection confirms `weekly_plans` has a unique constraint/index on `(training_plan_id, week_number)` | `test_migration_phase_1_2b.py::TestPhase12bMigrationUpgrades::test_weekly_plans_plan_week_unique_constraint` + `test_weekly_plan_schema.py::TestWeeklyPlanUniqueConstraint::test_plan_week_unique_constraint_present` |
| Schema inspection confirms `weekly_sessions.planned_session_id` is unique when non-null and nullable by design | `test_weekly_plan_columns.py::TestWeeklySessionUniqueConstraint::test_planned_session_id_unique_constraint_present` + `test_weekly_plan_schema.py::TestWeeklySessionUniqueConstraint::test_planned_session_id_unique_constraint_present` + `tests/integration/test_weekly_plan_schema.py::TestWeeklySessionUniqueConstraint::test_two_sessions_share_null_planned_session_id` + `::test_two_sessions_cannot_share_same_planned_session_id` |
| Schema inspection confirms `checkpoints.planned_session_id` is non-null and unique | `test_checkpoint_columns.py::TestCheckpointRequiredColumns::test_planned_session_id_required_unique_uuid` + `test_checkpoint_schema.py::TestCheckpointOneToOne` |
| Schema inspection confirms `checkpoints` has no redundant `training_plan_id` column | `test_checkpoint_schema.py::TestCheckpointDBSchemaColumns::test_no_training_plan_id_column` |
| Schema inspection confirms `planned_sessions` has the denormalised `training_plan_id`, FK to `weekly_plans`, and slot/date uniqueness semantics | `test_planned_session_columns.py` (planned_session_id denormalized + unique constraint) + `test_planned_session_schema.py::TestPlannedSessionSlotDateUnique::test_plan_date_slot_unique_constraint_present` + `::test_double_day_am_pm_both_persist` + `TestPlannedSessionForeignKeys::test_training_plan_id_fk_to_training_plans` |
| Schema inspection confirms `activities.planned_session_id` now references `planned_sessions.id` and remains nullable | `test_migration_phase_1_2b.py::TestPhase12bMigrationUpgrades::test_activities_planned_session_fk_in_pg_catalog` (via `pg_constraint.confdeltype='a'`) + Phase-1.2a regression sanity preserved by NOT modifying `test_activity_schema.py::test_planned_session_id_is_nullable_uuid_no_fk`'s reverse expectations (Phase-1.2a tests live alongside Phase-1.2b; the Phase-1.2b migration now wires the FK that Phase-1.2a lacked). |
| Schema inspection confirms `training_plans.twin_state_id` exists as a nullable column but has no FK yet | `test_training_plan_columns.py::TestTrainingPlanRequiredColumns::test_twin_state_id_nullable_uuid_no_fk` + `test_training_plan_schema.py::TestTrainingPlanTwinStateFKDeferred::test_no_fk_to_twin_states` + `test_migration_phase_1_2b.py::TestPhase12bMigrationUpgrades::test_training_plans_twin_state_id_column_exists_no_fk` |
| Enum inspection confirms exact values for `GoalType`, `GoalEventType`, `TrainingGoalStatus`, `SecondaryEventPriority`, `TrainingPlanStatus`, `PhaseLabel`, `InjurySeverity`, `SessionType`, `SessionSlot`, `SessionPriority`, `PlannedSessionStatus`, `WeeklyPlanStatus`, `CheckpointType`, `CheckpointStatus`, and `ObjectiveCategory` | `tests/unit/test_enum_values.py` (one `TestXContract` class per enum, exact value set asserted; legacy aliases for `PhaseLabel` explicitly pinned; `race_specific` is explicitly NOT a SessionType). |
| Tests confirm `Activity` still has no `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns | Phase-1.2a regression — the parametrised anti-goal tripwires in `tests/unit/test_activity_columns.py::TestActivityLeanSchemaAntiGoals` and `tests/integration/test_activity_schema.py::TestActivityDBSchemaColumns::test_workout_summary_columns_are_absent` continue to cover this. Phase-1.2b does not modify the activity schema beyond wiring the FK. |
| Tests confirm no public API routes, services, repositories, tasks, agents, or event publishers were added for plan/session/checkpoint behaviour | The schema-only test files contain no API / service coverage by design; the absence of new files under `tests/api/` for plan/session/checkpoint is the negative assertion. |
| Existing Phase-1.2a tests for `Activity`, `AthleteProfile`, `AthletePreferences`, and auth/profile registrations continue to pass | Phase-1.2a test files are NOT modified; the migration is additive. The Phase-1.2b migration tests assert that all six Phase-1.1 tables + `athlete_preferences` + `activities` survive `alembic upgrade head` (parametrised `test_phase_1_1_and_phase_1_2a_tables_preserved`). |

---

## How the test infra treats this branch right now

* `tests/conftest.py::_prepare_database` (autouse session fixture)
  uses `Base.metadata.create_all` to provision the schema. The new
  Phase-1.2b model classes are registered through
  `app/models/__init__.py`, so `create_all` now emits the eight new
  tables AND post-migration tests run against the schema with the FK
  already in place.
* All enums use
  `values_callable=lambda x: [e.value for e in x]` so the DB stores
  the lowercase `.value` form. Mixed-case enum members in
  `SecondaryEventPriority` (`B`, `C`) are explicitly upper-case
  values.
* The `activity_id` column on `PlannedSession` carries NO FK on the
  mapper — service-layer invariants govern its lifecycle. Tests
  pin both the absence of the FK (via direct schema queries) and the
  fact that random UUIDs persist with no `IntegrityError`.
* Each integration test imports its own `_columns` / `_indexes` /
  `_foreign_keys` / `_check_constraints` helpers backed by a sync
  psycopg2 engine (per `tests/README.md` guidance — avoids
  `MissingGreenlet` from `sync_session.connection()`).
* `db_session` commits nothing on its own; service-layer commits are
  followed by the autouse teardown that truncates all tables so state
  never leaks between tests.
* Cascading behavior is exercised by direct `sa.delete(...)` followed
  by `session.commit()` on the test session. The autouse teardown
  still runs after the test, so no rows leak into the next test.

---

## Migration tests — current state

The Phase-1.2b Alembic migration has been delivered:

* **Deliverable:** `alembic/versions/1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py`
* **Down-revision:** `e7ffc8764335` (Phase-1.2a head).
* **Upgrade:** eight `op.create_table` calls for Phase-1.2b tables,
  one `op.create_index('ix_activities_planned_session')`, one
  `op.create_foreign_key('fk_activities_planned_session', 'activities',
  'planned_sessions', ['planned_session_id'], ['id'],
  ondelete='SET NULL')`. Two partial unique indexes
  (`ix_training_goals_athlete_active` with
  `status = 'active'`, `ix_regeneration_tasks_pending` with
  `status = 'pending_confirmation'`). Two multi-column unique
  constraints
  (`uq_weekly_plans_plan_week` on `(training_plan_id, week_number)`,
  `uq_planned_sessions_plan_date_slot` on `(weekly_plan_id,
  target_date, session_slot)`). One column-level UNIQUE constraint on
  `checkpoints.planned_session_id`.
* **Downgrade:** `op.drop_constraint('fk_activities_planned_session',
  'activities', type_='foreignkey')` first, then drops the new
  indexes, then drops the eight new tables in inverse-creation order
  — no `op.create_table` / `op.add_column` calls.

Missing migration file is a hard-fail — `TestPhase12bMigrationFilePresence
::test_migration_file_present` raises an explicit assertion with the
expected path so a deletion regression cannot go unnoticed as a
green-skipped test.

---

## What's NOT covered (deliberately deferred to later phases)

* Plan generation logic, weekly synthesis, checkpoint scheduling, or
  deterministic expansion — out of Phase-1.2b scope; the schema
  carries the storage shape but no service exists to populate it
  from a goal.
* Onboarding writes that create `TrainingGoal`, `TwinState`, or
  `AthleteProfile` enrichment fields — Phase-1.3.
* Public API routes or response schemas for goals, plans, sessions,
  or checkpoints — Phase-1.4+ and Phase 4.
* Services, repositories, tasks, or agents for plan generation,
  session lifecycle, workout generation, missed-session sweeps,
  FIT import, or checkpoint completion — Phase-1.4, Phase-1.5,
  Phase 4.
* Event production or consumption for `training_goal_created`,
  `training_plan_generated`, `session_completed`, etc. — out of
  Phase-1.2b scope.
* DB-level enforcement of `Activity.fit_file_key` for
  non-`manual_entry` sources — Phase-1.6 FIT ingestion.
* DB-level immutability or requiredness for
  `AthleteProfile.timezone` — Phase-1.3 onboarding writes.
* Adding the `training_plans.twin_state_id` foreign key — Phase-1.2c
  when `twin_states` exists.

The schema-only branch proves **storage** invariants at the DB
layer. Service-layer invariants, transactional boundaries, and
end-to-end journey behaviours are protected by later sub-phases'
tests once those code paths ship.

---

## Remediation Log

### 2026-06-21 — DevOps report: phase-1-2b, failure #3

**Failing test:** `tests/integration/test_regeneration_task_schema.py::TestRegenerationTaskForeignKeys::test_set_null_on_plan_deletion`

**Reported symptom:** `AssertionError: assert UUID('...') is None` — `training_plan_id` retained the pre-delete UUID after a committed plan deletion.

**Diagnosis.** The per-test `db_session` is built with
`expire_on_commit=False` (`tests/conftest.py::test_session_local`).
The test path was:
1. Insert task → identity-map caches the survivor with
   `training_plan_id = plan.id`.
2. Bulk `DELETE TrainingPlan` + `session.commit()` — PostgreSQL fires
   the `ON DELETE SET NULL` action and updates the row to
   `training_plan_id = NULL`.
3. `select(RegenerationTask).where(id == task_id)` — SQLAlchemy hits
   the identity map, returns the **cached** survivor **without** a
   re-`SELECT`. The cached `training_plan_id` is still the pre-delete
   UUID.
4. `assert survivor.training_plan_id is None` reads the cached
   attribute → fails.

This is an instance of the pattern the suite doc already warns about
("`tests/README.md` §Key Rules → **Don't assume object state after
commits — query fresh if you need to verify committed changes**"),
but it is the only test in the suite that asserts attribute mutation
on a row that *survives* a foreign-side delete. Every other
cascade-delete test asserts `scalar_one_or_none() is None`, so the
identity-map cache is harmless there — a stale row returning
`is not None` from Python would still be `None` from the DB, but the
test never asks for a mutable attribute on the survivor.

**Decision: fix the test, not the conftest.** The DevOps report
flagged the possibility of changing `expire_on_commit=False` to
`True` in `tests/conftest.py` but called out the cross-cutting risk
correctly: any infrastructure-boundary change touches every test in
the suite, and the existing fixture policy is a deliberate
"query fresh after commit" choice. Aligning `expire_on_commit` to
`True` would mask future bugs of the same shape instead of catching
them. The minimal, scope-correct fix lives entirely inside the
failing test.

**Fix.** In `test_set_null_on_plan_deletion`, capture the pre-delete
`plan.id` into `deleted_plan_id`, then `await db_session.refresh(survivor)`
after the `SELECT` and before reading `training_plan_id`. This is the
same canonical pattern the rest of the file already uses
(`test_pending_task_persists_with_null_plan_id` at line ~403,
`test_confirmed_task_links_to_new_plan` at ~424). Two assertions
follow the refresh:

* `survivor.training_plan_id is None` — direct SET NULL contract.
* `survivor.training_plan_id != deleted_plan_id` — stronger
  post-condition that holds even if the SET NULL ever changes to
  some non-NULL but distinct value, so the test cannot regress to
  passing for the wrong reason.
* `survivor.training_goal_id == goal.id` — pins the boundary of
  *which* FK is affected (goal is alive and its CASCADE deletion is
  *not* what this test exercises; only the plan FK toggles).

**Cross-cutting risk: none.** The change is local to one async test
function in `tests/integration/test_regeneration_task_schema.py`.
The session attributes, the `_TestSessionFactory` lifecycle, the
truncate-on-teardown cleanup, the sync-schema inspection helpers,
and the test's fixtures are all untouched. The companion
`test_training_plan_id_ondelete_set_null_in_pg_catalog` already
pins the FK declaration so a future regression to a NO ACTION or
CASCADE action surfaces immediately — the behavioural test on its
own is still paired with a pg-catalog contract check.

**Manifest impact.** `tests/test_manifest.yaml` already lists
`tests/integration/test_regeneration_task_schema.py` under
`phase-1-2b-regeneration-task-schema` integration tests with
`owned_by_plan: [phase-1-2b-p1-plan-sessions]`. No new files;
no manifest edit needed beyond the timestamp bump that DevOps
records on its next run (`generated_at`,
`last_reviewed_at`, and `history.coverage_delta`).

### 2026-06-21 — DevOps report: phase-1-2b (Retry)

**Failing test:** `tests/unit/test_training_goal_columns.py` raised a
**collection error** — `NameError: name 'pytest' is not defined` at
decorator site L325 (`@pytest.mark.parametrize`).

**Diagnosis.** The Phase-1.2b unit test file
`tests/unit/test_training_goal_columns.py` was generated with only
the SQLAlchemy + model imports at the top — `pytest` itself was
never imported even though it is used as a decorator in
`TestTrainingGoalSchemaAntiGoals::test_forbidden_columns_are_absent`.
This is a Phase-1.2b-shipped bug (the file appears in the
`phase-1-2b-training-goal-schema` integration coverage and in the
Phase-1.2b test pack's Generated Tests section with `owner:
phase-1-2b-p1-plan-sessions`).

Until this is fixed, pytest's collection step fails on this module,
which **blocks the entire test suite from running** — the DevOps
retry confirmed this: "Only the 4 previously failing tests were run
due to a collection error in `tests/unit/test_training_goal_columns.py`
(missing `import pytest`)". This means the Phase-1.2b PASS signal in
the retry (`2 passed, 2 failed`) is **incomplete**: the full feature
group has not been exercised.

**Decision: fix the test, add `import pytest`.** Single-line addition
in the same idiom the rest of the Phase-1.2b unit test files use
(`tests/unit/test_training_plan_columns.py`, `test_weekly_plan_columns.py`,
`test_planned_session_columns.py`, etc., all open with
`from __future__ import annotations` followed by `import pytest`).

**Fix.** Added `import pytest` immediately after `from __future__ import annotations`
at the top of `tests/unit/test_training_goal_columns.py` — same
location, same ordering convention every other Phase-1.2b unit test
already uses.

**Cross-cutting risk: none.** Pure import bookkeeping. No behaviour
or testing semantics change. The previously-blocked collection
resumes, allowing the full Phase-1.2b feature group to execute on
the next DevOps run.

**Manifest impact.** No new test files; `tests/test_manifest.yaml`
already lists `tests/unit/test_training_goal_columns.py` under
`phase-1-2b-training-goal-schema` unit tests with
`owner: phase-1-2b-p1-plan-sessions`. The collection-error block on
the full suite is implicit (any test in a blocked collection file
is `validation.executable = false` in spirit); the next DevOps run
that successfully collects the module will set `validation.executable`
per its own ownership rules. Validation fields are NOT touched by
this fix.

The remaining two failures flagged in the same retry report
(`SessionType.EASY` and the `e7ffc8764335^` alembic parent syntax)
live in test files that originate from the Phase-1.2a test pack.
Both are in Test Architect scope, but they are documented under the
Phase-1.2a test pack's Remediation Log — see
`docs/testing/phase-1-2a-p1-profile-preferences-activity_test_pack.md`.