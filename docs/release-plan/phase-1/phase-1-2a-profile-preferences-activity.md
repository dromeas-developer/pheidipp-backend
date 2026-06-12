# Phase 1 — Core Models: Profile, Preferences, Activity
## Sub-Phase ID: Phase-1.2a

## Objective
Establish the supporting data structures that define who the athlete is (profile), how they train (preferences), and what they have done (activity). These entities are created during onboarding (1.3) and consumed by nearly every downstream system. `AthleteProfile` and `AthletePreferences` are each one-to-one with `Athlete`. `Activity` is the lean physiological observation — it represents a completed training session with minimal metadata, deferring rich signal storage to Phase 1.6.

## Challenge Notes
This sub-phase isolates the athlete-context tables so the architect can focus on profile/preferences precision without being overwhelmed by the full schema. The `TrainingBlock` entity name from the initial draft has been superseded by `TrainingGoal` in the final Phase 1 design (handled in 1.2b).

The `athlete_profiles` table was created in Phase-1.1 with a minimal schema (demographics only — `date_of_birth`, `sex`, `height_cm`). This sub-phase extends it to the full schema via Alembic migration, adding the personalisation model columns (`gap_curve_model`, `weather_response_model`, `banister_constants`, `cycle_personal_model`), location fields (`location_lat`, `location_lng`), `timezone`, `training_window`, `current_effort_generation`, `structural_risk_flag`, and `objective_thresholds`. The `athlete_profiles` table is never dropped and recreated — it is only extended.

## Capabilities Delivered
- Schema for `AthleteProfile` (demographics, personalisation storage)
- Schema for `AthletePreferences` (training configuration, data tier inference)
- Schema for `Activity` (lean observation index)
- Alembic migration for these tables and all required enums
- All constraints, indexes, and enums defined

## Architectural Contracts Required
- `01-entities/athlete-profile.md`
- `01-entities/athlete-preferences.md`
- `01-entities/activity.md`
- `00-foundations/terminology.md` (enums)
- `00-foundations/data-tiers.md` (data tier inference logic)

## Vision References Required
- `twin/cold-start.md` — onboarding tier philosophy
- `product/constraints.md` — running-only, no raw data surfaces

## Upstream Dependencies
- Phase-1.1 (Auth) — `Athlete` and the minimal `athlete_profiles` table must exist. The `athlete_profiles` table was created in Phase-1.1 with a minimal schema (demographics only). This sub-phase extends it to the full schema via Alembic migration.

## Downstream Enablement
- Phase-1.2b — `Activity` is referenced by `PlannedSession`
- Phase-1.2c — `AthleteProfile` stores personalisation models (`gap_curve_model`, `weather_response_model`, `banister_constants`)
- Phase-1.3 (Onboarding) — creates `AthleteProfile` and `AthletePreferences`
- Phase-1.4 (Plan Generation) — `AthletePreferences.weekly_schedule` constrains session distribution
- Phase-1.6 (FIT Import) — creates `Activity` records

## Invariants To Preserve
- `AthleteProfile`: one per `Athlete`. Unique constraint on `athlete_id`.
- `AthletePreferences`: one per `Athlete`. Unique constraint on `athlete_id`.
- `Activity` has no `avg_hr`, `avg_pace`, `avg_power`, or lap data fields.
- `Activity.source = 'manual_entry'` always has `calibration_eligible = false`, null load scores, null `fit_file_key`.
- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.

## Non-Goals
- Data is not written to these tables in this sub-phase — only schema creation.
- `AthleteIntegration` model (platform sync) — deferred to Phase 2.
- `RawSensorStream` and `PhysiologicalSegment` — deferred to Phase 5/6.

## Exit Gate
- All migrations run cleanly on a fresh database with no errors.
- `Activity` has no `avg_hr`, `avg_pace`, `avg_power` columns.
- `AthleteProfile` enforces unique constraint on `athlete_id`.
- `AthletePreferences` enforces unique constraint on `athlete_id`.

## Risks
- **Schema drift**: If 1.2b or 1.2c identify missing fields, migrations may need revision. Mitigation: expose schema early in each sub-phase.
- **Enum alignment**: `ActivitySource`, `DataTier`, `PhysiologicalIntentState` and other enums must be correct now or downstream phases will break. Mitigation: copy exact from `terminology.md`.
