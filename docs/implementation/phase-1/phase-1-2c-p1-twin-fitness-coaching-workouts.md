# Implementation Plan: Phase-1.2c — Core Models: Twin, Fitness, Coaching, Workouts
## Plan ID: Phase-1.2c-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.2c
Sub-Phase Title: Phase 1 — Core Models: Twin, Fitness, Physiology, Coaching & Workouts

## Objective
Establish the schema for the athlete's digital twin (fitness, physiology, snapshots), coaching output (messages, generation events), and workout structure. This is a pure schema sub-phase — no services or endpoints are built here. The models created form the foundation for all downstream coaching, workout generation, and FIT import features.

## Scope
- Schema for `TwinState` (append-only inline snapshots of fitness/fatigue/thresholds)
- Schema for `AthletePhysiology` (per-dimension Bayesian state, mutable)
- Schema for `AthleteFitness` (Banister scores, mutable)
- Schema for `CoachingMessage` (write-once, append-only)
- Schema for `GenerationEvent` (every LLM call, success or failure)
- Schema for `GeneratedWorkout` (two-column target structure, immutable)
- Schema for `WorkoutStep` (individual steps with physiological intent)
- New enums: `TwinTrigger`, `TwinConfidenceLevel`, `MessageType`, `StepType`, `RecoveryModifierLevel`, `WellnessTrend`
- Alembic migration for all tables with constraints and indexes
- Model registration in `app/models/__init__.py`

## Out Of Scope
- No services (TwinRecalibrationService, FitnessUpdateService, etc.) — deferred to later sub-phases
- No API endpoints — deferred to Phase 1.3, 1.5, 1.6
- No data written to any tables in this sub-phase — schema creation only
- No `PhysiologyMeasurement` table — deferred to Phase 2+
- No `RawSensorStream`, `PhysiologicalSegment`, `ExecutionObservation` — deferred to Phases 4-6
- Event producers/consumers — schema only, event publication deferred

## Architecture Contracts
- `01-entities/twin-state.md` — IMPLEMENTS
- `01-entities/athlete-physiology.md` — IMPLEMENTS
- `01-entities/athlete-fitness.md` — IMPLEMENTS
- `01-entities/coaching-message.md` — IMPLEMENTS
- `01-entities/generation-event.md` — IMPLEMENTS
- `01-entities/generated-workout.md` — IMPLEMENTS
- `01-entities/workout-step.md` — IMPLEMENTS
- `00-foundations/terminology.md` — DEPENDS ON (enum definitions)
- `00-foundations/confidence-model.md` — DEPENDS ON (confidence level semantics)
- `01-entities/athlete.md` — DEPENDS ON (FK target)
- `01-entities/training-goal.md` — DEPENDS ON (FK target for TwinState)
- `01-entities/activity.md` — DEPENDS ON (FK target for TwinState, CoachingMessage)
- `01-entities/planned-session.md` — DEPENDS ON (FK target for GeneratedWorkout)

## Invariants
- `TwinState` is append-only — no UPDATE or DELETE. Repository exposes only `insert`, `get_latest`, `get_by_activity`, `get_history`.
- `TwinState.confidence_level` is derived as `min(AthletePhysiology.lt1.hr.prior_weight, AthletePhysiology.lt2.hr.prior_weight)` at each snapshot.
- `TwinState.training_goal_id`, `model_version`, and `activity_id` are frozen at creation time.
- `AthleteFitness`: one per athlete, mutable. `form` must always equal `fitness - fatigue`.
- `AthletePhysiology`: one per athlete, mutable. `max_hr` bootstrapped from `220 - age`.
- `CoachingMessage` is immutable after creation. `first_message` — only one per active goal. `post_workout` — one per `activity_id`.
- `GenerationEvent` is written for every LLM call, success or failure. Records are never modified.
- `GeneratedWorkout` is append-only. `theoretical_targets` and `adjusted_targets` always both written.
- `WorkoutStep.physiological_intent` is never null.

## Implementation Steps

1. **[OWNER: Coder]** Add new enums to `app/models/enums.py`:
   - `TwinTrigger`: questionnaire, activity_sync, calibration, physiology_input, wellness_update
   - `TwinConfidenceLevel`: low, medium, high
   - `MessageType`: first_message, post_workout, wellness_alert, phase_transition, plan_regeneration, confidence_upgrade, cycle_check_in, weekly_summary
   - `StepType`: warmup, work, recovery, cooldown
   - `RecoveryModifierLevel`: green, amber, red
   - `WellnessTrend`: improving, stable, declining
   - `PhysiologicalIntent`: low_aerobic, high_aerobic, threshold, vo2max, neuromuscular, recovery
   - `MeasurementSource`: questionnaire_estimate, training_hr_deflection, training_rr_inflection, training_power_hr_ratio, field_test, lab_test
   - `SignalType`: power, gap, hr, description

2. **[OWNER: Coder]** Create `app/models/twin_state.py`:
   - Implement `TwinState` model with all fields from architecture contract
   - Include `metric_confidence` as JSONB column
   - Add unique constraint on `(athlete_id, activity_id)` where `activity_id IS NOT NULL`
   - Add index on `(athlete_id, created_at DESC)` for latest query
   - No `update()` or `delete()` methods on the model or future repository

3. **[OWNER: Coder]** Create `app/models/athlete_physiology.py`:
   - Implement `AthletePhysiology` model with nested parameter states
   - Use JSONB for `lt1`, `lt2`, `cp`, `vo2max`, `max_hr` parameter states
   - Add unique constraint on `athlete_id`
   - Include `updated_at` timestamp

4. **[OWNER: Coder]** Create `app/models/athlete_fitness.py`:
   - Implement `AthleteFitness` model with aggregate and dimensional scores
   - Include `time_constants` as JSONB with `BanisterTimeConstants` structure
   - Add hybrid property or check constraint to enforce `form = fitness - fatigue`
   - Add unique constraint on `athlete_id`
   - Include `last_activity_id` FK and `updated_at` timestamp

5. **[OWNER: Coder]** Create `app/models/coaching_message.py`:
   - Implement `CoachingMessage` model with all fields from architecture contract
   - Add index on `(athlete_id, generated_at DESC)` for message feed
   - Add index on `(athlete_id, message_type, generated_at DESC)` for frequency guards
   - No `update()` or `delete()` methods

6. **[OWNER: Coder]** Create `app/models/generation_event.py`:
   - Implement `GenerationEvent` model with all fields from architecture contract
   - `failure_reason` must be non-null when `success = false` (add check constraint)
   - Add index on `(athlete_id, created_at DESC)` for per-athlete audit
   - Add index on `(agent_name, created_at DESC)` for per-agent monitoring
   - Add index on `(success, created_at DESC)` for failure rate dashboards

7. **[OWNER: Coder]** Create `app/models/generated_workout.py`:
   - Implement `GeneratedWorkout` model with all fields from architecture contract
   - `theoretical_targets` and `adjusted_targets` as JSONB columns
   - Add unique constraint on `(planned_session_id, generation_date)` for idempotency
   - Add FK to `TwinState` for `twin_state_id`
   - Include `recovery_modifier_level` with default 'green'

8. **[OWNER: Coder]** Create `app/models/workout_step.py`:
   - Implement `WorkoutStep` model with all fields from architecture contract
   - `target` as JSONB column with `WorkoutTarget` structure
   - Add unique constraint on `(generated_workout_id, step_order)`
   - Add check constraint to ensure `physiological_intent` is never null
   - Add FK to `GeneratedWorkout`

9. **[OWNER: Coder]** Update `app/models/__init__.py`:
   - Import all new models: `TwinState`, `AthletePhysiology`, `AthleteFitness`, `CoachingMessage`, `GenerationEvent`, `GeneratedWorkout`, `WorkoutStep`
   - Import all new enums: `TwinTrigger`, `TwinConfidenceLevel`, `MessageType`, `StepType`, `RecoveryModifierLevel`, `WellnessTrend`, `PhysiologicalIntent`, `MeasurementSource`, `SignalType`

10. **[OWNER: Coder]** Generate Alembic migration:
    - Run `alembic revision --autogenerate -m "phase_1_2c_twin_fitness_coaching_workouts"`
    - Ensure migration creates all 7 tables with correct constraints and indexes
    - Verify migration includes all foreign key relationships

11. **[OWNER: DevOps]** Review and apply migration:
    - Review autogenerated migration for correctness
    - Add hypertable configuration if TimescaleDB is used for time-series tables
    - Run `db-upgrade.sh` to apply to test database
    - Verify all tables, constraints, and indexes are created correctly

12. **[OWNER: Test Architect]** Create unit tests for all models:
    - Test enum values match architecture contracts exactly
    - Test nullable/non-nullable constraints
    - Test unique constraints
    - Test check constraints (form computation, failure_reason presence)
    - Test foreign key relationships

13. **[OWNER: Test Architect]** Create integration tests for schema:
    - Test migration runs cleanly on fresh database
    - Test TwinState cannot be updated or deleted (repository contract)
    - Test AthleteFitness form = fitness - fatigue invariant
    - Test GeneratedWorkout idempotency constraint
    - Test WorkoutStep step_order uniqueness within workout

14. **[OWNER: Test Architect]** Update test manifest:
    - Add new test files to `tests/test-manifest/phase-1-2c.yaml`
    - Update `tests/test-manifest/index.yaml` to include phase-1-2c

## Event Contracts
This sub-phase defines schema only. Event production/consumption is deferred to later sub-phases (1.3, 1.5, 1.6). The following events will reference these entities when implemented:

**Future Events (not implemented in this sub-phase):**
- `twin_recalibrated` — produced when TwinState inserted (Phase 1.3)
- `twin_confidence_upgraded` — produced when confidence_level increases (Phase 1.3)
- `twin_model_ready` — produced when first TwinState created (Phase 1.3)
- `physiology_updated` — produced when AthletePhysiology posterior shifts (Phase 1.6)
- `fitness_updated` — produced when AthleteFitness updated (Phase 1.6)
- `coaching_message_generated` — produced when CoachingMessage inserted (Phase 1.5)
- `workout_generated` — produced when GeneratedWorkout inserted (Phase 1.5b)

## Pseudocode
No orchestration logic in this sub-phase (schema only).

### JSONB Structure Examples

**TwinState.metric_confidence:**
```json
{
  "lt1_hr": "low",
  "lt1_power": null,
  "lt1_pace": null,
  "lt2_hr": "low",
  "lt2_power": null,
  "lt2_pace": null,
  "cp": null
}
```

**AthletePhysiology.lt1:**
```json
{
  "hr": {
    "value": 152.0,
    "uncertainty": 8.5,
    "prior_weight": 0.5,
    "dominant_source": "questionnaire_estimate",
    "last_observation_date": "2026-06-24"
  },
  "power": null,
  "pace": null
}
```

**AthleteFitness.aggregate:**
```json
{
  "fitness": 0.0,
  "fatigue": 0.0,
  "form": 0.0
}
```

**GeneratedWorkout.theoretical_targets:**
```json
{
  "targets": [
    {
      "signal_type": "gap",
      "primary": {"min": 270, "max": 300, "unit": "sec/km"},
      "fallback": null,
      "description": "Easy aerobic pace"
    }
  ],
  "description": "Recovery run at conversational pace"
}
```

**WorkoutStep.target:**
```json
{
  "signal_type": "hr",
  "primary": {"min": 130, "max": 145, "unit": "bpm"},
  "fallback": null,
  "description": "Keep heart rate in aerobic zone"
}
```

## Testing Requirements
- All enums have exact values matching terminology.md and architecture contracts
- `TwinState` table has no UPDATE or DELETE methods in repository
- `TwinState` enforces unique constraint on `(athlete_id, activity_id)` where activity_id is not null
- `AthleteFitness` model enforces `form = fitness - fatigue` at application level
- `AthletePhysiology` has unique constraint on `athlete_id`
- `CoachingMessage` has no UPDATE or DELETE methods in repository
- `GenerationEvent` requires `failure_reason` when `success = false`
- `GeneratedWorkout` enforces unique constraint on `(planned_session_id, generation_date)`
- `GeneratedWorkout` always has both `theoretical_targets` and `adjusted_targets` non-null
- `WorkoutStep` enforces `physiological_intent` is never null
- `WorkoutStep` enforces unique constraint on `(generated_workout_id, step_order)`
- Migration runs cleanly on fresh database with no errors
- All foreign key relationships are correctly established

## Coder Handoff Notes
- **Critical Invariant**: TwinState is append-only. The repository you create in a future phase MUST NOT expose update() or delete() methods. Design the model now with this in mind (no __update__ methods).
- **JSONB Columns**: Several entities use JSONB for complex nested structures (metric_confidence, parameter states, targets). Use SQLAlchemy's `JSONB` type from `sqlalchemy.dialects.postgresql`.
- **Form Computation**: AthleteFitness.form should be a computed property or hybrid property that always returns `fitness - fatigue`. Do not store it as a separate mutable field.
- **Unique Constraints**: Pay special attention to partial unique indexes (e.g., TwinState activity_id where not null). Use PostgreSQL's `CREATE UNIQUE INDEX ... WHERE ...` syntax.
- **Enum Alignment**: Copy enum values EXACTLY from the architecture contracts. These are part of the public API contract and changing them later is a breaking change.
- **WellnessTrend Enum**: The architecture doesn't explicitly define this, but based on context from athlete-fitness (form_trend) and wellness-alert-agent (trend_direction), use: 'improving', 'stable', 'declining'.
- **GeneratedWorkout Targets**: Both theoretical_targets and adjusted_targets must ALWAYS be written, even when identical. This is a deliberate architectural decision for the two-column display.
- **Migration Strategy**: This is a large migration with 7 tables. Ensure foreign keys are created in the correct order to avoid circular dependency issues. Suggested order: TwinState, AthletePhysiology, AthleteFitness, GenerationEvent, CoachingMessage, GeneratedWorkout, WorkoutStep.
- **No Services Yet**: This sub-phase is schema only. Do not create repositories, services, or API endpoints. Those are deferred to Phase 1.3 and later.

## Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8, 9, 10  [OWNER: Coder] — includes migration generation
Skip:     Step 11 (DevOps — migration review and application),
          Step 12, 13, 14 (Test Architect — tests)
