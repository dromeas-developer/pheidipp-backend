# Validation Report — Phase-1.2a-P1
Date: 2026-06-20
Plan: docs/implementation/phase-1/phase-1-2a-p1-profile-preferences-activity.md

## Result: PASS WITH MINORS

---

## Layer 1: Plan Conformance

| Step | Description | Severity | Finding |
|------|-------------|----------|---------|
| 1 | Extend AthleteProfile with 11 columns | ✅ | All 11 columns added in correct order via `ALTER TABLE ADD COLUMN` |
| 2 | Add AthletePreferences model | ✅ | Model created with one-to-one athlete ownership and all required fields |
| 3 | Add Activity model | ✅ | Lean observation index created with all required fields, no forbidden columns |
| 4 | Define/register schema enums | ✅ | Sex, ActivitySource, DataTier, and preference enums all defined correctly |
| 5 | Create Phase-1.2a Alembic migration | ✅ | Migration creates tables, extends athlete_profiles, adds constraints |
| 6 | Register models and enums | ✅ | All models and enums exported in `app/models/__init__.py` |
| 7 | Add schema and migration tests | ✅ | Comprehensive test suite covers all invariants |

---

## Layer 2: Contract Conformance

| Contract | Check | Severity | Finding |
|----------|-------|----------|---------|
| Invariant: AthleteProfile one per Athlete | ✅ | Unique constraint on athlete_id preserved |
| Invariant: AthletePreferences one per Athlete | ✅ | Unique constraint on athlete_id enforced |
| Invariant: Activity has no avg_hr/avg_pace/avg_power/lap data | ✅ | Lean schema verified, all forbidden fields absent |
| Invariant: manual_entry has calibration_eligible=false, null load scores, null fit_file_key | ✅ | DB allows these; service-layer enforcement noted in docs |
| Invariant: Deduplication (athlete_id, external_id, source) unique where external_id non-null | ✅ | Partial unique index `uq_activities_athlete_external_source` with `WHERE external_id IS NOT NULL` |
| Invariant: fit_file_key required for non-manual_entry | ⚠️ | PLAN GAP — Invariant stated in plan but DB column is nullable (service-layer only) |
| Invariant: years_structured_training >= 0 | ✅ | CHECK constraint `ck_athlete_preferences_years_structured_training_non_negative` |
| Invariant: timezone immutable after creation | ⚠️ | PLAN GAP — Column is nullable, no DB-level immutability constraint |
| Event: activity_ingested | ✅ | Correctly NOT PRODUCED (out of scope) |
| Event: activity_calibration_eligible | ✅ | Correctly NOT PRODUCED (out of scope) |

---

## Layer 3: Deviations

| Item | What Was Added | Classification | Action |
|------|---------------|----------------|--------|
| `WeeklySchedule` structure in code comments | Documentation of JSONB structure in model docstrings | Acceptable | Helpful inline documentation, no action needed |
| Test suite expanded beyond requirements | Additional edge case tests | Acceptable | More thorough coverage, no action needed |

---

## Stack-Truth

### CRITICAL
- None

### MAJOR
- None

### MINOR
- `timezone` column is nullable in DB schema — plan states it's "required at onboarding" and "immutable after creation", but migration creates it as nullable with no immutability constraint. This is actually CORRECT per plan Step 1 which states columns are "nullable so Phase-1.1 registration path continues to work". However, plan Invariants section states immutability. This is a plan ambiguity, not an implementation error.

---

## Validation Confidence

**Level: HIGH**

| Dimension | Status |
|-----------|--------|
| Contracts embedded in plan | yes |
| Implementation files retrieved | 11 of 11 listed in scope |
| Release alignment checked | yes — belongs to Phase 1 |
| Deviation scan complete | yes |
| Dynamic context available | yes — implemented-state.md present |

All critical plan requirements are satisfied. The implementation correctly:
- Extends AthleteProfile with all 11 columns (gap_curve_model, weather_response_model, banister_constants, cycle_personal_model, location_lat, location_lng, timezone, training_window, current_effort_generation, structural_risk_flag, objective_thresholds)
- Creates AthletePreferences with unique athlete_id and CHECK constraint
- Creates Activity lean index with all required fields
- Implements partial unique dedup index with WHERE external_id IS NOT NULL
- Defines all enums with correct values
- Preserves Phase-1.1 registration path
- Provides comprehensive test coverage

---

## Routing

| Finding | Route To |
|---------|----------|
| MINOR (filename typo) | p-coder + this report |