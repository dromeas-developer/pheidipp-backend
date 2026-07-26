# Test Scenarios — Phase 1 Gap Analysis — Batch 2: Core Schema Invariants

## Source: docs/implementation/phase-1/gap-analysis-phase-1/overview.md
## Sub-Phases Covered: 1.2a (Profile, Preferences, Activity), 1.2b (Plan & Sessions), 1.2c (Twin, Fitness, Coaching, Workouts)

---

## Steps 1–3 — AthleteProfile / AthletePreferences / Activity Schema Invariants

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 1 | AthleteProfile unique athlete_id enforced | Insert two AthleteProfile rows with same `athlete_id` | `IntegrityError` (unique constraint `uq_athlete_profile_athlete_id` or equivalent) | database | db-session |
| 2 | AthletePreferences unique athlete_id enforced | Insert two AthletePreferences rows with same `athlete_id` | `IntegrityError` (unique constraint) | database | db-session |
| 3 | AthletePreferences years_structured_training negative rejected | Insert with `years_structured_training=-1` | `IntegrityError` (CHECK `ck_athlete_preferences_years_structured_training_non_negative`) | database | db-session |
| 4 | Activity has no avg_hr column | Inspect `Activity` model column set | Column set does not contain `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or any lap-data field | application-logic | none |
| 5 | Activity dedup on (athlete_id, external_id, source) | Insert two Activity rows with same `(athlete_id, external_id="ext123", source="manual_upload")` | `IntegrityError` (partial unique `uq_activities_athlete_external_source WHERE external_id IS NOT NULL`) | database | db-session |
| 6 | Activity dedup exempt for manual_entry (null external_id) | Insert two Activity rows with same `athlete_id`, `external_id=None`, `source="manual_entry"` | Both inserts succeed — partial unique index predicate `WHERE external_id IS NOT NULL` does not apply | database | db-session |

## Steps 4–6 — TrainingGoal / TrainingPlan / WeeklyPlan Schema Invariants

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 7 | Single active TrainingGoal per athlete | Insert two TrainingGoal rows with same `athlete_id`, both `status='active'` | `IntegrityError` (partial unique `ix_training_goals_athlete_active WHERE status='active'`) | database | db-session |
| 8 | Multiple inactive goals allowed | Insert two TrainingGoal rows with same `athlete_id`, both `status='completed'` | Both inserts succeed — partial unique only applies to `status='active'` | database | db-session |
| 9 | TrainingGoal fitness_level out of range rejected | Insert with `fitness_level=6` | `IntegrityError` (CHECK constraint on fitness_level range 1-5) | database | db-session |
| 10 | TrainingGoal weekly_volume_hours negative rejected | Insert with `weekly_volume_hours=-5.0` | `IntegrityError` (CHECK `weekly_volume_hours >= 0`) | database | db-session |
| 11 | TrainingGoal weekly_volume_km negative rejected | Insert with `weekly_volume_km=-10.0` | `IntegrityError` (CHECK `weekly_volume_km >= 0`) | database | db-session |
| 12 | WeeklyPlan unique (training_plan_id, week_number) | Insert two WeeklyPlan rows with same `(training_plan_id, week_number=1)` | `IntegrityError` (unique constraint) | database | db-session |
| 13 | Checkpoint planned_session_id one-to-one | Insert two Checkpoint rows with same `planned_session_id` | `IntegrityError` (unique FK constraint on `planned_session_id`) | database | db-session |

## Steps 7–10 — TwinState / AthleteFitness / AthletePhysiology Schema Invariants

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 14 | TwinState repository exposes no update/delete | Inspect `TwinStateRepository` method set | Methods are exactly: `get_latest`, `get_by_id`, `get_by_activity`, `get_by_activity_and_trigger`, `get_history`, `insert`. No `update`, `delete`, `save`, or `merge` method exists. | application-logic | none |
| 15 | TwinState append-only — direct UPDATE raises | Attempt `session.execute(update(TwinState).where(...))` | Operation succeeds at SQL level (no DB trigger blocks it), but no application code path calls it — the invariant is application-enforced by repository contract. Test asserts the repository API surface, not a DB trigger. | application-logic | db-session |
| 16 | AthleteFitness unique athlete_id | Insert two AthleteFitness rows with same `athlete_id` | `IntegrityError` (unique `uq_athlete_fitness_athlete`) | database | db-session |
| 17 | AthleteFitness form = fitness - fatigue (aggregate) — valid | Insert with `aggregate={"fitness": 100, "fatigue": 40, "form": 60}` | Insert succeeds (CHECK `ck_athlete_fitness_aggregate_form_invariant` passes: 60 = 100 - 40) | database | db-session |
| 18 | AthleteFitness form = fitness - fatigue (aggregate) — invalid | Insert with `aggregate={"fitness": 100, "fatigue": 40, "form": 50}` | `IntegrityError` (CHECK fails: 50 ≠ 100 - 40) | database | db-session |
| 19 | AthleteFitness form invariant on dimensional block (aerobic) | Insert with `aerobic={"fitness": 50, "fatigue": 20, "form": 30}` | Insert succeeds (CHECK passes: 30 = 50 - 20) | database | db-session |
| 20 | AthleteFitness form invariant on dimensional block — invalid | Insert with `aerobic={"fitness": 50, "fatigue": 20, "form": 25}` | `IntegrityError` (CHECK `ck_athlete_fitness_aerobic_form_invariant` fails) | database | db-session |
| 21 | AthleteFitness null dimensional block skips CHECK | Insert with `aerobic=None` | Insert succeeds — CHECK constraint has `(col IS NULL) OR (...)` predicate | database | db-session |
| 22 | AthleteFitness time_constants.source invalid value rejected | Insert with `time_constants={"source": "custom_value"}` | `IntegrityError` (CHECK `ck_athlete_fitness_time_constants_source_valid`: source must be in {population_default, individual_fitted}) | database | db-session |
| 23 | AthleteFitness time_constants.source population_default accepted | Insert with `time_constants={"source": "population_default", ...}` | Insert succeeds | database | db-session |
| 24 | AthleteFitness time_constants.source individual_fitted accepted | Insert with `time_constants={"source": "individual_fitted", ...}` | Insert succeeds | database | db-session |
| 25 | AthletePhysiology unique athlete_id | Insert two AthletePhysiology rows with same `athlete_id` | `IntegrityError` (unique constraint) | database | db-session |

## Steps 11–14 — CoachingMessage / GenerationEvent / GeneratedWorkout / WorkoutStep Schema Invariants

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 26 | CoachingMessage repository exposes no update/delete | Inspect `CoachingMessageRepository` method set | Methods are: `insert`, `get_by_athlete_id`, `get_by_athlete_and_type`, `get_existing_first_message`, `get_by_activity_and_type`, `get_all_count`. No `update`/`delete`. | application-logic | none |
| 27 | CoachingMessage first_message singleton per athlete | Insert two CoachingMessage rows with same `athlete_id`, both `message_type='first_message'` | `IntegrityError` (partial unique `uq_coaching_messages_athlete_first_message WHERE message_type='first_message'`) | database | db-session |
| 28 | CoachingMessage post_workout singleton per activity | Insert two CoachingMessage rows with same `activity_id`, both `message_type='post_workout'` | `IntegrityError` (partial unique `uq_coaching_messages_activity_post_workout WHERE message_type='post_workout' AND activity_id IS NOT NULL`) | database | db-session |
| 29 | CoachingMessage post_workout with null activity_id exempt | Insert two CoachingMessage rows with `activity_id=None`, `message_type='post_workout'` | Both succeed — partial unique predicate requires `activity_id IS NOT NULL` | database | db-session |
| 30 | CoachingMessage content empty rejected | Insert with `content=""` | `IntegrityError` (CHECK `ck_coaching_messages_content_non_empty: length(content) > 0`) | database | db-session |
| 31 | GeneratedWorkout unique (planned_session_id, generation_date) | Insert two GeneratedWorkout rows with same `(planned_session_id, generation_date)` | `IntegrityError` (unique `uq_generated_workouts_planned_session_generation_date`) | database | db-session |
| 32 | GeneratedWorkout theoretical_targets must be JSONB object | Insert with `theoretical_targets="not-an-object"` (or null) | `IntegrityError` (CHECK `jsonb_typeof(theoretical_targets) = 'object'`) | database | db-session |
| 33 | GeneratedWorkout adjusted_targets must be JSONB object | Insert with `adjusted_targets=null` | `IntegrityError` (CHECK `jsonb_typeof(adjusted_targets) = 'object'`) | database | db-session |
| 34 | GeneratedWorkout recovery_modifier_level invalid rejected | Insert with `recovery_modifier_level="purple"` | `IntegrityError` (CHECK `recovery_modifier_level IN ('green', 'amber', 'red')`) | database | db-session |
| 35 | WorkoutStep unique (generated_workout_id, step_order) | Insert two WorkoutStep rows with same `(generated_workout_id, step_order=1)` | `IntegrityError` (unique `uq_workout_steps_generated_workout_step_order`) | database | db-session |
| 36 | WorkoutStep physiological_intent NOT NULL | Insert with `physiological_intent=None` | `IntegrityError` (NOT NULL constraint) | database | db-session |
| 37 | WorkoutStep step_order < 1 rejected | Insert with `step_order=0` | `IntegrityError` (CHECK `ck_workout_steps_step_order_positive: step_order >= 1`) | database | db-session |
| 38 | WorkoutStep description empty rejected | Insert with `description=""` | `IntegrityError` (CHECK `ck_workout_steps_description_non_empty: length(description) > 0`) | database | db-session |
| 39 | WorkoutStep duration_seconds negative rejected | Insert with `duration_seconds=-10` | `IntegrityError` (CHECK `ck_workout_steps_duration_non_negative: duration_seconds IS NULL OR duration_seconds >= 0`) | database | db-session |
| 40 | WorkoutStep duration_seconds null accepted | Insert with `duration_seconds=None` | Insert succeeds (CHECK allows NULL) | database | db-session |

## Step 15 — SystemEvent / Outbox Schema Invariants

| # | Scenario | Input | Expected | Enforcement | Mock Boundary |
|---|---|---|---|---|---|
| 41 | SystemEvent athlete_id NOT NULL | Insert SystemEvent with `athlete_id=None` | `IntegrityError` (NOT NULL constraint) | database | db-session |
| 42 | SystemEvent append-only — no update path | Inspect `SystemEventRepository` method set | No `update`/`delete` method; only `insert` and read methods | application-logic | none |