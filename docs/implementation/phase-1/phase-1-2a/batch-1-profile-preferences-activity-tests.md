> **Baseline — test companion for** `batch-1-profile-preferences-activity.md`, migrated from `docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements. Schema-only plan — tests focus on migration, model metadata, and constraint enforcement.

### Migration
- Given fresh database, `alembic upgrade head` succeeds with no migration errors
- Given existing Phase 1-1 database, migration applies without data loss (existing athlete + profile rows survive)
- Given migration is reversible: `alembic downgrade -1` succeeds

### Backward Compatibility — Phase 1-1 Registration
- Given Phase 1-1 registration journey (`POST /auth/register`), creates exactly one `Athlete`, one email-provider `AthleteAuth`, one minimal `AthleteProfile`, and one `RefreshToken`
- Given existing auth endpoints still return expected responses after migration
- Given no NOT NULL violations on new profile columns when minimal registration creates a profile

### AthleteProfile Schema
- Given `athlete_profiles` contains full Phase 1-2a columns: `gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`, `location_lat`, `location_lng`, `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, `objective_thresholds`
- Given `athlete_profiles.athlete_id` has unique constraint
- Given new JSONB columns default to NULL (no schema-level default — nullable)
- Given existing columns (`date_of_birth`, `sex`, `height_cm`, `updated_at`) are preserved

### AthletePreferences Schema
- Given `athlete_preferences.athlete_id` has unique constraint (one-to-one with athletes)
- Given `years_structured_training` has CHECK constraint ≥ 0 at database level
- Given inserting `years_structured_training = -1` raises constraint violation
- Given `weekly_schedule` column is JSONB type, not null
- Given all preference fields are present: `sport_background`, `training_time_of_day`, `gps_source`, `hr_source`, `power_source`, `primary_training_platform`

### Activity Schema
- Given `activities` contains lean observation fields: `id`, `athlete_id`, `planned_session_id`, `source`, `external_id`, `activity_date`, `start_time`, `duration_seconds`, `aerobic_load`, `neuromuscular_load`, `structural_load`, `has_hr`, `has_rr_intervals`, `has_power`, `calibration_eligible`, `quality_flags`, `fit_file_key`, `ingestion_pipeline_version`, `cleaning_pipeline_version`, `notes`, `created_at`
- Given `activities` does NOT contain: `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, or lap-data columns (verify by schema inspection)
- Given `calibration_eligible` defaults to `false`
- Given `has_hr`, `has_rr_intervals`, `has_power` default to `false`
- Given `quality_flags` defaults to `{}` (empty JSONB)
- Given `planned_session_id` is nullable UUID (FK deferred to phase-1-2b)

### Deduplication Constraint
- Given two activities with same `(athlete_id, external_id, source)` where `external_id` is non-null → uniqueness violation
- Given two activities with same `athlete_id` and `source` but different `external_id` → both succeed
- Given two activities with same `athlete_id` and `external_id` but `external_id = null` → both succeed (partial unique index skips null)

### Enum Values
- Given `ActivitySource` enum values are exactly: `INTERVALS_ICU`, `MANUAL_UPLOAD`, `GARMIN_DIRECT`, `MANUAL_ENTRY`
- Given `DataTier` enum values are exactly: `TIER_1`, `TIER_2`, `TIER_3`, `TIER_4`, `TIER_5`, `TIER_6`
- Given `Sex` enum remains compatible with Phase 1-1 values: `male`, `female`, `not_specified`
- Given inserting `source` value outside the enum raises integrity error

### Data Tier Inference
- Given `infer_data_tier(hr_source=CHEST_STRAP, power_source=POWER_METER)` → `TIER_1`
- Given `infer_data_tier(hr_source=CHEST_STRAP, power_source=NONE)` → `TIER_3`
- Given `infer_data_tier(hr_source=WRIST_OPTICAL, power_source=POWER_METER)` → `TIER_2`
- Given `infer_data_tier(hr_source=WRIST_OPTICAL, power_source=NONE)` → `TIER_4`
- Given `infer_data_tier(hr_source=NONE, power_source=NONE)` → `TIER_5`
- Given all documented `{hr_source, power_source}` combinations map correctly

### Model Registration
- Given `AthleteProfile`, `AthletePreferences`, `Activity` are importable from `app.models`
- Given `ActivitySource`, `DataTier` are importable from `app.models`
- Given `infer_data_tier` is importable from `app.models`
- Given `activities` table is discoverable by Alembic autogenerate (model registered in `Base.metadata`)

### Indexes
- Given partial unique index exists on `(athlete_id, external_id, source) WHERE external_id IS NOT NULL`
- Given composite index exists on `(athlete_id, activity_date)`
- Given composite index exists on `(athlete_id, start_time)`
- Given FK index exists on `athlete_id` referencing `athletes`
