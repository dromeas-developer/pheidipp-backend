> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-2a, verified against the current codebase on 2026-07-19.

## Batch Objective

Implement the Phase 1-2a schema-only foundation for athlete context: extend the existing Phase 1-1 `AthleteProfile` table to the full profile contract, add the new `AthletePreferences` and `Activity` persistence models, define the required enums/constraints/indexes, and verify the migration path from the current Phase 1-1 database revision. This plan does not implement onboarding writes, activity ingestion, load computation, APIs, or downstream plan/session services.

## Preconditions

- Athlete and minimal AthleteProfile exist (from phase-1-1 auth/registration)
- Auth models support the existing registration path
- Alembic is at the Phase 1-1 head revision
- `planned_sessions` table does NOT yet exist — `Activity.planned_session_id` FK is deferred to phase-1-2b

## Scope

- Extend `athlete_profiles` table with full architecture schema (additive ALTER TABLE only — no drop and recreate)
- Add `athlete_preferences` table with one-to-one athlete ownership
- Add `activities` table as a lean physiological observation index
- Define enums: `ActivitySource` (4 values), `DataTier` (1-6), ensure `Sex` compatibility
- Alembic migration with constraints and indexes
- Register models and enums in `app/models/__init__.py`

## Out Of Scope

- Writing onboarding data into `AthleteProfile` or `AthletePreferences`
- Creating profile, preferences, or activity API endpoints
- Implementing FIT upload, object storage, manual activity entry, load computation, calibration eligibility
- `PlannedSession`, `TrainingGoal`, `TrainingPlan`, `WeeklyPlan`, `WeeklySession`, `Checkpoint` schemas
- Changing auth, token, or `require_self` behaviour
- Producing or consuming domain events

## Steps

1. [OWNER: Coder] Extend the existing `AthleteProfile` model from Phase 1-1 to the full schema. Use additive operations — never drop and recreate the table. Preserve `id`, `athlete_id`, `date_of_birth`, `sex`, `height_cm`, `updated_at`. Add: `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model` (JSONB personalisation models), `location_lat`, `location_lng`, `timezone`, `training_window` (location/scheduling), `current_effort_generation`, `structural_risk_flag`, `objective_thresholds`. Preserve unique `athlete_id` constraint.

2. [OWNER: Coder] Add `AthletePreferences` model: `athlete_id` (unique, one-to-one), `sport_background`, `years_structured_training` (CHECK ≥ 0), `training_time_of_day`, `weekly_schedule` (JSONB), `gps_source`, `hr_source`, `power_source`, `primary_training_platform`, `updated_at`.

3. [OWNER: Coder] Add `Activity` model as a lean observation index: `athlete_id` (FK CASCADE), `planned_session_id` (nullable UUID — FK deferred to phase-1-2b), `source` (ActivitySource enum), `external_id` (nullable), `activity_date`, `start_time`, `duration_seconds`, `aerobic_load` (nullable), `neuromuscular_load` (nullable), `structural_load` (nullable), `has_hr` (default false), `has_rr_intervals` (default false), `has_power` (default false), `calibration_eligible` (default false), `quality_flags` (JSONB default {}), `fit_file_key` (nullable), `ingestion_pipeline_version` (nullable), `cleaning_pipeline_version` (nullable), `notes`, `created_at`. Do NOT add `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns.

4. [OWNER: Coder] Define/register enums: ensure `Sex` compatibility with `male`, `female`, `not_specified`. Add `ActivitySource` with `intervals_icu`, `manual_upload`, `garmin_direct`, `manual_entry`. Add `DataTier` with 1-6. No multi-sport activity sources or raw-data dashboard fields.

5. [OWNER: Coder] Create Alembic migration from Phase 1-1 head: ALTER TABLE `athlete_profiles` (additive columns only), CREATE TABLE `athlete_preferences` (unique `athlete_id`, CHECK constraint), CREATE TABLE `activities` (partial unique index on `(athlete_id, external_id, source) WHERE external_id IS NOT NULL`, athlete/date indexes). Leave `planned_session_id` FK deferred — add in phase-1-2b.

6. [OWNER: Coder] Register new models and enums in `app/models/__init__.py`. Add `infer_data_tier` pure helper function in `app/models/athlete_preferences.py`.

## Context Needed

- `01-entities/athlete-profile.md` — full profile schema contract
- `01-entities/athlete-preferences.md` — preferences schema, weekly schedule JSONB shape
- `01-entities/activity.md` — lean activity schema contract
- `00-foundations/terminology.md` — enum values for `Sex`, `ActivitySource`, `DataTier`
- `00-foundations/data-tiers.md` — hardware capability tiers and inference rules
- `docs/vision/twin/cold-start.md` — honest onboarding tier philosophy
- `docs/vision/product/constraints.md` — running-only twin, no raw-data surfaces

## Batch Success Criteria

- `alembic upgrade head` succeeds on a fresh database
- Phase 1-1 registration journey still works (creates one Athlete, one AthleteAuth, one minimal AthleteProfile, one RefreshToken)
- `athlete_profiles` has full Phase 1-2a column set with unique `athlete_id` constraint preserved
- `athlete_profiles` auth path (minimal profile creation at registration) still works — no NOT NULL violations on new columns
- `athlete_preferences` has unique `athlete_id` and `years_structured_training >= 0` enforced at DB level
- `activities` contains lean observation fields and does NOT contain `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns
- Duplicate `(athlete_id, external_id, source)` with non-null `external_id` raises uniqueness violation
- `ActivitySource` enum values: exactly `intervals_icu`, `manual_upload`, `garmin_direct`, `manual_entry`
- `DataTier` enum values: exactly 1-6
- `infer_data_tier(hr_source, power_source)` correctly maps all documented combinations (tier 1-6)
- Existing auth API and repository tests pass without schema regressions

## Files Expected To Change

- `app/models/athlete_profile.py` — extend model columns
- `app/models/athlete_preferences.py` — new model (+ `infer_data_tier` helper)
- `app/models/activity.py` — new model
- `app/models/enums.py` — add `ActivitySource`, `DataTier`
- `app/models/__init__.py` — register new models + enums + `infer_data_tier`
- `migrations/versions/<rev>_phase_1_2a_profile_preferences_activity.py` — new migration

## Coder Notes

- **Schema-only**. No services, no APIs, no event production, no onboarding writes. Models and migration only.
- **Additive migration only**. `athlete_profiles` already exists from Phase 1-1. Extend with ALTER TABLE ADD COLUMN. Never drop and recreate.
- **Phase 1-1 compatibility**. Existing registration creates a minimal profile. New columns (e.g. `timezone`) must be nullable — NOT NULL constraints break the existing auth registration path.
- **`Activity.planned_session_id`**. Column is nullable UUID. FK to `planned_sessions` is added in Phase 1-2b when that table exists. Do not create the FK here.
- **Lean activity model**. No `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns. `Activity` is a physiological observation index, not a workout dashboard.
- **`fit_file_key` is the reprocessing anchor**. Column definition only in this plan. The invariant that non-manual activities require the raw FIT file stored before Activity creation belongs to the ingestion implementation (Phase 1-6).
- **Flag — `ActivityRepository` missing from `app/repositories/__init__.py`**. As of 2026-07-19, `ActivityRepository` is implemented but not exported in the init file. This is a pre-existing registration gap.
