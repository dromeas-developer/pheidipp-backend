> **Baseline — migrated from** `docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md` **on** 2026-07-19.
> This plan was implemented before the BRD format was introduced.
> It documents what was built, verified against the current codebase
> on 2026-07-19. See `## Coder Notes` for any gaps found during migration.

## Batch Objective

Implement the `ThresholdDetectionService` — the computation engine that analyses cleaned sensor streams from calibration-eligible running activities and produces physiological threshold observations (LT1 HR, LT2 HR, CP). This plan also introduces the `PhysiologyMeasurement` model and `PhysiologyParameter` enum that the observation history depends on.

## Preconditions

No preconditions — this is the first plan in sub-phase 2-3. Plans P2 (PhysiologyUpdateService) and P3 (TwinRecalibrationService extension + pipeline integration) depend on the components built here.

## Scope

- `PhysiologyParameter` enum (lt1_hr, lt1_power, lt1_pace, lt2_hr, lt2_power, lt2_pace, cp, vo2max_ml_kg_min, vo2max_power, max_hr)
- `PhysiologyMeasurement` model — append-only observation history table
- `PhysiologyMeasurementRepository` — insert and range/parameter queries
- Alembic migration for the `physiology_measurements` table
- `ThresholdDetectionService` implementing three detection algorithms: HR deflection, HRV/RR inflection, Power-to-HR ratio
- LT1 passive inference methods: natural training analysis, HR drift, HR recovery
- Signal selection logic (which algorithm applies based on available signals)
- `ThresholdObservation` dataclass
- Reading cleaned streams from object storage via `RawSensorStreamRepository` and `ObjectStorageClient`

## Steps

1. [OWNER: Coder] Add `PhysiologyParameter` enum to `app/models/enums.py` with values: `LT1_HR`, `LT1_POWER`, `LT1_PACE`, `LT2_HR`, `LT2_POWER`, `LT2_PACE`, `CP`, `VO2MAX_ML_KG_MIN`, `VO2MAX_POWER`, `MAX_HR`. Follow the existing `str, Enum` pattern used by `MeasurementSource`. Register the enum in `app/models/__init__.py` imports.

2. [OWNER: Coder] Create `PhysiologyMeasurement` model in `app/models/physiology_measurement.py`. Append-only table `physiology_measurements` with columns: `id` (UUID PK), `athlete_id` (FK → athletes, CASCADE), `activity_id` (FK → activities, SET NULL — null for lab/field test measurements), `parameter` (PhysiologyParameter enum, non-native String), `observed_value` (Float, non-null), `source` (MeasurementSource enum, non-native String), `measurement_date` (Date, non-null), `algorithm_used` (String(64), nullable), `confidence_weight` (Float, nullable), `raw_data_reference` (String(512), nullable), `notes` (Text, nullable), `created_at` (DateTime, server_default=now()). Indexes: `(athlete_id, measurement_date DESC)`, `(athlete_id, parameter, source)`. No UPDATE/DELETE methods on the model. Register in `app/models/__init__.py`.

3. [OWNER: Coder] Generate Alembic migration for the `physiology_measurements` table. Follow existing migration naming convention.

4. [OWNER: Coder] Create `PhysiologyMeasurementRepository` in `app/repositories/physiology_measurement_repository.py`. Expose: `insert(measurement)` (flush, no commit), `get_by_athlete(athlete_id, limit)`, `get_by_athlete_and_parameter(athlete_id, parameter, limit)`, `get_recent_for_parameter(athlete_id, parameter, source, from_date, limit)`. No update/delete methods. Register in `app/repositories/__init__.py`.

5. [OWNER: Coder] Create `ThresholdObservation` dataclass in `app/services/threshold_detection_service.py`. Fields: `parameter` (PhysiologyParameter), `observed_value` (float), `source` (MeasurementSource), `weight` (float), `activity_id` (UUID), `measurement_date` (date), `algorithm_used` (str), `confidence_weight` (float | None).

6. [OWNER: Coder] Implement `ThresholdDetectionService` in `app/services/threshold_detection_service.py`. The primary entry point `async def detect(self, athlete_id, activity_id) -> list[ThresholdObservation]` performs: load Activity, verify `calibration_eligible = true` and `sport_type = RUNNING`, load `RawSensorStream`, download cleaned stream from object storage, run signal selection, execute applicable algorithms, return observations. The service does NOT write to `PhysiologyMeasurement` — that is `PhysiologyUpdateService`'s responsibility (Plan P2).

7. [OWNER: Coder] Implement the HR deflection algorithm (Algorithm 1). Segment cleaned stream into intensity bins using GAP or power. Fit linear HR-intensity regression. LT1: first departure from linearity. LT2: second, steeper departure. Require ≥3 distinct intensity steps and R² ≥ 0.80. Produce `LT1_HR` and `LT2_HR` observations with source `TRAINING_HR_DEFLECTION` and weight 1.0.

8. [OWNER: Coder] Implement the HRV/RR inflection algorithm (Algorithm 2). Compute RMSSD in 60-second rolling windows. Detect LT1: first significant RMSSD drop (>15% below baseline). LT2: second inflection. Require ≥8 minutes per intensity level. Produce `LT1_HR` and `LT2_HR` observations with source `TRAINING_RR_INFLECTION` and weight 2.5.

9. [OWNER: Coder] Implement the power-to-HR ratio algorithm (Algorithm 3). Detect ratio breakpoint where power/HR ratio begins sustained decline. Only runs when `has_power = true`. Produce `CP` observation with source `TRAINING_POWER_HR_RATIO` and weight 1.5.

10. [OWNER: Coder] Implement signal selection logic: if has_rr_intervals → run RR inflection; if has_hr + has_power → run HR deflection + power-to-HR ratio; if has_hr only → run HR deflection. RR inflection takes priority over HR deflection when both available.

11. [OWNER: Coder] Implement LT1 passive inference methods: Natural Training Analysis (cross-session, ≥3 easy runs with consistent HR ±5 bpm, weight 0.5), HR Drift (per-session, steady-state ≥20 min, weight 1.0), HR Recovery (per-session, hard effort + ≥2 min recovery, weight 0.5).

## Context Needed

Step 1:
- Primary: `app/models/enums.py` (existing enum pattern), `app/models/__init__.py` (registration pattern)

Step 2:
- Primary: `app/models/athlete_physiology.py` (FK target), `app/models/raw_sensor_stream.py` (append-only model pattern)

Step 3:
- Primary: output of Step 2, existing Alembic migration pattern

Step 4:
- Primary: `app/repositories/raw_sensor_stream_repository.py` (repository pattern), output of Step 2

Step 5:
- Primary: `app/services/signal_cleaning_service.py` (`CleanedRecord`, `CleanedStream` dataclasses)

Step 6:
- Primary: `app/services/signal_cleaning_service.py`, `app/repositories/raw_sensor_stream_repository.py`, `app/repositories/activity_repository.py`, `app/services/object_storage_client.py`

Step 7-9:
- Primary: `docs/architecture/02-computations/threshold-detection.md`

Step 10:
- Primary: `docs/architecture/02-computations/threshold-detection.md` (Signal Selection section)

Step 11:
- Primary: `docs/architecture/02-computations/lt1-detection.md`, `app/repositories/activity_repository.py`, `app/repositories/planned_session_repository.py`

## Batch Success Criteria

Batch 1 (Steps 1-4) — Model Foundation:
- `PhysiologyParameter` enum exists with all 10 values
- `PhysiologyMeasurement` model exists with all specified columns, indexes, no update/delete
- Alembic migration creates `physiology_measurements` table
- `PhysiologyMeasurementRepository` exists with insert + read methods, no update/delete

Batch 2 (Steps 5, 6, 10) — Service Skeleton:
- `ThresholdObservation` dataclass exists
- `ThresholdDetectionService` constructed with all dependencies
- `detect()` returns `list[ThresholdObservation]`
- Signal selection routes correctly based on available signals
- Calibration eligibility and sport type gates return empty list
- Missing `RawSensorStream` returns empty list

Batch 3 (Steps 7, 8, 9) — Detection Algorithms:
- HR deflection produces correct observations when ≥3 steps and R² ≥ 0.80
- RR inflection produces correct observations when RR data and ≥8 min/level
- Power-to-HR ratio produces CP observation when clear breakpoint

Batch 4 (Step 11) — Passive Inference:
- Natural training analysis produces LT1_HR with weight 0.5 when ≥3 consistent easy runs
- HR drift identifies steady-state segments ≥20 min
- HR recovery produces LT1_HR observation when hard effort + ≥2 min recovery

## Files Expected To Change

- `app/models/enums.py` — new `PhysiologyParameter` enum
- `app/models/physiology_measurement.py` — new model
- `app/models/__init__.py` — register model and enum
- `alembic/versions/<migration>.py` — new migration
- `app/repositories/physiology_measurement_repository.py` — new repository
- `app/repositories/__init__.py` — register repository
- `app/services/threshold_detection_service.py` — new service with `ThresholdObservation` dataclass and all algorithms

## Coder Notes

- Verified against current codebase (2026-07-19): all entities, services, repositories, and tests exist. No discrepancies.
- Test coverage: 126 tests across 7 files (unit, integration, behaviour) — all passing.
- The plan references `phase_2_3_p1_physics_measurement.py` for the migration name; the actual migration is `8413e6547a40_phase_2_3_p1_physiology_measurement.py`.
