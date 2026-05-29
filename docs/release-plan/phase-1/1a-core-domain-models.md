# 1a — Core Domain Models
*Build the complete DB schema right first time*

## Objective

Establish every core domain model the system will ever need, with correct fields,
constraints, and relationships from the start. This is the single most important
sub-phase — a schema built correctly here avoids costly migrations in every
subsequent phase. Models that are not yet used are still defined in full, so later
phases wire services against a stable schema.

## Scope

All models in the planning, coaching, and twin layers created in full:
`Athlete`, `AthleteProfile`, `AthletePreferences`, `TrainingBlock`,
`TrainingPlan`, `PlannedSession`, `TwinState`, `CoachingMessage`,
`GenerationEvent`, `GeneratedWorkout`, `Activity`, `PostWorkoutAnalysis`.

All enums required by these models.

One Alembic migration covering all tables.

## Non-Goals

- No services or endpoints — models only
- `WorkoutStep` model is deferred to sub-phase 2c (requires `PhysiologicalIntentState`)
- `AthleteIntegration` deferred to sub-phase 2a (FIT ingestion)
- `ExecutionObservation` deferred to sub-phase 4a (real FIT analysis)
- All wellness, segmentation, coaching-services, and adaptation models deferred
  to their respective phases
- No data is written to any of these tables in this sub-phase

## Architecture References

- Full field specifications for all models: `architecture/data-models.md`
- Full field specs for planning models: `architecture/planning-and-sessions.md`
- `TwinState` append-only invariant and field list: `architecture/twin-state.md`
- `GenerationEvent` field list: `architecture/llm-and-agents.md`
- Core principle (no global averages on Activity): `architecture/principles.md`

## Dependencies

None. This is the first sub-phase.

## Models Introduced

**`Athlete`** — root entity. Fields: `id`, `email`, `hashed_password`,
`onboarding_complete` (bool, default false), `created_at`.
Unique index on `email`.

**`AthleteProfile`** — stable demographics, one-to-one with Athlete.
Fields: `athlete_id` FK, `date_of_birth`, `sex` (enum: `male`, `female`,
`not_specified`), `height_cm`, `weight_kg`, `updated_at`.

**`AthletePreferences`** — mutable training configuration, one-to-one with Athlete.
Full field set from `architecture/planning-and-sessions.md` including:
`sport_background`, `years_structured_training`, `training_time_of_day`,
`weekly_schedule` (JSONB), `gps_source`, `hr_source`, `power_source`,
`primary_training_platform`. No DELETE endpoint. PATCH only.

**`TrainingBlock`** — goal context, one-to-many per athlete, append-only.
Full field set from `architecture/planning-and-sessions.md` including:
`goal_type`, `goal_event_type`, `goal_event_date`, `custom_distance_km`,
`weekly_volume_hours`, `weekly_volume_km`, `fitness_level` (1-5 CHECK),
`recent_injury`, `injury_severity`, `status` (enum: `active`, `completed`, `abandoned`),
`created_at`, `closed_at`.
`goal_type` values: `race_event`, `fitness_improvement`, `maintenance`, `recovery`.
`goal_event_type` null when goal_type ≠ `race_event`.
`injury_severity` required when goal_type = `recovery` (enum: `InjurySeverity`: `minor`, `moderate`, `major`).
DB-level constraint: cannot have two `active` blocks per athlete (partial unique
index on `athlete_id WHERE status = 'active'`).

**`TrainingPlan`** — generated periodised plan, one-to-one with TrainingBlock.
Fields: `training_block_id` FK, `twin_state_id` FK (nullable — set when generated),
`phases` (JSONB — ordered phase descriptor array), `status` (enum: `active`,
`superseded`, `completed`), `superseded_at`, `created_at`.

**`PlannedSession`** — one record per intended session in the plan.
Full field set from `architecture/planning-and-sessions.md` including:
`training_plan_id` FK, `target_date`, `week_number`, `phase_label`, `session_type`,
`intent_description`, `approximate_duration_minutes`,
`status` (enum: `pending`, `generated`, `completed`, `skipped`, `missed`,
`redistributed`), `skip_reason`, `redistributed_to_date`,
`activity_id` FK (nullable, set when completed).

**`TwinState`** — append-only twin model snapshot.
Full field set from `architecture/twin-state.md` and `architecture/data-models.md`:
`athlete_id` FK, `training_block_id` FK, `fitness_score`, `fatigue_score`,
`lt1_estimate_bpm`, `lt2_estimate_bpm`, `max_hr_estimate_bpm`,
`ftp_estimate_watts` (nullable), `vo2max_estimate` (nullable),
`data_tier` (int 1-6), `confidence_level` (enum: `low`, `medium`, `high`),
`trigger` (enum: `questionnaire`, `activity_sync`, `calibration`, `wellness_update`),
`model_version`, `created_at`.
No UPDATE or DELETE — insert only. No unique constraint on athlete_id.

**`CoachingMessage`** — LLM-generated message to athlete.
Fields: `id`, `athlete_id` FK, `twin_state_id` FK, `activity_id` FK (nullable),
`message_type` (enum: `first_message`, `post_workout`, `weekly_summary`,
`plan_transition`, `wellness_alert`), `content` (Text),
`prompt_version`, `generated_at`.

**`GenerationEvent`** — log of every LLM call, success or failure.
Full field set from `architecture/llm-and-agents.md`:
`agent_name`, `prompt_version`, `input_token_count`, `output_token_count`,
`latency_ms`, `success` (bool), `failure_reason` (nullable),
`athlete_id` FK, `trigger_context`, `created_at`.
This is a proper DB table from day one — not a log that becomes a table later.

**`GeneratedWorkout`** — on-the-day workout for a PlannedSession.
Fields from `architecture/data-models.md` Workout Layer:
`planned_session_id` FK, `twin_state_id` FK,
`workout_structure` (JSONB — used in Phase 1; replaced by `WorkoutStep` FK in 2c),
`theoretical_targets` (JSONB), `adjusted_targets` (JSONB),
`recovery_modifier_level` (enum: `green`, `amber`, `red`, default `green`),
`recovery_modifier_reason` (nullable Text), `generated_at`.
Note: `theoretical_targets` and `adjusted_targets` are both present from Phase 1
even though they are identical until wellness and weather are added in Phase 3.
The two-column structure is correct from the start.

**`Activity`** — lean physiological observation index. No global averages.
Full field set from `architecture/data-models.md` Ingestion Layer:
`athlete_id` FK, `planned_session_id` FK (nullable),
`source` (enum: `intervals_icu`, `manual_upload`, `garmin_direct`, `manual_entry`),
`external_id` (nullable, for deduplication),
`activity_date`, `start_time`, `duration_seconds`,
`aerobic_load` (nullable float), `neuromuscular_load` (nullable float),
`structural_load` (nullable float),
`has_hr` (bool, default false), `has_rr_intervals` (bool, default false),
`has_power` (bool, default false),
`calibration_eligible` (bool, default false),
`quality_flags` (JSONB, default empty),
`notes` (nullable Text),
`fit_file_key` (nullable — null for manual entries; required for all FIT uploads),
`ingestion_pipeline_version` (nullable),
`cleaning_pipeline_version` (nullable),
`created_at`.
Constraint: `fit_file_key` NOT NULL enforced at application layer for source
≠ `manual_entry`. DB constraint deferred to sub-phase 2a when FIT ingestion is live.

**`PostWorkoutAnalysis`** — coaching analysis linked to an activity.
Fields: `id`, `activity_id` FK (unique — one analysis per activity),
`coaching_message_id` FK, `compliance_summary` (JSONB),
`execution_findings` (JSONB), `created_at`.

## Enums Introduced

All in `app/models/enums.py`:
`Sex`, `SportBackground`, `TrainingTimeOfDay`, `GpsSource`, `HrSource`,
`PowerSource`, `PrimaryTrainingPlatform`, `GoalType`, `GoalEventType`,
`InjurySeverity`, `TrainingBlockStatus`, `PhaseLabel`, `SessionType`, `PlannedSessionStatus`,
`TwinConfidenceLevel`, `TwinTrigger`, `MessageType`, `ActivitySource`,
`RecoveryModifierLevel`, `TrainingPlanStatus`.

## Services & Tasks Introduced

None in this sub-phase — models only.

## Endpoints Introduced

None in this sub-phase — models only.

## Key Constraints

- `TwinState` has no UPDATE or DELETE operations. The ORM model must not expose them.
- `Activity` stores no `avg_hr`, `avg_pace`, `avg_power`, or lap data. If these
  fields exist on the current model they must be removed.
- `TrainingBlock` enforces single active block per athlete via a partial unique index,
  not application logic alone.
- `TrainingPlan` old records receive `superseded_at` when replaced — never deleted.
- `GenerationEvent` is a real DB table, not an in-memory log or a file log.

## Done Criteria

- All migrations run cleanly on a fresh database with no errors.
- `TwinState` has no ORM-level `update()` or `delete()` methods.
- `Activity` has no `avg_hr`, `avg_pace`, `avg_power` columns.
- Attempting to create a second active `TrainingBlock` for an athlete raises a
  database-level unique constraint violation.
