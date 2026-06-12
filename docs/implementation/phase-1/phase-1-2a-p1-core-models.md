# Implementation Plan: Phase-1.2a — Core Models: Profile, Preferences, Activity
## Plan ID: Phase-1.2a-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.2a
Sub-Phase Title: Phase 1 — Core Models: Profile, Preferences, Activity

## Objective
Implement the schema-only foundation for the athlete-context tables used by onboarding and downstream coaching systems: extend the existing `athlete_profiles` table to the full `AthleteProfile` schema, create the `AthletePreferences` table, and create the lean `Activity` observation table. This plan does not write data, expose APIs, compute load, or implement ingestion services; it prepares the database contracts that Phase-1.3, Phase-1.4, and Phase-1.6 will consume.

## Scope
- Extend the existing `athlete_profiles` table from the Phase-1.1 minimal demographics schema to the full `AthleteProfile` schema.
- Create the `athlete_preferences` table with one-to-one linkage to `Athlete`.
- Create the `activities` table as a lean observation index.
- Define required database enums and check constraints for `AthleteProfile`, `AthletePreferences`, and `Activity`.
- Define required unique constraints and indexes, including the `Activity` external deduplication rule.
- Preserve the Phase-1.1 `athlete_profiles` table by extending it only; do not drop and recreate it.
- Keep the plan schema-only: no data seeding, no service logic, no endpoint implementation, no FIT parsing, no load computation, and no calibration logic.

## Out Of Scope
- Implementing onboarding, profile, preferences, or activity endpoints.
- Creating or writing `AthleteIntegration`, `RawSensorStream`, `PhysiologicalSegment`, `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, or `PlannedSession`.
- Implementing object storage, FIT parsing, load computation, calibration eligibility, twin recalibration, or post-workout analysis.
- Adding averaged workout fields to `Activity`.
- Adding raw data surfaces, workout charts, lap dumps, or dashboard-style summaries.
- Changing release sequencing or merging this schema work into Phase-1.2b.

## Architecture Contracts
- `01-entities/athlete-profile.md` — IMPLEMENTS the full `AthleteProfile` schema and preserves the existing one-to-one profile relationship.
- `01-entities/athlete-preferences.md` — IMPLEMENTS the `AthletePreferences` schema and data-tier-related preference fields.
- `01-entities/activity.md` — IMPLEMENTS the lean `Activity` observation index schema.
- `00-foundations/terminology.md` — DEPENDS ON shared enum values and domain terminology.
- `00-foundations/data-tiers.md` — DEPENDS ON data tier capability model and preference-based tier inference fields.
- `docs/vision/twin/cold-start.md` — DEPENDS ON honest low-confidence onboarding tier philosophy.
- `docs/vision/product/constraints.md` — DEPENDS ON running-only twin model and no raw data surfaces.

## Invariants
- One `AthleteProfile` per `Athlete`. Created at registration. Enforced by unique constraint on `(athlete_id)`.
- One `AthletePreferences` per `Athlete`. Created during onboarding. Enforced by unique constraint on `(athlete_id)`.
- `years_structured_training >= 0`. CHECK constraint at DB level.
- `timezone` is required at onboarding (validated against IANA tz database). Immutable after creation — changing timezone requires a support process. All scheduled tasks (MissedSessionSweepTask, WorkoutPrefetchTask) and date interpretations use this timezone.
- `training_window` defaults to 06:00–20:00 if not set. Mutable via PATCH. Only used by WorkoutPrefetchTask for prefetch timing. MissedSessionSweepTask uses timezone only, not training_window.
- `structural_risk_flag` is computed at onboarding from `AthletePreferences.sport_background`. When `true`, the structural load density penalty coefficient is 0.08 (vs 0.12 population default). See `02-computations/load-computation.md`.
- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.
- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields do not exist on `Activity`. They are never added.
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.
- Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.
- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.
- Tier 5 and 6 activities are never `calibration_eligible`.
- Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`.

## Implementation Steps
1. Confirm the Phase-1.1 baseline: `Athlete` exists and `athlete_profiles` already contains the minimal registration columns `date_of_birth`, `sex`, and `height_cm`. Do not drop, rename, or recreate `athlete_profiles`.
2. Define or update shared database enums from the architecture contracts: `Sex`, `SportBackground`, `TrainingTimeOfDay`, `GpsSource`, `HrSource`, `PowerSource`, `PrimaryTrainingPlatform`, and `ActivitySource`.
3. Extend `athlete_profiles` with the full schema fields: `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`, `location_lat`, `location_lng`, `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`.
4. Add safe defaults and nullability for the profile extension so existing Phase-1.1 rows remain valid: `current_effort_generation` defaults to `1`, `structural_risk_flag` defaults to `false`, and fields not known at registration remain nullable until Phase-1.3 onboarding validation supplies them.
5. Enforce `AthleteProfile` one-to-one ownership by ensuring a unique constraint or unique index exists on `(athlete_id)`.
6. Create `athlete_preferences` with `athlete_id` as the one-to-one FK to `Athlete`, and enforce a unique constraint on `(athlete_id)`.
7. Add `athlete_preferences` fields for `sport_background`, `years_structured_training`, `training_time_of_day`, `weekly_schedule`, `gps_source`, `hr_source`, `power_source`, `primary_training_platform`, and `updated_at`.
8. Add the `years_structured_training >= 0` CHECK constraint at DB level.
9. Create `activities` with the lean observation fields: `id`, `athlete_id`, `planned_session_id`, `source`, `external_id`, `activity_date`, `start_time`, `duration_seconds`, `aerobic_load`, `neuromuscular_load`, `structural_load`, `has_hr`, `has_rr_intervals`, `has_power`, `calibration_eligible`, `quality_flags`, `fit_file_key`, `ingestion_pipeline_version`, `cleaning_pipeline_version`, `notes`, and `created_at`.
10. Do not add `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or `lap_data` columns to `activities`.
11. Add `Activity` check constraints for source semantics: `manual_entry` must have `calibration_eligible = false`, null load scores, and null `fit_file_key`; non-manual sources must have a non-null `fit_file_key`.
12. Add the partial unique index for Activity deduplication: `(athlete_id, external_id, source)` where `external_id IS NOT NULL`.
13. Add useful query indexes for downstream phases: `athlete_id`, `activity_date`, `planned_session_id`, `created_at`, and the deduplication partial index.
14. For `activities.planned_session_id`, create the nullable column in this sub-phase but do not create the FK constraint until Phase-1.2b, because `planned_sessions` is created later and the schema currently has a circular linkage direction.
15. Run the migration suite on a fresh database and verify that no Phase-1.2a data is seeded or written.

## Event Contracts
| Event | PRODUCES or CONSUMES | Payload fields required by this plan | Ordering assumptions |
|---|---|---|---|
| None | None | None | This sub-phase is schema-only. Do not emit, consume, or alter event contracts. |

Future `Activity` events (`activity_ingested`, `activity_calibration_eligible`) are not implemented by this plan. Future `PlannedSession` event handling is not implemented by this plan.

## Pseudocode
```text
run_phase_1_2a_schema_migration
  verify athlete_profiles baseline exists
  extend athlete_profiles
    add personalisation JSONB fields
    add location/timezone/training_window fields
    add current_effort_generation default 1
    add structural_risk_flag default false
    add objective_thresholds JSONB
    ensure unique athlete_id constraint

  create athlete_preferences
    add athlete_id FK to athletes
    add preference fields
    ensure unique athlete_id constraint
    add years_structured_training >= 0 check

  create activities
    add athlete_id FK to athletes
    add nullable planned_session_id column only
    add source enum and activity fields
    ensure no avg or lap columns exist
    add manual_entry semantic check
    add non-manual fit_file_key check
    add partial unique index on (athlete_id, external_id, source) where external_id is not null
    add downstream query indexes

  verify migration on fresh database
```

## Testing Requirements
- Fresh database migration succeeds with no errors and no destructive recreation of `athlete_profiles`.
- `athlete_profiles` contains the full Phase-1.2a schema fields and still enforces one record per `athlete_id`.
- Existing Phase-1.1-style `athlete_profiles` rows remain valid after the extension migration.
- `athlete_preferences` enforces one record per `athlete_id`.
- Inserting `athlete_preferences.years_structured_training < 0` fails at the DB constraint layer.
- `activities` has no `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or `lap_data` columns.
- Inserting an `activities` row with `source = 'manual_entry'`, `calibration_eligible = false`, null load scores, and null `fit_file_key` succeeds.
- Inserting an `activities` row with `source != 'manual_entry'` and null `fit_file_key` fails at the DB constraint layer.
- Inserting duplicate `activities` rows with the same non-null `(athlete_id, external_id, source)` fails.
- The `activities.planned_session_id` column exists as nullable, but its FK constraint is not required in Phase-1.2a because `planned_sessions` is created in Phase-1.2b.
- No data is inserted into `athlete_profiles`, `athlete_preferences`, or `activities` by the Phase-1.2a migration.

## Coder Handoff Notes
- This is a schema-only plan. If a step requires service logic, endpoint logic, or data writes, it belongs to a later sub-phase.
- The most important preservation rule is: do not drop and recreate `athlete_profiles`; extend the existing Phase-1.1 table.
- Do not add raw or averaged workout fields to `Activity`. The table is a lean observation index, not a workout dashboard.
- `fit_file_key` is a hard prerequisite for non-manual activities. Preserve the non-manual `fit_file_key IS NOT NULL` constraint even though FIT ingestion is implemented later.
- `manual_entry` is a valid non-error state: `calibration_eligible = false`, null load scores, and null `fit_file_key`.
- Because `planned_sessions` is created in Phase-1.2b, do not try to force an FK from `activities.planned_session_id` in Phase-1.2a. That FK must be added after `planned_sessions` exists.
- Copy enum values exactly from the architecture contracts; downstream phases depend on these values being stable.
- The migration must leave the database ready for Phase-1.3 onboarding, but it must not perform onboarding or create default preference records.
