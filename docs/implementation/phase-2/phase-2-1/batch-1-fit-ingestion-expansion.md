> **Baseline — migrated from** `docs/implementation/phase-2/phase-2-1-p1-fit-ingestion-expansion.md`, `phase-2-1-p2-validation-remediation.md`, and `phase-2-1-p3-sport-type-filtering.md` **on** 2026-07-19.
> This plan documents what was built in Phase 2-1, verified against the current codebase on 2026-07-19.

## Batch Objective

Expand the FIT ingestion pipeline to process full sensor signals (power, GPS, RR intervals), correctly identify sport type from FIT files, and evaluate calibration eligibility. This activates power-based load computation for Tier 1-2 athletes, neuromuscular and structural load computation, and enforces the running-only boundary for twin calibration (Principle #8). Non-running activities are recorded in the training log but excluded from the calibration pipeline.

## Preconditions

Depends on Phase-1.6 simple FIT import (basic HR-only ingestion), `Activity` model (has_hr, has_power, has_rr_intervals, fit_file_key already exist), `FitParserService` (basic FIT parsing), `ObjectStorageClient`.

## Scope

**Schema:**
- `has_gps` boolean column on `Activity`
- `SportType` enum: `running`, `cycling`, `swimming`, `strength`, `yoga_mobility`, `other`, `unknown`
- `sport_type` and `sport_type_detection_version` columns on `Activity`

**FIT parser expansion:**
- GPS records (distance, elevation, speed/pace), RR interval time-series, session-level totals
- FIT `sport`/`sub_sport` extraction mapped to `SportType` via Garmin/Ant+ mapping table
- `detection_confidence` (`high`/`low`/`unknown`) and `detection_version` (`"v1"`) on parsed data
- GPS spike artifact detection (speed > 25 m/s)

**Load computation:**
- Power-based aerobic load (Tier 1-2, fourth-power intensity factor; falls back to HR for Tier 3-4)
- Neuromuscular load (Tier 1-4: variability index + time above VO2max)
- Structural load (GPS required: distance + elevation + density penalty, cap 15, crossover coefficient 0.08 vs 0.12)

**Calibration eligibility:**
- Sport-type gate as first check: `sport_type != 'running'` → `false` immediately
- Five-rule gate: `has_hr AND source != manual_entry AND duration >= 1200s AND hr_dropout_pct <= 0.20 AND NOT gps_loss AND NOT sensor_malfunction`
- Tier 5-6 activities never eligible
- Non-running activities' `data_tier` overridden to Tier 6

**Quality flags:**
- `gps_loss` via continuous-gap detection (> 30s gap between consecutive timestamps, not coverage ratio)
- `structural_risk_flag` via `AthleteProfileRepository` (not raw SQL)

**Events:**
- `sport_type_detected` — fires for all non-manual-entry sources with `{activity_id, sport_type, detection_confidence, detection_version}`
- `activity_calibration_eligible` — fires when eligible with `{activity_id, aerobic_load, neuromuscular_load, structural_load}`
- Event ordering within transaction: `sport_type_detected` → `activity_ingested` → `activity_calibration_eligible`

**API:**
- `has_gps`, `sport_type`, `sport_type_detection_version` in `ActivityResponse`

## Steps

### Schema Layer

1. [OWNER: Coder] Add `has_gps` boolean column to `Activity` model. `nullable=False`, `default=False`, `server_default="false"`.

2. [OWNER: Coder] Add `SportType` enum to `app/models/enums.py` with values: `running`, `cycling`, `swimming`, `strength`, `yoga_mobility`, `other`, `unknown`. Use the `str, Enum` pattern.

3. [OWNER: Coder] Add `sport_type` (non-null, `server_default='unknown'`, SAEnum with `length=32`) and `sport_type_detection_version` (nullable `String(16)`) columns to `Activity` model. Register `SportType` in `app/models/__init__.py`.

4. [OWNER: DevOps] Generate Alembic migrations for `has_gps`, `sport_type`, and `sport_type_detection_version`. Backfill `calibration_eligible = false` for all existing rows where `sport_type = 'unknown'`.

### FIT Parser Expansion

5. [OWNER: Coder] Extend `ParsedFitData` dataclass with: `gps_records: List[GpsRecord]` (timestamp, position_lat, position_long, distance, altitude, speed), `rr_records: List[float]` (ms values), `total_distance_m: float | None`, `total_ascent_m: float | None`, `has_gps: bool`, `moving_duration_seconds: int`, `sport_type: SportType` (default `UNKNOWN`), `detection_confidence: str` (default `"unknown"`), `detection_version: str` (default `"v1"`).

6. [OWNER: Coder] Expand `FitParserService._parse_sync` to extract: GPS records from `record` messages, RR interval values from `rr_interval` fields (time-series, not just presence), session-level totals (`total_distance`, `total_ascent`), and FIT `sport`/`sub_sport` from the `session` message. Map to `SportType` using the Garmin/Ant+ table: sport=1→`running`, 2→`cycling`, 3→`other`, 4→`strength`, 5→`swimming`, 14→`other`, 0/254/missing→`unknown`. Set `detection_confidence`: `"high"` when sport field present and mappable, `"low"` when present but unrecognized, `"unknown"` when absent/generic. Flag GPS spikes (speed > 25 m/s).

### Load Computation

7. [OWNER: Coder] Extend `LoadComputationInputs` with: `data_tier`, `total_distance_m`, `total_ascent_m`, `recent_structural_load_72h`, `structural_risk_flag`, `power_records`, `sport_type`, `sport_type_detection_version`.

8. [OWNER: Coder] Implement power-based aerobic load: fourth-power intensity factor `sum((watts / cp)^4)` normalised to 3600s, for Tier 1-2. Fall back to HR-based for Tier 3-4. Use CP from `AthletePhysiology.cp` or population estimate (250W male, 200W female).

9. [OWNER: Coder] Implement neuromuscular load: variability index (coefficient of variation of power or GAP) + time above VO2max (95% of LT2 intensity), for Tier 1-4. Null for Tier 5-6.

10. [OWNER: Coder] Implement structural load: `base = (distance_km) * surface_modifier` (surface defaults to `unknown` = 1.0), `gradient_cost = (elevation_gain_m / 100) * 0.18 * distance_km`, `density_penalty = min(recent_structural_load_72h * coefficient, 15)`. Coefficient: 0.08 for crossover athletes (`structural_risk_flag = true`), 0.12 otherwise. Requires GPS; returns null when `has_gps = false`.

### Calibration Eligibility

11. [OWNER: Coder] Activate full calibration eligibility gate in `CalibrationEligibilityService.evaluate`:

    **First check — sport-type exclusion:**
    - `if activity.sport_type != SportType.RUNNING: return False`

    **Five-rule gate (only reached for running activities):**
    - `source != manual_entry`
    - `has_hr = true`
    - `duration_seconds >= 1200`
    - `hr_dropout_pct <= 0.20`
    - `NOT gps_loss AND NOT sensor_malfunction`

    Tier 5-6 activities return false. `calibration_eligible` is never manually overridden.

### Ingestion Pipeline Wiring

12. [OWNER: Coder] Update `ActivityIngestionService._run_ingestion_pipeline`:

    a. After FIT parse: set `activity.sport_type` from `parsed.sport_type`, set `activity.sport_type_detection_version` from `parsed.detection_version`. Set `activity.has_gps` from `parsed.has_gps`.

    b. Infer `data_tier` from `AthletePreferences`. If `parsed.sport_type != SportType.RUNNING`, override `data_tier` to `DataTier.TIER_6`.

    c. Compute quality flags: `hr_dropout_pct` from HR continuity analysis. **`gps_loss`** uses continuous-gap detection (scan `parsed.gps_records` timestamps; flag `true` iff any single gap > 30 seconds; preserve: no-GPS → `false`, empty-GPS-list → `true`). Out-of-order timestamps (negative delta) not treated as gaps.

    d. **`structural_risk_flag`** read via `AthleteProfileRepository.get_by_athlete_id(athlete_id)`, defaulting to `False` when profile missing. Inject `AthleteProfileRepository` as an optional constructor dependency.

    e. Pass expanded `LoadComputationInputs` to `LoadComputationService`. Flush load scores and calibration eligibility to Activity.

    f. Fire events in order:
       - `sport_type_detected` (all non-manual-entry sources) — payload: `{activity_id, sport_type, detection_confidence, detection_version}`
       - `activity_ingested` (existing, add `sport_type` to payload)
       - `activity_calibration_eligible` (only when eligible AND aerobic_load non-null) — payload: `{activity_id, aerobic_load, neuromuscular_load, structural_load}`

    g. Add `ActivityRepository.get_recent_structural_load(athlete_id, since_date)` for density penalty computation.

### API Surface

13. [OWNER: Coder] Add `has_gps`, `sport_type`, and `sport_type_detection_version` fields to `ActivityResponse` schema. Update `ActivityListResponse` if independently defined.

14. [OWNER: Coder] Update `app/models/__init__.py` and `app/services/__init__.py` exports for `SportType`, `ParsedFitData`, `LoadComputationInputs`, and `LoadScores` with new fields.

## Context Needed

Schema: `app/models/activity.py`, `app/models/enums.py`, `app/models/__init__.py`
FIT parser: `app/services/fit_parser_service.py`, `02-computations/sport-type-detection.md`
Load computation: `app/services/load_computation_service.py`, `02-computations/load-computation.md`
Calibration: `app/services/calibration_eligibility_service.py`
Pipeline: `app/services/activity_ingestion_service.py`, `app/repositories/athlete_profile_repository.py`, `00-foundations/data-tiers.md`, `00-foundations/event-catalogue.md`
API: `app/schemas/activity.py`

## Batch Success Criteria

- `has_gps`, `sport_type`, `sport_type_detection_version` columns exist on Activity with migration applied
- `SportType` enum has all seven values, registered
- `ParsedFitData` carries GPS records, RR intervals, session totals, sport type with confidence
- FIT sport extraction maps correctly: running, cycling, swimming, strength, unknown
- Power-based aerobic load for Tier 1-2 with power data; HR-based fallback for Tier 3-4
- Neuromuscular load for Tier 1-4 (variability index + VO2max time)
- Structural load with density penalty (cap 15, crossover coefficient 0.08, non-crossover 0.12)
- `gps_loss` uses continuous-gap detection (> 30s gap → true; ≤ 30s → false)
- `structural_risk_flag` uses `AthleteProfileRepository` (not raw SQL)
- Calibration eligibility gate: sport-type check first, then five rules
- Non-running activities: calibration_eligible = false, data_tier overridden to Tier 6
- `sport_type_detected` event fires with correct payload before `activity_calibration_eligible`
- `activity_calibration_eligible` event fires when eligible with load scores
- API responses include `has_gps`, `sport_type`, `sport_type_detection_version`

## Files Expected To Change

- `app/models/activity.py` — add `has_gps`, `sport_type`, `sport_type_detection_version`
- `app/models/enums.py` — add `SportType`
- `app/models/__init__.py` — register `SportType`
- `alembic/versions/<migrations>.py` — has_gps + sport_type columns + backfill
- `app/services/fit_parser_service.py` — expand `ParsedFitData` and `_parse_sync`
- `app/services/load_computation_service.py` — power/neuromuscular/structural load, `LoadComputationInputs`
- `app/services/calibration_eligibility_service.py` — sport-type gate + five-rule gate
- `app/services/activity_ingestion_service.py` — pipeline wiring, quality flags, event firing, repo injection
- `app/repositories/activity_repository.py` — add `get_recent_structural_load`
- `app/schemas/activity.py` — add `has_gps`, `sport_type`, `sport_type_detection_version`
- `app/services/__init__.py` — updated exports

## Coder Notes

- `ActivityRepository` is not registered in `app/repositories/__init__.py` — it is imported directly.
- Sport-type detection lives in `FitParserService._map_fit_sport_to_enum()` — no standalone `SportTypeDetectionService` class exists.
- Non-running activities are excluded at the calibration eligibility gate (first check), not at the ingestion boundary. Load computation still runs but returns null because `data_tier = Tier 6`.
