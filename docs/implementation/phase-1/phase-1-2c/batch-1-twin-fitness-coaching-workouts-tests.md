> **Baseline — test companion for** `batch-1-twin-fitness-coaching-workouts.md`, migrated from `docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md` + `phase-1-2c-p1-fix-missing-fk.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements. Schema-only plan — tests focus on migration, model metadata, and constraint enforcement.

### Migration
- Given `alembic upgrade head` succeeds from Phase 1-2b head on a fresh database
- Given `alembic downgrade -1` succeeds and reverts Phase 1-2c schema
- Given main migration creates 7 tables: `twin_states`, `athlete_physiology`, `athlete_fitness`, `generation_events`, `coaching_messages`, `generated_workouts`, `workout_steps`
- Given FK fix migration creates `fk_training_plans_twin_state` constraint
- Given downgrade of FK fix drops the constraint without errors

### TwinState
- Given `twin_states` contains all fields from architecture contract: `athlete_id`, `training_goal_id`, `activity_id`, `data_tier`, `confidence_level`, `trigger`, `model_version`, `fitness`/`fatigue`/`form`, `lt1_`/`lt2_` thresholds, `cp_watts`, `readiness_level`, `wellness_trend`, `metric_confidence`, `created_at`
- Given `activity_id` is nullable
- Given partial unique index on `(athlete_id, activity_id) WHERE activity_id IS NOT NULL`
- Given inserting two TwinStates with same `(athlete_id, null)` succeeds (nulls not constrained)
- Given inserting two TwinStates with same `(athlete_id, same_activity_id)` raises uniqueness violation
- Given `confidence_level` is `TwinConfidenceLevel` enum with values `low`, `medium`, `high`
- Given `trigger` is `TwinTrigger` enum with value `questionnaire`
- Given `metric_confidence` is JSONB column
- Given index on `(athlete_id, created_at DESC)` exists for latest query

### AthletePhysiology
- Given `athlete_physiology` has unique `athlete_id`
- Given `lt1` and `lt2` are JSONB columns — structure: `{hr: {value, uncertainty, prior_weight, dominant_source, last_observation_date}, power: null, pace: null}`
- Given `cp`, `vo2max`, `max_hr` are nullable JSONB columns
- Given inserting two physiology rows for same athlete raises uniqueness violation

### AthleteFitness
- Given `athlete_fitness` has unique `athlete_id`
- Given `aggregate` is JSONB column — structure: `{fitness: 0.0, fatigue: 0.0, form: 0.0}`
- Given CHECK constraint enforces `form = fitness - fatigue`
- Given inserting `{fitness: 10, fatigue: 5, form: 10}` raises CHECK violation (10 ≠ 10-5)
- Given inserting `{fitness: 10, fatigue: 5, form: 5}` succeeds
- Given `aerobic`, `neuromuscular`, `structural` are nullable JSONB columns
- Given `time_constants` is JSONB with `{source, aerobic, neuromuscular, structural, fitted_at}`
- Given `last_activity_id` FK to `activities.id` is nullable

### CoachingMessage
- Given `coaching_messages` has unique partial index on `(athlete_id) WHERE message_type = 'first_message'`
- Given unique partial index on `(athlete_id, activity_id) WHERE message_type = 'post_workout'`
- Given inserting two `first_message` records for same athlete raises uniqueness violation
- Given inserting two `post_workout` records for same `(athlete_id, activity_id)` raises uniqueness violation
- Given `message_type` is `MessageType` enum
- Given `content` is `Text` column (non-null)
- Given `prompt_version` is `String(32)`
- Given `generated_at` has server default `now()`
- Given `twin_state_id` FK to `twin_states.id` and `activity_id` FK to `activities.id` (nullable)

### GenerationEvent
- Given `generation_events` has CHECK constraint: `failure_reason IS NOT NULL` when `success = false`
- Given CHECK constraint: `failure_reason IS NULL` when `success = true`
- Given inserting `success=true, failure_reason='error'` raises CHECK violation
- Given inserting `success=false, failure_reason=null` raises CHECK violation
- Given inserting `success=false, failure_reason='timeout'` succeeds
- Given inserting `success=true, failure_reason=null` succeeds
- Given `agent_name` is `String(96)` (non-null)
- Given `input_token_count`, `output_token_count`, `latency_ms` are non-negative CHECK constraints
- Given indexes on `(athlete_id, created_at DESC)`, `(agent_name, created_at DESC)`, `(success, created_at DESC)`

### GeneratedWorkout
- Given `generated_workouts` has unique constraint on `(planned_session_id, generation_date)`
- Given inserting two workouts for same `(session_id, date)` raises uniqueness violation
- Given `theoretical_targets` and `adjusted_targets` are non-null JSONB columns (both always written)
- Given `recovery_modifier_level` defaults to `'green'`
- Given `recovery_modifier_reason` is nullable
- Given `twin_state_id` FK to `twin_states.id`
- Given `planned_session_id` FK to `planned_sessions.id`

### WorkoutStep
- Given `workout_steps` has unique constraint on `(generated_workout_id, step_order)`
- Given inserting two steps with same `(workout_id, step_order)` raises uniqueness violation
- Given `physiological_intent` is non-null CHECK constraint — inserting null intent raises violation
- Given `physiological_intent` is `PhysiologicalIntent` enum
- Given `description` is non-empty CHECK constraint — inserting empty string raises violation
- Given `step_order` is positive CHECK constraint
- Given `duration_seconds` is non-negative CHECK constraint
- Given `target` is JSONB column with `WorkoutTarget` structure: `{signal_type, primary, fallback, description}`
- Given `session_purpose` defaults to `'general'`

### FK Fix: training_plans.twin_state_id
- Given `training_plans.twin_state_id` has FK to `twin_states.id` with `ON DELETE SET NULL`
- Given deleting a `TwinState` referenced by a `TrainingPlan` sets `twin_state_id = NULL`
- Given inserting `TrainingPlan` with `twin_state_id` referencing non-existent `TwinState` raises FK violation
- Given Alembic downgrade of FK fix migration drops the constraint successfully
- Given FK fix migration does NOT modify the existing `79dc97d4e433` migration file

### Enum Values
- Given `TwinTrigger`: `questionnaire`, `activity_sync`, `calibration`, `physiology_input`, `wellness_update`
- Given `TwinConfidenceLevel`: `low`, `medium`, `high`
- Given `MessageType`: `first_message`, `post_workout`, plus deferred types
- Given `StepType`: `warmup`, `work`, `recovery`, `cooldown`
- Given `RecoveryModifierLevel`: `green`, `amber`, `red`
- Given `WellnessTrend`: `improving`, `stable`, `declining`
- Given `PhysiologicalIntent`: `low_aerobic`, `high_aerobic`, `threshold`, `vo2max`, `neuromuscular`, `recovery`
- Given `MeasurementSource`: `questionnaire_estimate`, `training_hr_deflection`, `training_rr_inflection`, `training_power_hr_ratio`, `field_test`, `lab_test`
- Given `SignalType`: `power`, `gap`, `hr`, `description`
- Given all enum values match `00-foundations/terminology.md` and architecture contracts exactly

### No Backward Breakage
- Given existing Phase 1-2b tables are preserved (training_goals, training_plans, weekly_plans, etc.)
- Given existing `Activity` model tests pass (no regression)
- Given migration runs cleanly on fresh database from Phase 1-2b baseline