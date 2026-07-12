# Execution Manifest — Phase-2.3-P1 — Batch 1

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-3-p1-threshold-detection.md
Batch:             1 of 4
Manifest Version:  v1
Generated At:      2026-07-10T00:00:00Z
Source Plan Lines: 598
Manifest Lines:    134

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Implement the `PhysiologyMeasurement` model, `PhysiologyParameter` enum,
Alembic migration, and `PhysiologyMeasurementRepository` to establish the
data layer for threshold detection observations.

## Preconditions
No preconditions — this is the first batch.

## Steps
### Step 1 — Add `PhysiologyParameter` enum to `app/models/enums.py`
[OWNER: Coder] Add `PhysiologyParameter` enum to `app/models/enums.py` with
values: `LT1_HR`, `LT1_POWER`, `LT1_PACE`, `LT2_HR`, `LT2_POWER`,
`LT2_PACE`, `CP`, `VO2MAX_ML_KG_MIN`, `VO2MAX_POWER`, `MAX_HR`. Follow the
existing `str, Enum` pattern used by `MeasurementSource`. Register the enum
in `app/models/__init__.py` imports.

### Step 2 — Create `PhysiologyMeasurement` model
[OWNER: Coder] Create `PhysiologyMeasurement` model in
`app/models/physiology_measurement.py`. Append-only table
`physiology_measurements` with columns: `id` (UUID PK), `athlete_id`
(FK → athletes, CASCADE), `activity_id` (FK → activities, SET NULL — null
for lab/field test measurements), `parameter` (PhysiologyParameter enum,
non-native String), `observed_value` (Float, non-null), `source`
(MeasurementSource enum, non-native String), `measurement_date` (Date,
non-null), `algorithm_used` (String(64), nullable — null for manual
entries), `confidence_weight` (Float, nullable — algorithm-specific
confidence 0.0–1.0), `raw_data_reference` (String(512), nullable),
`notes` (Text, nullable), `created_at` (DateTime, server_default=now()).
Indexes: `(athlete_id, measurement_date DESC)` for history queries,
`(athlete_id, parameter, source)` for dedup lookup. No UPDATE/DELETE
methods on the model. Register in `app/models/__init__.py`.

### Step 3 — Generate Alembic migration
[OWNER: Coder] Generate Alembic migration for the
`physiology_measurements` table. The migration creates the table with all
columns and indexes from Step 2. Follow the existing migration naming
convention (`phase_2_3_p1_physics_measurement.py`).

### Step 4 — Create `PhysiologyMeasurementRepository`
[OWNER: Coder] Create `PhysiologyMeasurementRepository` in
`app/repositories/physiology_measurement_repository.py`. Expose:
`insert(measurement)` (flush, no commit), `get_by_athlete(athlete_id,
limit)` (newest first), `get_by_athlete_and_parameter(athlete_id,
parameter, limit)`, `get_recent_for_parameter(athlete_id, parameter,
source, from_date, limit)` (for dedup detection and natural training
analysis queries). No update/delete methods. Register in
`app/repositories/__init__.py`.

## Context Needed
Step 1:
  Primary:    `app/models/enums.py` (existing enum pattern — `MeasurementSource`
              is the closest model)
  Secondary:  `app/models/__init__.py` (registration pattern)
  Fallback:   —
  Forbidden:  —
Step 2:
  Primary:    `app/models/athlete_physiology.py` (FK target, JSONB shape
              reference), `app/models/raw_sensor_stream.py` (append-only model
              pattern with UniqueConstraint)
  Secondary:  `app/models/enums.py` (MeasurementSource enum for source column)
  Fallback:   —
  Forbidden:  —
Step 3:
  Primary:    output of Step 2 (model definition), existing migration
              `alembic/versions/297ea8ac7f69_phase_2_2_p1_batch_1_raw_sensor_streams.py`
              (migration naming and structure pattern)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 4:
  Primary:    `app/repositories/raw_sensor_stream_repository.py` (repository
              pattern — insert + flush, no commit), output of Step 2
  Secondary:  `app/repositories/__init__.py` (registration pattern)
  Fallback:   —
  Forbidden:  —

## Relevant Architecture Contracts
- `01-entities/athlete-physiology.md` — DEPENDS ON (PhysiologyMeasurement
  append-only table, MeasurementSource enum, PhysiologyParameterState shape)
- `01-entities/raw-sensor-stream.md` — DEPENDS ON (RawSensorStream row provides
  the cleaned-stream object key)

## Relevant Invariants
- "`PhysiologyMeasurement` is append-only" (athlete-physiology storage model)

## Relevant Event Contracts
This plan does not produce or consume events.

## Relevant Notes
This plan does not produce or consume events. `ThresholdDetectionService`
produces `ThresholdObservation` data structures consumed by
`PhysiologyUpdateService` (Plan P2). No events are fired at this layer.

## Files Expected To Change
- [NEW] app/models/enums.py
- [EXISTING] app/models/__init__.py
- [NEW] app/models/physiology_measurement.py
- [NEW] alembic/versions/phase_2_3_p1_physiology_measurements.py
- [NEW] app/repositories/physiology_measurement_repository.py
- [EXISTING] app/repositories/__init__.py

## Batch Success Criteria
Batch 1 complete when:
- `PhysiologyParameter` enum exists in `app/models/enums.py` with all 10
  values and is imported in `app/models/__init__.py`
- `PhysiologyMeasurement` model exists in
  `app/models/physiology_measurement.py` with all specified columns and
  indexes, registered in `app/models/__init__.py`
- Alembic migration file exists and creates the `physiology_measurements`
  table
- `PhysiologyMeasurementRepository` exists in
  `app/repositories/physiology_measurement_repository.py` with `insert`,
  `get_by_athlete`, `get_by_athlete_and_parameter`,
  `get_recent_for_parameter` methods, registered in
  `app/repositories/__init__.py`
- No update/delete methods exist on the repository