# Test Pack — Phase 1.2b (plan-sessions)

**Plan:** `docs/implementation/phase-1/phase-1-2b-p1-plan-sessions.md`  
**Generated:** 2026-06-20  
**Promoted:** 2026-06-23  
**DevOps Report:** `reports/phase-1-2b_devops.md`  
**Result:** 880/880 tests passed in 127 seconds

---

## Overview

Phase 1.2b delivers the training plan infrastructure: training goals, secondary events, training plans, regeneration tasks, weekly plans, planned sessions, and checkpoints. This test pack validates the complete schema layer for these entities.

### Migration

- **File:** `alembic/versions/1b9e9026db1e_phase_1_2b_plans_sessions_checkpoints.py`
- **From:** `e7ffc8764335` (Phase 1.2a head)
- **Creates:** 8 new tables (`training_goals`, `secondary_events`, `training_plans`, `regeneration_tasks`, `weekly_plans`, `weekly_sessions`, `planned_sessions`, `checkpoints`)
- **Extends:** `activities.planned_session_id` with FK to `planned_sessions.id` (ON DELETE SET NULL)

---

## Features Tested

### 1. Enum Contracts (`phase-1-2b-enums`)

**Tests:** `tests/unit/test_enum_values.py`

Validates closed ontology membership for all Phase 1.2b enums:

- `GoalType` (5 values)
- `GoalEventType` (7 values)
- `TrainingGoalStatus` (3 values)
- `InjurySeverity` (3 values)
- `SecondaryEventPriority` (2 values)
- `TrainingPlanStatus` (3 values)
- `PhaseLabel` (20 canonical + 3 legacy)
- `SessionType` (16 values)
- `SessionSlot` (2 values)
- `SessionPriority` (2 values)
- `PlannedSessionStatus` (6 values)
- `WeeklyPlanStatus` (3 values)
- `CheckpointType` (5 values)
- `CheckpointStatus` (3 values)
- `ObjectiveCategory` (9 values)

**Bug Fixes During This Phase:**
- Fixed `PlannedSessionStatus.SCHEDULED` → `PlannedSessionStatus.PENDING` (line 592 in `test_activity_schema.py`)
- Added required `session_priority=SessionPriority.PRIMARY` to `PlannedSession` test factory (line 594)

---

### 2. Training Goal Schema (`phase-1-2b-training-goal-schema`)

**Tests:** 
- Unit: `tests/unit/test_training_goal_columns.py`
- Integration: `tests/integration/test_training_goal_schema.py`

**Invariants Protected:**
- Full column set present
- Partial unique index `ix_training_goals_athlete_active` WHERE `status='active'`
- One active goal per athlete (two ACTIVE goals raise IntegrityError)
- ACTIVE + COMPLETED can coexist
- ACTIVE + ABANDONED can coexist
- CHECK: `weekly_volume_hours >= 0`
- CHECK: `weekly_volume_km >= 0`
- CHECK: `fitness_level BETWEEN 1 AND 5`
- CHECK: `custom_distance_km IS NULL OR > 0`
- CHECK: `target_distance_km IS NULL OR > 0`
- CHECK: `target_time_minutes IS NULL OR > 0`
- FK to athletes CASCADES on deletion
- Recovery goal with MODERATE injury severity round-trips
- Minimal goal persists with all optional fields NULL

---

### 3. Secondary Event Schema (`phase-1-2b-secondary-event-schema`)

**Tests:**
- Unit: `tests/unit/test_secondary_event_columns.py`
- Integration: `tests/integration/test_secondary_event_schema.py`

**Invariants Protected:**
- Full column set present
- `event_type` uses `GoalEventType` enum
- `priority` uses `SecondaryEventPriority` enum (B or C)
- `event_date` is required
- `event_name` is nullable
- FK to `training_goals` CASCADES on deletion
- Indexes on (`training_goal_id`) and (`training_goal_id`, `event_date`)
- Minimal {type, date, priority} row persists without `event_name`

---

### 4. Regeneration Task Schema (`phase-1-2b-regeneration-task-schema`)

**Tests:**
- Unit: `tests/unit/test_regeneration_task_columns.py`
- Integration: `tests/integration/test_regeneration_task_schema.py`

**Invariants Protected:**
- Full column set present
- FK to `training_goals` CASCADES on deletion
- FK to `training_plans` SET NULLs on plan deletion (task survives)
- CHECK: `status IN ('pending_confirmation', 'confirmed', 'declined', 'expired')`
- Partial index `ix_regeneration_tasks_pending` WHERE `status='pending_confirmation'`
- Pending row carries NULL `training_plan_id`
- Confirmed row links to its new plan
- `decided_at` is nullable; set on confirmation

---

### 5. Training Plan Schema (`phase-1-2b-training-plan-schema`)

**Tests:**
- Unit: `tests/unit/test_training_plan_columns.py`
- Integration: `tests/integration/test_training_plan_schema.py`

**Invariants Protected:**
- Full column set present
- FK to `training_goals` CASCADES on deletion
- `twin_state_id` is nullable UUID WITHOUT FK (deferred to Phase 1.2c)
- JSONB structural columns default to empty arrays / NULL
- Supersession is non-destructive (`superseded_at` + `status='superseded'`)

---

### 6. Weekly Plan Schema (`phase-1-2b-weekly-plan-schema`)

**Tests:**
- Unit: `tests/unit/test_weekly_plan_columns.py`
- Integration: `tests/integration/test_weekly_plan_schema.py`

**Invariants Protected:**
- Full column set present
- UNIQUE (`training_plan_id`, `week_number`)
- FK to `training_plans` CASCADES on deletion
- CHECK: `week_number >= 1`
- Minimal plan persists with `week_number=1`

---

### 7. Planned Session Schema (`phase-1-2b-planned-session-schema`)

**Tests:**
- Unit: `tests/unit/test_planned_session_columns.py`
- Integration: `tests/integration/test_planned_session_schema.py`

**Invariants Protected:**
- Full column set present
- UNIQUE (`weekly_plan_id`, `target_date`, `session_slot`)
- FK to `weekly_plans` CASCADES on deletion
- FK to `training_plans` CASCADES on deletion (denormalized)
- CHECK: `approximate_duration_minutes > 0`
- CHECK: `week_number >= 1`
- `block_position` bounded to {first, middle, last}
- `session_priority` is required (PRIMARY or SECONDARY)
- `session_slot` is nullable (single-session days)

---

### 8. Checkpoint Schema (`phase-1-2b-checkpoint-schema`)

**Tests:**
- Unit: `tests/unit/test_checkpoint_columns.py`
- Integration: `tests/integration/test_checkpoint_schema.py`

**Invariants Protected:**
- Full column set present
- UNIQUE + NOT NULL `planned_session_id` (strict 1:1 with PlannedSession)
- NO `training_plan_id` column (derived via PlannedSession → WeeklyPlan → TrainingPlan)
- FK to `planned_sessions` CASCADES on deletion
- CHECK: `status IN ('scheduled', 'completed', 'skipped')`
- CHECK: `trajectory_status IN ('ahead', 'on_track', 'behind', 'at_risk')`
- `secondary_metrics` ARRAY(String) round-trips

---

### 9. Activity Schema Extension (`phase-1-2b-activity-schema-extension`)

**Tests:**
- Integration: `tests/integration/test_activity_schema.py` (updated)

**Invariants Protected:**
- `activities.planned_session_id` FK to `planned_sessions.id` with ON DELETE SET NULL
- FK constraint appears in `pg_constraint`
- FK uses `confdeltype='n'` (SET NULL)
- FK trigger fires on `planned_session` deletion
- Activity row survives `planned_session` deletion

---

### 10. Migration (`phase-1-2b-migration`)

**Tests:**
- Integration: `tests/integration/test_migration_phase_1_2b.py`

**Invariants Protected:**
- `alembic upgrade head` on fresh database succeeds (rc=0)
- `alembic downgrade -1` returns schema to Phase 1.2a baseline
- Delivered revision equals `1b9e9026db1e`
- `down_revision` chains from Phase 1.2a head (`e7ffc8764335`)
- Migration never drops Phase 1.1 / Phase 1.2a tables
- All 8 Phase 1.2b tables created
- `ix_training_goals_athlete_active` emitted with predicate
- `ix_regeneration_tasks_pending` emitted with predicate
- `uq_weekly_plans_plan_week` UNIQUE emitted
- `uq_planned_sessions_plan_date_slot` UNIQUE emitted
- Checkpoints UNIQUE on `planned_session_id` emitted
- `fk_activities_planned_session` FK emitted with ON DELETE SET NULL
- `training_plans.twin_state_id` WITHOUT FK (deferred to Phase 1.2c)

---

## Test File Inventory

### Unit Tests (8 files)
- `tests/unit/test_enum_values.py`
- `tests/unit/test_training_goal_columns.py`
- `tests/unit/test_secondary_event_columns.py`
- `tests/unit/test_regeneration_task_columns.py`
- `tests/unit/test_training_plan_columns.py`
- `tests/unit/test_weekly_plan_columns.py`
- `tests/unit/test_planned_session_columns.py`
- `tests/unit/test_checkpoint_columns.py`

### Integration Tests (9 files)
- `tests/integration/test_training_goal_schema.py`
- `tests/integration/test_secondary_event_schema.py`
- `tests/integration/test_regeneration_task_schema.py`
- `tests/integration/test_training_plan_schema.py`
- `tests/integration/test_weekly_plan_schema.py`
- `tests/integration/test_planned_session_schema.py`
- `tests/integration/test_checkpoint_schema.py`
- `tests/integration/test_activity_schema.py` (updated for Phase 1.2b FK)
- `tests/integration/test_migration_phase_1_2b.py`

---

## Coverage Classification

### Routes
- **Covered:** None (Phase 1.2b is schema-only; API endpoints come in Phase 1.2c+)
- **Missing:** All training goal/plan/session API endpoints (out of scope)

### Events
- **Covered:** None (Phase 1.2b is schema-only)
- **Missing:**
  - `training_plan_generated`
  - `planned_session_generated`
  - `session_completed`
  - `session_skipped`
  - `session_missed`
  - `weekly_plan_created`
  - `week_completed`
  - `checkpoint_completed`

### Invariants
- **Covered:** 88 invariants (see feature sections above)
- **Partial:** None
- **Missing:** None (all Phase 1.2b schema invariants are tested)

---

## Execution Groups

### p1-2b-p1-unit (smoke scope)
- 8 unit test files
- No DB/container dependencies
- Fast execution (<10 seconds total)

### p1-2b-p1-integration (feature scope)
- 8 integration test files
- Requires test DB with Phase 1.2b schema
- Validates DB-level constraints, indexes, FKs

### p1-2b-p1-migration (feature scope)
- 1 migration test file
- Tests upgrade/downgrade paths
- Depends on p1-2b-p1-unit and p1-2b-p1-integration

### Cross-Phase Dependencies
- `p1-2a-p1-integration` → `p1-2b-p1-integration` (runs before)
- `p1-2a-p1-migration` → `p1-2b-p1-migration` (runs before)

---

## Known Issues & Resolutions

### Issue 1: PlannedSessionStatus.SCHEDULED does not exist
**Location:** `tests/integration/test_activity_schema.py:592`  
**Resolution:** Changed to `PlannedSessionStatus.PENDING`  
**Root Cause:** Enum has PENDING, GENERATED, COMPLETED, SKIPPED, MISSED, REDISTRIBUTED — no SCHEDULED

### Issue 2: Missing required session_priority field
**Location:** `tests/integration/test_activity_schema.py:594`  
**Resolution:** Added `session_priority=SessionPriority.PRIMARY` to PlannedSession constructor  
**Root Cause:** `session_priority` is NOT NULL with no default; test factory must provide it

---

## Promotion Summary

All 10 Phase 1.2b features have been promoted:

| Feature | Status | Tests |
|---|---|---|
| phase-1-2b-enums | promoted | 1 unit |
| phase-1-2b-training-goal-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-secondary-event-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-regeneration-task-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-training-plan-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-weekly-plan-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-planned-session-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-checkpoint-schema | promoted | 1 unit + 1 integration |
| phase-1-2b-activity-schema-extension | promoted | 1 integration |
| phase-1-2b-migration | promoted | 1 integration |

**Total:** 17 test files (8 unit + 9 integration)

---

## Next Phase

Phase 1.2c will deliver:
- Twin state infrastructure
- Workout generation service integration
- Session lifecycle events
- API endpoints for training plan management

This test pack provides the foundation for testing those services.