> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-2c-p1-twin-fitness-coaching-workouts.md` + `phase-1-2c-p1-fix-missing-fk.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-2c, including the post-migration FK fix, verified against the current codebase on 2026-07-19.

## Batch Objective

Establish the schema for the athlete's digital twin (fitness, physiology, snapshots), coaching output (messages, generation events), and workout structure. This is a pure schema sub-phase — no services or endpoints are built here. The models created form the foundation for all downstream coaching, workout generation, and FIT import features. Also resolves the deferred `training_plans.twin_state_id` foreign key constraint that was intentionally omitted in Phase 1-2b.

## Preconditions

- Phase 1-2b migration is applied: `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, `PlannedSession`, `Checkpoint` exist
- `training_plans.twin_state_id` column exists as nullable UUID but has no FK constraint
- `Activity`, `AthleteProfile`, `AthletePreferences` exist (from 1-2a)
- `TrainingGoal` exists (from 1-2b)
- `PlannedSession` exists (from 1-2b) — FK target for `GeneratedWorkout`

## Scope

- `TwinState` model — append-only inline snapshots (fitness/fatigue/thresholds/confidence/metrics)
- `AthletePhysiology` model — per-dimension Bayesian state, mutable, unique per athlete
- `AthleteFitness` model — Banister scores, mutable, unique per athlete, `form = fitness - fatigue`
- `CoachingMessage` model — write-once, append-only, partial unique indexes for first_message and post_workout
- `GenerationEvent` model — every LLM call audit trail, `failure_reason` consistency check
- `GeneratedWorkout` model — two-column target structure, unique `(planned_session_id, generation_date)`, append-only
- `WorkoutStep` model — steps with physiological intent, unique `(generated_workout_id, step_order)`, intent never null
- New enums: 9 enums for the above models
- Alembic migration for all 7 tables
- FK fix: add `ForeignKe("twin_states.id", ondelete="SET NULL")` on `training_plans.twin_state_id` (deferred from 1-2b)
- Model registration in `app/models/__init__.py`

## Out Of Scope

- No services (TwinRecalibrationService, FitnessUpdateService, etc.)
- No API endpoints
- No data written to any tables — schema creation only
- No `PhysiologyMeasurement` table
- No `RawSensorStream`, `PhysiologicalSegment`, `ExecutionObservation`
- Event publication — events reference these entities but are produced in later phases

## Steps

1. [OWNER: Coder] Add new enums to `app/models/enums.py`: `TwinTrigger` (questionnaire, activity_sync, calibration, physiology_input, wellness_update), `TwinConfidenceLevel` (low, medium, high), `MessageType` (first_message, post_workout, etc.), `StepType` (warmup, work, recovery, cooldown), `RecoveryModifierLevel` (green, amber, red), `WellnessTrend` (improving, stable, declining), `PhysiologicalIntent` (low_aerobic, high_aerobic, threshold, vo2max, neuromuscular, recovery), `MeasurementSource` (questionnaire_estimate, training_hr_deflection, etc.), `SignalType` (power, gap, hr, description).

2. [OWNER: Coder] Create `TwinState` model: `athlete_id` (FK), `training_goal_id` (FK), `activity_id` (FK, nullable), `data_tier`, `confidence_level`, `trigger`, `model_version`, `fitness`/`fatigue`/`form`, `lt1_`/`lt2_` thresholds (pace/power/hr, nullable), `cp_watts` (nullable), `readiness_level`, `wellness_trend` (nullable), `metric_confidence` (JSONB), `created_at`. Append-only — no UPDATE/DELETE methods. Unique on `(athlete_id, activity_id) WHERE activity_id IS NOT NULL`.

3. [OWNER: Coder] Create `AthletePhysiology` model: `athlete_id` (unique FK), `lt1`/`lt2` JSONB (nested `{value, uncertainty, prior_weight, dominant_source, last_observation_date}`), `cp`/`vo2max`/`max_hr` JSONB (nullable), `updated_at`. Mutable — one per athlete.

4. [OWNER: Coder] Create `AthleteFitness` model: `athlete_id` (unique FK), `aggregate` JSONB (`{fitness, fatigue, form}`), `aerobic`/`neuromuscular`/`structural` JSONB (nullable), `time_constants` JSONB, `last_activity_id` FK (nullable), `updated_at`. Mutable — one per athlete. CHECK constraint: `form = fitness - fatigue`.

5. [OWNER: Coder] Create `CoachingMessage` model: `athlete_id` (FK), `twin_state_id` (FK), `activity_id` (FK, nullable), `message_type`, `content`, `prompt_version`, `generated_at`. Append-only. Partial unique indexes: `(athlete_id) WHERE message_type = 'first_message'`, `(athlete_id, activity_id) WHERE message_type = 'post_workout'`.

6. [OWNER: Coder] Create `GenerationEvent` model: `athlete_id` (FK), `agent_name`, `prompt_version`, `trigger_context`, `input_token_count`, `output_token_count`, `latency_ms`, `success`, `failure_reason` (nullable), `created_at`. Append-only. CHECK constraint: `failure_reason IS NOT NULL` iff `success = false`.

7. [OWNER: Coder] Create `GeneratedWorkout` model: `planned_session_id` (FK), `twin_state_id` (FK), `theoretical_targets`/`adjusted_targets` JSONB (both non-null), `recovery_modifier_level` (default `green`), `recovery_modifier_reason` (nullable), `generation_date`, `generated_at`. Unique on `(planned_session_id, generation_date)`. Append-only.

8. [OWNER: Coder] Create `WorkoutStep` model: `generated_workout_id` (FK), `step_order`, `step_type`, `session_type`, `physiological_intent` (non-null CHECK), `session_purpose` (default `general`), `target` JSONB, `duration_seconds` (nullable), `description` (non-null CHECK). Unique on `(generated_workout_id, step_order)`. Append-only.

9. [OWNER: Coder] Register all new models and enums in `app/models/__init__.py`.

10. [OWNER: Coder] Generate Alembic migration from Phase 1-2b head: creates 7 tables with constraints and indexes. Migration order: TwinState, AthletePhysiology, AthleteFitness, GenerationEvent, CoachingMessage, GeneratedWorkout, WorkoutStep (avoid circular FK deps).

### FK Fix: training_plans.twin_state_id

11. [OWNER: Coder] In `app/models/training_plan.py`, update `twin_state_id` column to include deferred FK: `ForeignKe("twin_states.id", ondelete="SET NULL")`. Remove the docstring comment about deferral. Generate a new Alembic migration (`add_training_plans_twin_state_fk`) that creates the FK. Migration must include `op.drop_constraint` in downgrade.

## Context Needed

- `01-entities/twin-state.md` — append-only snapshot schema
- `01-entities/athlete-physiology.md` — Bayesian state schema
- `01-entities/athlete-fitness.md` — Banister scores, time constants
- `01-entities/coaching-message.md` — message types, append-only, idempotency indexes
- `01-entities/generation-event.md` — LLM audit trail, failure_reason consistency
- `01-entities/generated-workout.md` — two-column target, idempotency
- `01-entities/workout-step.md` — steps with physiological intent
- `01-entities/training-plan.md` — FK fix target
- `00-foundations/terminology.md` — enum values
- `00-foundations/confidence-model.md` — confidence level semantics

## Batch Success Criteria

- `alembic upgrade head` succeeds on fresh database from Phase 1-2b head
- `alembic downgrade -1` succeeds
- All 7 tables created with correct columns, types, constraints, and indexes
- `TwinState` table has partial unique index on `(athlete_id, activity_id) WHERE activity_id IS NOT NULL`
- `AthleteFitness` has unique `athlete_id` and CHECK enforcing `form = fitness - fatigue`
- `AthletePhysiology` has unique `athlete_id`
- `CoachingMessage` has partial unique indexes for `first_message` and `post_workout`
- `GenerationEvent` has CHECK: `failure_reason IS NOT NULL` when `success = false`, `failure_reason IS NULL` when `success = true`
- `GeneratedWorkout` has unique `(planned_session_id, generation_date)` and both target columns non-null
- `WorkoutStep` has unique `(generated_workout_id, step_order)`, `physiological_intent` non-null CHECK, `description` non-empty CHECK
- All 9 enums have exact values matching terminology.md
- FK fix: `training_plans.twin_state_id` has FK to `twin_states.id` with `ON DELETE SET NULL`
- No services, APIs, or event publishers added

## Files Expected To Change

- `app/models/enums.py` — add 9 new enums
- `app/models/twin_state.py` — new model
- `app/models/athlete_physiology.py` — new model
- `app/models/athlete_fitness.py` — new model
- `app/models/coaching_message.py` — new model
- `app/models/generation_event.py` — new model
- `app/models/generated_workout.py` — new model
- `app/models/workout_step.py` — new model
- `app/models/training_plan.py` — add FK on twin_state_id (FK fix)
- `app/models/__init__.py` — register new models + enums
- `migrations/versions/<rev>_phase_1_2c_twin_fitness_coaching_workouts.py` — main migration
- `migrations/versions/<rev>_add_training_plans_twin_state_fk.py` — FK fix migration

## Coder Notes

- **Schema-only**. No services, repositories, APIs, or event producers. Models and migrations only.
- **TwinState is append-only**. Design the model now with no update/delete methods. The repository contract must reflect this in later phases.
- **AthleteFitness form invariant**. `form` should be a computed property or CHECK-constrained to always equal `fitness - fatigue`. Do not store as a separately mutable field.
- **JSONB columns**. `metric_confidence`, `lt1`/`lt2`/`cp`/`vo2max`/`max_hr`, `aggregate`/`aerobic`/`neuromuscular`/`structural`, `time_constants`, `theoretical_targets`/`adjusted_targets`, `target` — all use `sqlalchemy.dialects.postgresql.JSONB`.
- **Partial unique indexes**. TwinState `activity_id WHERE NOT NULL`, CoachingMessage `first_message` and `post_workout` — use `CREATE UNIQUE INDEX ... WHERE ...` syntax.
- **Migration order**. [TwinState → AthletePhysiology → AthleteFitness] first (no cross-FK deps among these), then [GenerationEvent → CoachingMessage → GeneratedWorkout → WorkoutStep] (CoachingMessage FK to TwinState, GeneratedWorkout FK to TwinState+PlannedSession, WorkoutStep FK to GeneratedWorkout).
- **FK fix is a separate migration**. Do not modify the already-committed `79dc97d4e433` migration. Update the SQLAlchemy model, then autogenerate a new migration. The original 1-2c migration cannot add this FK because it would create a circular dependency.
- **Enum alignment**. Copy enum values EXACTLY from architecture contracts and `00-foundations/terminology.md`. These are part of the public API contract — changing them later is a breaking change.
- **`workout_steps.description` non-empty CHECK**. SQLAlchemy doesn't autogenerate CHECK constraints for `description IS NOT NULL AND description != ''` — add manually in migration or use a server-side trigger. The model should use `nullable=False` to ensure the constraint is enforced at application level.
