# Implementation Plan: Phase-1.6 — Simple FIT Import & Post-Workout

## Plan ID: Phase-1.6-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.6
Sub-Phase Title: Simple FIT Import & Post-Workout

## Objective
Implement the complete end-to-end data flow for FIT file upload, processing, twin recalibration, and post-workout coaching message generation. This is the first time real training data flows through the system, establishing the foundational ingestion pipeline that will be expanded in Phase 2.

## Scope
- Create `FitParserService` to extract HR data, duration, and start_time from FIT files
- Implement object storage client integration to store raw FIT files before Activity creation
- Create `LoadComputationService` with heuristic formula for aerobic_load computation from HR data
- Implement `TwinRecalibrationService` to update AthleteFitness via Banister model and create new TwinState records
- Create `ComplianceService` to compare actual session to PlannedSession
- Implement `PostWorkoutAgent` to generate three-paragraph post-workout messages
- Add POST `/athletes/{id}/activities/upload` endpoint for FIT file upload
- Add POST `/athletes/{id}/activities/{aid}/analyse` endpoint for post-workout analysis
- Add GET `/athletes/{id}/activities` and GET `/athletes/{id}/activities/{aid}` endpoints
- Add GET `/athletes/{id}/activities/{aid}/analysis` endpoint
- Ensure GenerationEvent logging for every LLM call
- Implement all required invariants and simplifications as specified in the sub-phase document

## Out Of Scope
- Power, GPS, or RR interval data processing (HR only for Phase 1.6)
- RawSensorStream entity creation (data parsed on-the-fly and discarded)
- ExecutionObservation or rep-level analysis (post-workout is compliance + effort narrative only)
- Calibration eligibility (all sessions are `calibration_eligible = false` for Phase 1.6)
- Threshold detection or confidence level changes
- Comparable sessions functionality
- Wellness/weather modifiers on load or targets

## Architecture Contracts
- `01-entities/activity.md` — IMPLEMENTS
- `01-entities/twin-state.md` — IMPLEMENTS  
- `01-entities/athlete-fitness.md` — IMPLEMENTS
- `01-entities/athlete-physiology.md` — DEPENDS ON (must exist before this plan starts)
- `01-entities/coaching-message.md` — IMPLEMENTS
- `01-entities/generation-event.md` — IMPLEMENTS
- `01-entities/generated-workout.md` — DEPENDS ON (for compliance comparison)
- `01-entities/planned-session.md` — DEPENDS ON (for compliance comparison)
- `02-computations/load-computation.md` — IMPLEMENTS (heuristic HR-only formula)
- `02-computations/banister-update.md` — IMPLEMENTS
- `03-agents/post-workout-agent.md` — IMPLEMENTS
- `04-platform/storage-topology.md` — IMPLEMENTS (object storage integration)
- `docs/vision/coach/post-workout.md` — IMPLEMENTS
- `docs/vision/coach/daily-view.md` — IMPLEMENTS
- `docs/vision/twin/confidence-and-uncertainty.md` — IMPLEMENTS
- `docs/vision/twin/training-zones.md` — IMPLEMENTS

## Invariants
- Object storage upload happens BEFORE `Activity` record creation. If upload fails, no `Activity` is created and the task retries.
- `fit_file_key` is always set for `source != manual_entry`.
- No averaged fields (`avg_hr`, `avg_pace`, etc.) are stored on `Activity`.
- `LoadComputationService` must receive raw records from `FitParserService`, not summary stats.
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService`.
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden. For Phase 1.6, all sessions are NOT calibration-eligible.
- `TwinState` is append-only. `TwinRecalibrationService` never updates the existing record.
- `PostWorkoutAgent` is idempotent — calling the endpoint twice returns the same `CoachingMessage` without calling the LLM again.
- Every LLM call writes a `GenerationEvent`.
- `Activity` deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null.

## Implementation Steps
1. [OWNER: Coder] Create `ObjectStorageClient` service following the storage topology specification, implementing methods to store and retrieve FIT files with the pattern `fit-files/{athlete_id}/{activity_date}/{uuid}.fit`.

2. [OWNER: Coder] Implement `FitParserService` to parse FIT files and extract HR data records (bpm per second), duration, start_time, and basic metadata. Handle common FIT file structures from Garmin, Coros, and other devices with graceful failure on unsupported formats.

3. [OWNER: Coder] Create `LoadComputationService` implementing the heuristic aerobic load formula from HR data using HR reserve integration with exponential weighting. For Phase 1.6, this will only compute `aerobic_load`; `neuromuscular_load` and `structural_load` remain null.

4. [OWNER: Coder] Implement `TwinRecalibrationService` to apply the Banister update formula to `AthleteFitness` records and create new `TwinState` snapshots with `trigger = activity_sync`. Ensure append-only behavior and proper inline snapshot creation.

5. [OWNER: Coder] Create `ComplianceService` to compare actual session data (duration, session type) against the linked `PlannedSession` and generate structured compliance findings.

6. [OWNER: Coder] Implement `PostWorkoutAgent` following the three-paragraph structure specified in the vision documents, receiving pre-computed compliance findings and generating coaching messages with proper null handling for Phase 1.6 limitations.

7. [OWNER: Coder] Create `activity_api.py` module with the required endpoints:
   - POST `/athletes/{athlete_id}/activities/upload` - handle multipart FIT file upload
   - GET `/athletes/{athlete_id}/activities` - list activities
   - GET `/athletes/{athlete_id}/activities/{activity_id}` - get single activity
   - POST `/athletes/{athlete_id}/activities/{activity_id}/analyse` - trigger post-workout analysis
   - GET `/athletes/{athlete_id}/activities/{activity_id}/analysis` - get analysis results

8. [OWNER: Coder] Implement the core ingestion workflow that orchestrates all services in the correct order: object storage upload → Activity creation → FIT parsing → load computation → twin recalibration → (later) post-workout analysis.

9. [OWNER: Coder] Add proper error handling for FIT parsing failures, object storage failures, and service failures with appropriate HTTP status codes and retry mechanisms.

10. [OWNER: Coder] Generate Alembic migration for any schema changes required by the new Activity fields and relationships.

11. [OWNER: DevOps] Review and augment the Alembic migration for hypertable/extension requirements if needed, then apply it to test and production databases.

12. [OWNER: Test Architect] Create comprehensive test files covering:
    - FIT file parsing with various device formats
    - Object storage integration with failure scenarios
    - Load computation with different HR patterns
    - Twin recalibration with Banister updates
    - Post-workout agent with three-paragraph output validation
    - API endpoint testing with authentication and authorization
    - Idempotency testing for analysis endpoint

## Event Contracts
- `activity_ingested` — PRODUCES
  - Payload: `{activity_id, date, duration, has_hr, has_rr, has_power, fit_file_key}`
  - Ordering: Must fire after Activity record is committed and object storage upload succeeds

- `fitness_updated` — CONSUMES (for twin recalibration)
  - Payload: `{athlete_id, aggregate_form, last_activity_id}`
  - Ordering: Must have fired before twin recalibration can occur

## Pseudocode
```
FIT file upload received
  → Store raw FIT file in object storage with key fit-files/{athlete_id}/{activity_date}/{uuid}.fit
  → If storage fails → return 500, retry mechanism
  → Create Activity record with source = manual_upload, fit_file_key = storage_key, load scores = null
  → Parse FIT file with FitParserService to extract HR records, duration, start_time
  → Compute aerobic_load using LoadComputationService with heuristic HR formula
  → Update Activity with computed load scores
  → Set calibration_eligible = false (Phase 1.6 simplification)
  → Apply Banister update to AthleteFitness via TwinRecalibrationService
  → Create new TwinState record with trigger = activity_sync and inline fitness/fatigue snapshot
  → Fire activity_ingested event

POST /analyse endpoint called
  → Check if CoachingMessage exists for this activity
  → If exists → return existing message (idempotent)
  → If not exists → 
      → Get linked PlannedSession for compliance comparison
      → Run ComplianceService to generate structured findings
      → Call PostWorkoutAgent with context including compliance findings
      → Create GenerationEvent record before LLM call
      → Generate CoachingMessage with three-paragraph structure
      → Return coaching message
```

## Testing Requirements
- Uploading a valid FIT file creates an Activity with source = manual_upload, non-null fit_file_key, and populated aerobic_load score
- GET /athletes/{id}/twin/history shows a new TwinState after upload with updated fitness and fatigue scores
- POST /athletes/{id}/activities/{aid}/analyse returns a three-paragraph post-workout coach message
- Calling the analyse endpoint twice returns the same message without a second LLM call
- Simulating object storage failure during upload does not create an Activity record
- FIT files from different devices (Garmin, Coros) are parsed successfully
- Invalid/corrupt FIT files return appropriate error responses without creating Activity records
- All LLM calls result in GenerationEvent records being created

## Coder Handoff Notes
```
## Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8, 9, 10  [OWNER: Coder] — includes migration generation
Skip:     Step 11 (DevOps — migration review and application),
          Step 12 (Test Architect — tests)
```

Key implementation considerations:
- **Object storage first**: Always upload to object storage before creating any database records. This ensures the reprocessing anchor exists.
- **HR-only processing**: Phase 1.6 only processes HR data. Ignore power, GPS, and RR interval data even if present in the FIT file.
- **Simplified load computation**: Use the heuristic formula with population norm thresholds since calibration isn't enabled yet.
- **No calibration eligibility**: Set `calibration_eligible = false` for all sessions in Phase 1.6, regardless of data quality.
- **Append-only TwinState**: Never update existing TwinState records. Always create new ones.
- **Idempotent analysis**: Cache post-workout analysis results to avoid duplicate LLM calls.
- **Three-paragraph structure**: The PostWorkoutAgent must strictly follow the vision document's three-paragraph format with no bullets, headers, or emojis.
- **Error handling**: FIT parsing should fail gracefully with descriptive errors rather than crashing on unsupported file formats.
- **File naming**: Follow existing service and API naming patterns established in the codebase (e.g., `auth_service.py`, `workout_generation_agent.py`).