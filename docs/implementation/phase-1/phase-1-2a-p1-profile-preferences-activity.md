# Implementation Plan: Phase-1.2a — Profile, Preferences, and Activity Schema
## Plan ID: Phase-1.2a-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.2a
Sub-Phase Title: Phase 1 — Core Models: Profile, Preferences, Activity

## Objective
Implement the Phase-1.2a schema-only foundation for athlete context: extend the existing Phase-1.1 `AthleteProfile` table to the full profile contract, add the new `AthletePreferences` and `Activity` persistence models, define the required enums/constraints/indexes, and verify the migration path from the current Phase-1.1 database revision. This plan does not implement onboarding writes, activity ingestion, load computation, APIs, or downstream plan/session services.

## Scope
- Extend the existing `athlete_profiles` table/model without dropping or recreating it.
- Add the `athlete_preferences` table/model with one-to-one athlete ownership and preference fields required for schedule, hardware, platform, and data-tier inference.
- Add the `activities` table/model as a lean physiological observation index.
- Define and register the enums needed by these schemas, including `ActivitySource`, `DataTier`, and existing `Sex` compatibility.
- Add the Alembic migration that extends `athlete_profiles`, creates `athlete_preferences`, creates `activities`, and adds required constraints and indexes.
- Add schema-level tests that prove the Phase-1.2a exit gate and preserve Phase-1.1 auth/profile behaviour.

## Out Of Scope
- Writing onboarding data into `AthleteProfile` or `AthletePreferences`.
- Creating profile, preferences, or activity API endpoints.
- Implementing FIT upload, object storage, manual activity entry, load computation, or calibration eligibility services.
- Implementing `PlannedSession`, `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, or `Checkpoint` schemas.
- Implementing `RawSensorStream`, `PhysiologicalSegment`, `AthleteIntegration`, or any platform sync model.
- Changing authentication, token issuance, refresh-token rotation, or `require_self` behaviour.
- Producing or consuming domain events in this plan.

## Architecture Contracts
- `01-entities/athlete-profile.md` — IMPLEMENTS the full `AthleteProfile` schema while preserving the existing Phase-1.1 minimal registration profile.
- `01-entities/athlete-preferences.md` — IMPLEMENTS the `AthletePreferences` schema, weekly schedule JSONB, hardware/platform fields, and data-tier input fields.
- `01-entities/activity.md` — IMPLEMENTS the lean `Activity` schema, including signal flags, load-score nullable fields, calibration eligibility flag, quality flags, version fields, and `fit_file_key`.
- `00-foundations/terminology.md` — DEPENDS ON exact enum values for `Sex`, `ActivitySource`, `DataTier`, and related closed ontologies where referenced by these schemas.
- `00-foundations/data-tiers.md` — DEPENDS ON the hardware capability tiers and inference rules used by `AthletePreferences`.
- `docs/vision/twin/cold-start.md` — DEPENDS ON honest onboarding tier philosophy: profile/preferences must support conservative cold-start behaviour without pretending unavailable data exists.
- `docs/vision/product/constraints.md` — DEPENDS ON running-only twin modelling and no raw-data surfaces; `Activity` must remain a lean running observation index, not a workout dashboard record.
- `docs/implementation/implemented-state.md` — DEPENDS ON the Phase-1.1 state where `Athlete`, minimal `AthleteProfile`, auth models, migrations, and registrations already exist.

## Invariants
- `AthleteProfile`: one per `Athlete`. Unique constraint on `athlete_id`.
- `AthletePreferences`: one per `Athlete`. Unique constraint on `athlete_id`.
- `Activity` has no `avg_hr`, `avg_pace`, `avg_power`, or lap data fields.
- `Activity.source = 'manual_entry'` always has `calibration_eligible = false`, null load scores, null `fit_file_key`.
- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.
- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.
- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields do not exist on `Activity`. They are never added.
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.
- `timezone` is required at onboarding (validated against IANA tz database). Immutable after creation — changing timezone requires a support process. All scheduled tasks (`MissedSessionSweepTask`, `WorkoutPrefetchTask`) and date interpretations use this timezone.
- `years_structured_training >= 0`. CHECK constraint at DB level.
- `hr_source` is the primary input for data tier inference. See `00-foundations/data-tiers.md`.
- Changes to `hr_source` or `power_source` affect the data tier of the next ingested Activity but do not retroactively alter historical Activities.
- `weekly_schedule` is stored as structured JSONB. Each day's `available` and `max_hours` directly constrain `PlanGenerationService` session distribution. `long_workout` marks the day for long run placement. `doubles_eligible` marks the day as eligible for AM primary + PM secondary sessions.

## Implementation Steps
1. Extend the existing `AthleteProfile` persistence model from the Phase-1.1 minimal schema to the full architecture schema:
   - Preserve `id`, `athlete_id`, `date_of_birth`, `sex`, `height_cm`, and `updated_at`.
   - Add personalisation model JSONB fields: `gap_curve_model`, `weather_response_model`, `banister_constants`, and `cycle_personal_model`.
   - Add location and scheduling fields: `location_lat`, `location_lng`, `timezone`, and `training_window`.
   - Add effort-generation and risk fields: `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`.
   - Preserve the one-to-one `athlete_id` uniqueness already introduced in Phase-1.1.

2. Add the `AthletePreferences` persistence model:
   - One-to-one `athlete_id` with DB uniqueness.
   - Sport/training background fields: `sport_background` and `years_structured_training`.
   - Time/schedule fields: `training_time_of_day` and `weekly_schedule` JSONB.
   - Hardware/platform fields: `gps_source`, `hr_source`, `power_source`, and `primary_training_platform`.
   - `updated_at` timestamp.
   - DB-level non-negative constraint for `years_structured_training`.

3. Add the `Activity` persistence model as a lean observation index:
   - Identity and ownership fields: `id`, `athlete_id`, and nullable `planned_session_id`.
   - Source and deduplication fields: `source`, `external_id`, and `activity_date`.
   - Timing and duration fields: `start_time` and `duration_seconds`.
   - Load-score fields: nullable `aerobic_load`, `neuromuscular_load`, and `structural_load`.
   - Signal availability fields: `has_hr`, `has_rr_intervals`, and `has_power`.
   - Calibration and quality fields: `calibration_eligible` and `quality_flags` JSONB.
   - Reprocessing and version fields: nullable `fit_file_key`, `ingestion_pipeline_version`, and `cleaning_pipeline_version`.
   - Notes and `created_at`.
   - Do not add `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns.

4. Define/register schema enums:
   - Keep `Sex` compatible with existing Phase-1.1 values: `male`, `female`, `not_specified`.
   - Add `ActivitySource` with exactly `intervals_icu`, `manual_upload`, `garmin_direct`, and `manual_entry`.
   - Add `DataTier` with values `1` through `6`.
   - Do not add multi-sport activity sources or raw-data dashboard fields.

5. Create the Phase-1.2a Alembic migration from the current Phase-1.1 head:
   - Extend `athlete_profiles` with `ALTER TABLE ADD COLUMN` operations; never drop and recreate the table.
   - Create `athlete_preferences` with the one-to-one athlete constraint and `years_structured_training` check.
   - Create `activities` with the lean observation schema, deduplication index, athlete/date indexes, and enum support.
   - Add the partial unique deduplication constraint for `(athlete_id, external_id, source)` where `external_id` is non-null.
   - Include `planned_session_id` as a nullable UUID column, but do not create a placeholder `planned_sessions` table in this plan. The DB foreign key to `planned_sessions` must be added in Phase-1.2b once that table exists.

6. Register new models and enums through the existing model package so migration discovery includes the new tables without changing auth registrations.

7. Add schema and migration tests that directly inspect the database objects and model metadata:
   - Fresh migration upgrade succeeds from an empty database.
   - Existing Phase-1.1 registration profile creation still succeeds.
   - `athlete_profiles` has the full Phase-1.2a column set and retains the unique `athlete_id` constraint.
   - `athlete_preferences` has unique `athlete_id` and non-negative `years_structured_training`.
   - `activities` has the required lean fields and no raw-summary fields.
   - Duplicate `(athlete_id, external_id, source)` inserts are rejected when `external_id` is non-null.

## Event Contracts
No events are produced or consumed by this schema-only plan.

- `activity_ingested` — NOT PRODUCED. Activity record creation and event production remain out of scope until FIT/manual ingestion is implemented.
- `activity_calibration_eligible` — NOT PRODUCED. Calibration eligibility computation remains out of scope until load computation and calibration services exist.
- `session_completed` — NOT CONSUMED. Linking activities to planned sessions remains out of scope until plan/session services exist.
- `onboarding_completed` — NOT CONSUMED. Onboarding orchestration remains out of scope.

## Pseudocode
```text
Phase-1.2a migration
  start from Phase-1.1 head
  verify athlete_profiles already exists

  alter athlete_profiles
    add personalisation JSONB fields
    add location fields
    add timezone
    add training_window JSONB
    add effort-generation, structural-risk, and objective-threshold fields

  create athlete_preferences
    define one-to-one athlete_id uniqueness
    define years_structured_training >= 0
    define weekly_schedule JSONB

  create activities
    define lean running observation fields
    define partial unique index on (athlete_id, external_id, source) where external_id is not null
    define athlete/date indexes
    leave planned_session_id as nullable UUID until planned_sessions exists in Phase-1.2b

  register models and enums
```

## Testing Requirements
- Running `alembic upgrade head` on a fresh database succeeds with no migration errors.
- Running the Phase-1.1 registration journey still creates exactly one `Athlete`, one email-provider `AthleteAuth`, one minimal `AthleteProfile`, and one refresh-token record.
- Schema inspection confirms `athlete_profiles` contains the full Phase-1.2a profile fields: `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`, `location_lat`, `location_lng`, `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`.
- Schema inspection confirms `athlete_profiles.athlete_id` remains unique.
- Schema inspection confirms `athlete_preferences.athlete_id` is unique and `years_structured_training >= 0` is enforced.
- Schema inspection confirms `activities` contains the lean observation fields and does not contain `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns.
- Inserting two activities with the same non-null `(athlete_id, external_id, source)` raises a database uniqueness violation.
- Enum values for `ActivitySource` are exactly `intervals_icu`, `manual_upload`, `garmin_direct`, and `manual_entry`.
- Enum values for `DataTier` are exactly `1`, `2`, `3`, `4`, `5`, and `6`.
- Data-tier inference maps `running_power_meter + chest_strap_rr` to Tier 1, `running_power_meter + non-RR HR` to Tier 2, `chest_strap_rr` to Tier 3, `chest_strap_no_rr` or `wrist_optical` to Tier 4, `hr_source = none` to Tier 5, and fallback to Tier 6.
- Existing auth API and repository tests continue to pass without schema regressions.

## Coder Handoff Notes
- No implementation ADR is required; this plan follows the architecture schema contracts directly.
- This is schema-only. Do not implement onboarding writes, profile/preferences APIs, activity upload/manual-entry APIs, FIT object storage, load computation, calibration eligibility, or event publication.
- Do not drop and recreate `athlete_profiles`; Phase-1.1 already created it. Extend it with additive migration operations only.
- Preserve Phase-1.1 compatibility: existing registration creates a minimal profile, so onboarding-time required fields such as `timezone` should not break the existing auth registration path.
- `Activity.planned_session_id` is part of the Activity schema, but `planned_sessions` is created in Phase-1.2b. Do not create a placeholder planned-sessions table here; add the foreign key in Phase-1.2b once the referenced table exists.
- `Activity` must remain lean. Do not add workout-summary or dashboard fields such as average heart rate, average pace, average power, cadence, or lap data.
- `fit_file_key` is the reprocessing anchor. This plan only defines the column; the invariant that non-manual activities require the raw FIT file to be stored before Activity creation belongs to the later ingestion implementation.
- Keep ownership singular: `AthleteProfile` owns stable demographics and fitted personalisation models; `AthletePreferences` owns hardware, platform, and schedule preferences; `Activity` owns the lean observation index.
