# Execution Manifest — Phase-2.2-P1 — Batch 1

## Manifest Metadata
Source Plan:       docs/implementation/phase-2/phase-2-2-p1-signal-cleaning.md
Batch:             1 of 3
Manifest Version:  v1
Generated At:      2026-07-07T00:00:00Z
Source Plan Lines: 437
Manifest Lines:    152

This section is for telemetry and debugging only — it does not affect how
the coder should read or act on anything below it. If a bug is later
traced to a specific batch's implementation, this is what identifies
exactly which manifest, generated from exactly which state of the master
plan, produced it. `Manifest Version` is the schema version of this
template, not a content version — bump it only if the section structure
above changes, not per regeneration.

## Objective
Deliver the RawSensorStream model, repository, and ActivityRepository methods to persist cleaned sensor data alongside the Activity entity.

## Preconditions
No preconditions — this is the first batch.

## Steps
### Step 1 — Add the `RawSensorStream` ORM model in `app/models/raw_sensor_stream.py`.
Add the `RawSensorStream` ORM model in `app/models/raw_sensor_stream.py`. The table is `raw_sensor_streams`, append-only. Columns follow `raw-sensor-stream.md` exactly: `id` (UUID PK), `activity_id` (UUID FK → activities.id, ON DELETE CASCADE, with a UNIQUE constraint enforcing one-row-per-Activity), `fit_file_key` (the cleaned-stream object key — not raw FIT), `sampling_rate_hz` (default/stored 1.0 after resampling), `available_channels` (JSONB with keys `hr`, `rr_intervals`, `power`, `pace`, `cadence`, `elevation` — all booleans), `cleaning_pipeline_version` (non-null string), `created_at` (server-default now). Add the FK index `ix_raw_sensor_streams_activity` to support the one-to-one lookup. Do NOT add a `cleaned_at` or `updated_at` column — append-only means no mutation columns. Register the model in `app/models/__init__.py` so Alembic discovery includes it.

### Step 3 — Introduce `RawSensorStreamRepository` in `app/repositories/raw_sensor_stream_repository.py`.
Introduce `RawSensorStreamRepository` in `app/repositories/raw_sensor_stream_repository.py`. The repository exposes only: `insert(stream)` (flushes & refreshes), `get_by_activity_id(activity_id)` (the one-to-one lookup used by downstream threshold detection in Phase-2.3), and `exists_for_activity(activity_id)` (used by the cleaning task for retry idempotency — if a row already exists for the activity, the task returns success without re-doing the work). Mirror the pattern in `app/repositories/activity_repository.py`: AsyncSession injected at construction; reads via `select(...)`; no UPDATE or DELETE methods. Register it in `app/repositories/__init__.py`.

### Step 6 — Add `update_cleaning_version` to `ActivityRepository`
Add `update_cleaning_version` to `ActivityRepository` (mirroring the existing `update_load_scores` / `update_calibration_eligibility` pattern): look up by id, set `cleaning_pipeline_version`, flush, refresh, return. Document the only permitted transition as `null → non-null` (no downgrade path is exposed; re-cleaning with a new version is a future-phase concern, flagged in ADR-009 tradeoffs).

## Context Needed
### Step 1
**Primary:**    `01-entities/raw-sensor-stream.md` (TypeScript Schema + Object
              Storage Key Pattern + Invariants sections); `app/models/activity.py`
              (column style, FK pattern, JSONB default pattern to mirror)
**Secondary:**  `app/db/base.py` (Base import)
**Forbidden:**  Do not add mutation columns (`updated_at`, `cleaned_at`) — append-only
**This is everything relevant to Step 1.**

### Step 3
**Primary:**    `app/repositories/activity_repository.py` (the exact AsyncSession
              injection, flush-then-refresh, no-DELETE pattern to mirror);
              output of Step 1 (the RawSensorStream model)
**This is everything relevant to Step 3.**

### Step 6
**Primary:**    `app/repositories/activity_repository.py` → `update_load_scores`
              and `update_calibration_eligibility` (the three existing
              load-only mutations; this step adds a fourth, `update_cleaning_version`,
              following the identical pattern)
**This is everything relevant to Step 6.**

## Relevant Architecture Contracts
- `01-entities/raw-sensor-stream.md` — IMPLEMENTS (entity, key pattern `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`, append-only storage, all four invariants)
- `01-entities/activity.md` — DEPENDS ON (`cleaning_pipeline_version` field already exists; `calibration_eligible`, `sport_type`, `fit_file_key` already set by `CalibrationEligibilityService` / `FitParserService`; chain `calibration_evaluated → cleaned` state transition per the Activity state diagram)

## Relevant Invariants
- "One `RawSensorStream` per `Activity`. Created atomically with the cleaned stream upload." (`01-entities/raw-sensor-stream.md`)
- "The `fit_file_key` on `RawSensorStream` is the cleaned stream key — different from `Activity.fit_file_key` (raw FIT). The naming is intentional: both entities use the same field name pointing to different keys." (`01-entities/raw-sensor-stream.md`)
- "Cleaned data stored in object storage is immutable (append-only, never updated)" (Phase-2.2 sub-phase)
- "Activities with `source = manual_entry` never get `RawSensorStream` (no FIT file)" (Phase-2.2 sub-phase)

## Relevant Event Contracts
None. This plan does not produce or consume events in Batch 1.

## Relevant Notes
None. No notes explicitly reference entities or concepts that appear in Batch 1's Steps or Context Needed.

## Files Expected To Change
- [NEW] `app/models/raw_sensor_stream.py`
- [NEW] `app/models/__init__.py` (modification to register model)
- [NEW] `app/repositories/raw_sensor_stream_repository.py`
- [NEW] `app/repositories/__init__.py` (modification to register repository)
- [EXISTING] `app/repositories/activity_repository.py`

## Batch Success Criteria
Batch 1 complete when:
- `app/models/raw_sensor_stream.py` exists, the `RawSensorStream` class is
  registered in `app/models/__init__.py`, and the table name is
  `raw_sensor_streams` with `activity_id` UNIQUE + FK + index
  `ix_raw_sensor_streams_activity`.
- `app/repositories/raw_sensor_stream_repository.py` exists with exactly
  `insert`, `get_by_activity_id`, `exists_for_activity` — no UPDATE/DELETE —
  and is registered in `app/repositories/__init__.py`.
- `ActivityRepository.update_cleaning_version(activity_id, version)` exists
  and sets `cleaning_pipeline_version` on the loaded row.