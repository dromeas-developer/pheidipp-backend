# Implementation Plan: Phase-2.1 — FIT Ingestion Pipeline Expansion

## Plan ID: Phase-2.1-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-2.1
Sub-Phase Title: FIT Ingestion Pipeline Expansion & Calibration Eligibility

## Objective
Expand the FIT ingestion pipeline to process full sensor signals (power, GPS, RR intervals) and evaluate calibration eligibility per the five-rule gate. This plan activates power-based load computation for Tier 1-2 athletes, neuromuscular and structural load computation for eligible tiers, and transitions `CalibrationEligibilityService` from the Phase-1.6 hard-off to the full rule-based evaluation. Activities now properly populate the calibration pipeline, creating the foundation for threshold detection in Phase-2.3.

## Scope
- Add `has_gps` field to `Activity` model and database schema
- Expand `FitParserService` to extract GPS records (distance, elevation, speed/pace), RR interval data (full time-series, not just presence flag), and lap data from FIT files
- Extend `ParsedFitData` dataclass to carry GPS records, RR interval records, and lap data
- Expand `LoadComputationService` to compute:
  - Power-based aerobic load for Tier 1-2 athletes (replaces HR-based formula when power available)
  - Neuromuscular load for Tier 1-4 (variability index + time above VO2max)
  - Structural load for activities with GPS data (distance + elevation + density penalty)
- Activate full five-rule calibration eligibility gate in `CalibrationEligibilityService` (remove PHASE_1_6_HARD_OFF)
- Update `ActivityIngestionService` to:
  - Infer data tier from `AthletePreferences` hardware sources
  - Populate `has_gps` flag based on parsed FIT data
  - Pass data tier to `LoadComputationService` for tier-specific formula selection
  - Fire `activity_calibration_eligible` event when `calibration_eligible = true`
- Update activity API response schemas to include `has_gps` flag

## Out Of Scope
- Signal cleaning pipeline (Phase 2.2) — raw FIT data used for calibration eligibility but cleaning deferred
- Threshold detection algorithms (Phase 2.3) — calibration eligibility comes first
- `ActivityPowerProfile` creation (Phase 2.6) — requires `calibration_eligible = true` AND `has_power = true` but implemented separately
- Power load coaching observation metrics (`supra_threshold_joules`, `w_prime_depletion_pct`) — deferred to Phase 2.6
- Auto-sync integrations (intervals.icu, Garmin direct) — manual upload only for Phase 2.1
- Surface type detection from GPS — uses `unknown` default for structural load computation
- `RawSensorStream` entity creation — deferred to Phase 2.2 signal cleaning

## Architecture Contracts
- `01-entities/activity.md` — IMPLEMENTS (extends signal flags, load computation)
- `01-entities/athlete-physiology.md` — DEPENDS ON (threshold references not yet used; future Phase 2.3)
- `00-foundations/data-tiers.md` — IMPLEMENTS (tier-specific load computation, calibration rules)
- `02-computations/load-computation.md` — IMPLEMENTS (full three-dimensional load formulas)
- `02-computations/signal-cleaning.md` — DEPENDS ON (understanding input format; cleaning deferred)
- `04-platform/storage-topology.md` — DEPENDS ON (object storage for FIT files)
- `04-platform/event-topology.md` — IMPLEMENTS (fires `activity_calibration_eligible`)

## Invariants
- `fit_file_key` is REQUIRED and never null for any source other than `manual_entry`. The ingestion task must store the FIT file in object storage before creating the Activity record. If storage fails, no Activity is created and the task retries.
- `avg_hr`, `avg_pace`, `avg_power`, `avg_cadence`, `lap_data` — these fields do not exist on `Activity`. They are never added.
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService` synchronously within the ingestion task.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden.
- Source `manual_entry` activities always have `calibration_eligible = false`, null load scores, and null `fit_file_key`. These are not error conditions.
- Deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null. Duplicate ingestion attempts for the same external session create one Activity.
- Tier 5 and 6 activities are never `calibration_eligible`.
- Tier 6 activities have null `aerobic_load`, `neuromuscular_load`, `structural_load`.
- A session without GPS (`has_gps = false`) defaults to Tier 6 for structural load purposes even if HR is present.
- Grade-adjusted pace (GAP) is always used as the mechanical work proxy. Raw pace is never used in any calculation.
- Non-running activities are excluded from twin calibration.

## Implementation Steps

1. [OWNER: Coder] Add `has_gps` boolean column to `Activity` model in `app/models/activity.py`. Set `nullable=False`, `default=False`, `server_default="false"`. Add index on `(athlete_id, activity_date)` filtered by `calibration_eligible = true` if not already present.

2. [OWNER: DevOps] Generate Alembic migration for the new `has_gps` column. Review for hypertable compatibility if applicable. Apply to test database.

3. [OWNER: Coder] Extend `ParsedFitData` dataclass in `app/services/fit_parser_service.py` to include:
   - `gps_records: List[GpsRecord]` where `GpsRecord` is a frozen dataclass with `timestamp`, `position_lat`, `position_long`, `distance`, `altitude`, `speed` fields
   - `rr_records: List[float]` — RR interval values in milliseconds
   - `total_distance_m: float | None` — total distance from session message
   - `total_ascent_m: float | None` — total elevation gain from session message
   - `has_gps: bool` — true when GPS records present
   - `moving_duration_seconds: int` — moving time (excluding auto-pause)

4. [OWNER: Coder] Expand `FitParserService._parse_sync` to extract GPS records from `record` messages containing position/distance/altitude fields, RR interval values from `rr_interval` fields (not just presence detection), and session-level totals (total distance, total ascent). Populate all new `ParsedFitData` fields. Update artifact detection to flag GPS spikes (speed > 25 m/s).

5. [OWNER: Coder] Extend `LoadComputationInputs` in `app/services/load_computation_service.py` to include:
   - `data_tier: DataTier`
   - `total_distance_m: float | None`
   - `total_ascent_m: float | None`
   - `recent_structural_load_72h: float`
   - `structural_risk_flag: bool` (from `AthleteProfile.sport_background != 'running_primary'`)
   - `power_records: List[int] | None`

6. [OWNER: Coder] Implement power-based aerobic load computation in `LoadComputationService`. For Tier 1-2 athletes with power data, use the fourth-power intensity factor formula: `acc += (watts / cp_estimate)^4` normalised to 3600 seconds. Fall back to HR-based formula when power unavailable. Requires `AthletePhysiology.cp` or uses population estimate when null.

7. [OWNER: Coder] Implement neuromuscular load computation in `LoadComputationService`. Compute variability index (coefficient of variation of power or GAP over session) and time above VO2max threshold (95% of LT2 intensity). Available for Tier 1-4. Returns null for Tier 5-6.

8. [OWNER: Coder] Implement structural load computation in `LoadComputationService`. Use formula: `base = (distance_km) * surface_modifier`, `gradient_cost = (elevation_gain_m / 100) * 0.18 * distance_km`, `density_penalty = min(recent_structural_load_72h * coefficient, 15)`. Surface type defaults to `unknown` (modifier 1.0). Crossover athlete coefficient: 0.08 for structural risk flag, 0.12 otherwise. Requires GPS data; returns null when `has_gps = false`.

9. [OWNER: Coder] Update `LoadComputationService.compute_aerobic_load` to return fully populated `LoadScores` dataclass with all three dimensions computed according to data tier capabilities. Update method signature to accept `LoadComputationInputs` with all required fields.

10. [OWNER: Coder] Activate full five-rule gate in `CalibrationEligibilityService.evaluate` by setting `PHASE_1_6_HARD_OFF = False`. The gate checks: `has_hr AND source != manual_entry AND duration >= 1200s AND hr_dropout_pct <= 0.20 AND NOT gps_loss AND NOT sensor_malfunction`. Note: `isUsableSessionType` check deferred (requires session classification from Phase 2.2).

11. [OWNER: Coder] Update `ActivityIngestionService._run_ingestion_pipeline` to:
    - Fetch `AthletePreferences` to infer data tier via `infer_data_tier()`
    - Fetch recent structural load sum from `ActivityRepository` (72h window)
    - Pass expanded inputs to `LoadComputationService`
    - Populate `has_gps` flag on Activity from parsed FIT data
    - Update `Activity.quality_flags` with `hr_dropout_pct` computed from HR record continuity analysis
    - Evaluate calibration eligibility and update `Activity.calibration_eligible`

12. [OWNER: Coder] Update `ActivityIngestionService._run_ingestion_pipeline` to fire `activity_calibration_eligible` event via `EventPublisher` when `calibration_eligible = true` AND load scores are non-null. Event payload: `{activity_id, aerobic_load, neuromuscular_load, structural_load}`. Event fires within the same transaction as Activity update.

13. [OWNER: Coder] Update `ActivityRepository` to add method `get_recent_structural_load(athlete_id, since_date)` that sums `structural_load` for calibration-eligible activities in the time window. Used by density penalty computation.

14. [OWNER: Coder] Add `has_gps` field to `ActivityResponse` and `ActivityListResponse` schemas in `app/schemas/activity.py`. Update response builders to include the new field.

15. [OWNER: Coder] Update `app/models/__init__.py` exports if new enums or types are introduced. Update `app/schemas/__init__.py` exports for modified response schemas. Update `app/services/__init__.py` exports for new dataclasses.

16. [OWNER: Test Architect] Write tests for expanded `FitParserService`:
    - GPS record extraction from standard FIT files
    - RR interval time-series extraction
    - Artifact detection (GPS spikes, impossible HR values)
    - Empty GPS data handling
    - Session-level totals extraction

17. [OWNER: Test Architect] Write tests for `LoadComputationService`:
    - Power-based aerobic load for Tier 1-2 (verify formula against known values)
    - HR-based aerobic load for Tier 3-4 (existing behavior preserved)
    - Neuromuscular load computation (variability index + VO2max time)
    - Structural load with density penalty (verify cap at MAX_DENSITY_PENALTY=15)
    - Null returns for Tier 5-6 where appropriate
    - Crossover athlete coefficient adjustment

18. [OWNER: Test Architect] Write tests for `CalibrationEligibilityService`:
    - All five gate rules evaluated correctly
    - `manual_entry` always returns false
    - Short duration (< 1200s) returns false
    - HR dropout > 20% returns false
    - GPS loss and sensor malfunction flags handled
    - Tier 5-6 activities return false

19. [OWNER: Test Architect] Write integration tests for `ActivityIngestionService`:
    - Full pipeline with power + GPS + RR data produces all three load scores
    - `activity_calibration_eligible` event fires when eligible
    - Event does not fire when calibration_eligible = false
    - `has_gps` populated correctly
    - Data tier inferred from preferences and used for formula selection

## Event Contracts

### Produces
| Event | Trigger | Payload | Ordering |
|---|---|---|---|
| `activity_calibration_eligible` | `calibration_eligible` set to `true` AND load scores non-null | `{activity_id: string, aerobic_load: number, neuromuscular_load: number \| null, structural_load: number \| null}` | Fires after Activity update within same transaction. Must fire after `activity_ingested` event for same activity. |

### Consumes
None. This plan only produces events.

## Pseudocode

```
# Load Computation Flow (Step 9)
receive ParsedFitData, AthletePreferences, recent_structural_load_72h
data_tier = infer_data_tier(preferences.hr_source, preferences.power_source)

# Aerobic load
if data_tier in [1, 2] and ParsedFitData.has_power:
    aerobic_load = compute_power_aerobic_load(ParsedFitData.power_records, physiology.cp)
elif ParsedFitData.has_hr:
    aerobic_load = compute_hr_aerobic_load(ParsedFitData.hr_records, max_hr, resting_hr)
else:
    aerobic_load = null  # Tier 5-6

# Neuromuscular load
if data_tier in [1, 2, 3, 4]:
    values = ParsedFitData.power_records if data_tier in [1, 2] else gap_records
    variability = coefficient_of_variation(values)
    time_above_vo2 = count(values > vo2_threshold)
    neuromuscular_load = (variability * duration_hours) + (time_above_vo2_hours * 2.5)
else:
    neuromuscular_load = null

# Structural load
if ParsedFitData.has_gps and total_distance_m > 0:
    surface_modifier = 1.0  # unknown default
    base = (total_distance_m / 1000) * surface_modifier
    gradient_cost = (total_ascent_m / 100) * 0.18 * (total_distance_m / 1000)
    density_coefficient = 0.08 if structural_risk_flag else 0.12
    density_penalty = min(recent_structural_load_72h * density_coefficient, 15)
    structural_load = base + gradient_cost + density_penalty
else:
    structural_load = null

return LoadScores(aerobic_load, neuromuscular_load, structural_load)
```

```
# Calibration Eligibility Flow (Step 10-12)
receive Activity, ParsedFitData
if Activity.source == 'manual_entry':
    calibration_eligible = false
elif not Activity.has_hr:
    calibration_eligible = false
elif ParsedFitData.moving_duration_seconds < 1200:
    calibration_eligible = false
elif quality_flags.hr_dropout_pct > 0.20:
    calibration_eligible = false
elif quality_flags.gps_loss:
    calibration_eligible = false
elif quality_flags.sensor_malfunction:
    calibration_eligible = false
elif data_tier in [5, 6]:
    calibration_eligible = false
else:
    calibration_eligible = true

Activity.calibration_eligible = calibration_eligible

if calibration_eligible and aerobic_load is not null:
    fire activity_calibration_eligible event
```

## Testing Requirements
- Uploading a FIT file with power data creates an `Activity` with `has_power = true`, non-null `aerobic_load` (power-based), and `calibration_eligible = true` when it meets the five-rule gate
- Uploading a FIT file without power but with GPS and HR creates `Activity` with `has_gps = true`, HR-based `aerobic_load`, non-null `structural_load`, and `calibration_eligible = true` when eligible
- Uploading a FIT file with RR intervals creates `Activity` with `has_rr_intervals = true` and full RR time-series in parsed data
- Uploading a FIT file with optical HR only (no GPS, no power) creates `Activity` with HR-based load, null structural/neuromuscular load, and `calibration_eligible` based on gate rules
- Simulating a FIT file that fails the five-rule gate (e.g., duration < 1200s) results in `calibration_eligible = false` and null load scores
- `GET /athletes/{id}/activities/{aid}` shows `has_gps`, `has_power`, `has_rr_intervals` flags correctly populated
- Structural load density penalty caps at MAX_DENSITY_PENALTY (15) even with extreme recent load values
- Tier 5 activities (GPS only, no HR) get `calibration_eligible = false` and null load scores
- `activity_calibration_eligible` event fires with correct payload when eligibility is true

## Coder Handoff Notes

## Coder Scope
Execute:  Steps 1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15  [OWNER: Coder] — includes migration generation
Skip:     Step 2 (DevOps — migration review and application),
          Steps 16, 17, 18, 19 (Test Architect — tests)

### Known Risks
1. **Power-based load requires CP estimate**: `LoadComputationService` needs a critical power reference. `AthletePhysiology.cp` is null until threshold detection runs (Phase 2.3). For Phase 2.1, use a population estimate (e.g., 250W for male, 200W for female) or derive from `AthleteProfile.fitness_level` as a bootstrap. Mark this clearly as a bootstrap value that Phase 2.3 will replace.

2. **GPS quality varies widely**: GPS data quality affects structural load accuracy. The `gps_loss` quality flag is set by FIT parsing artifact detection (Step 4). Be conservative in flagging GPS loss — only flag when position/altitude data is missing for > 30 continuous seconds during moving time, not for brief signal drops.

3. **RR interval extraction may vary by device**: Different FIT producers encode RR intervals differently. Some use `rr_interval` field, others use HRV messages. Test with multiple device types (Garmin, Polar, Wahoo). If extraction fails for a device, set `has_rr_intervals = false` rather than raising an error — the activity is still valid for HR-based processing.

### Architecture Interpretations
1. **`moving_duration_seconds` vs `duration_seconds`**: The calibration gate uses moving duration (time excluding auto-pause), not total elapsed time. Extract this from FIT `total_timer_time` (which excludes auto-pause in most implementations), falling back to `total_elapsed_time` or HR record count if unavailable.

2. **Surface type defaults to `unknown`**: Phase 2.1 does not implement surface detection from GPS coordinates. Use `SURFACE_MODIFIERS['unknown'] = 1.0` for all structural load computations. Phase 2.2 or later may add surface classification.

3. **Density penalty requires historical query**: The structural load formula references `recent_structural_load_72h`, which requires querying previous activities. For an athlete's first activity, this value is 0. The query should use `ActivityRepository.get_recent_structural_load()` filtering by `calibration_eligible = true` and `structural_load IS NOT NULL`.

### Suggested Implementation Order
1. Model changes first (Step 1-2) to establish schema
2. FIT parser expansion (Steps 3-4) to get richer data
3. Load computation services (Steps 5-9) building from simplest (HR) to most complex (structural with density penalty)
4. Calibration eligibility activation (Step 10) now that data is available
5. Pipeline orchestration (Steps 11-13) wiring everything together
6. API surface updates (Steps 14-15) last as they depend on all prior work

### Event Ordering
The `activity_calibration_eligible` event must fire **after** `activity_ingested` for the same activity. Both events fire within the same transaction. The outbox pattern ensures they are published in insertion order after commit.

### Deferred Capabilities
- Power load coaching metrics (`supra_threshold_joules`, `w_prime_depletion_pct`) are explicitly deferred to Phase 2.6. Do not implement them in this plan.
- `ActivityPowerProfile` creation is Phase 2.6 scope. This plan only computes load scores on Activity.
- Signal cleaning (Phase 2.2) operates on the raw FIT data extracted here. Ensure `ParsedFitData` output is compatible with the 7-step cleaning pipeline defined in `02-computations/signal-cleaning.md`.
