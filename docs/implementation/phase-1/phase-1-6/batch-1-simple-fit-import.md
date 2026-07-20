> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-6, verified against the current codebase on 2026-07-19.

## Batch Objective

Implement the complete end-to-end data flow for FIT file upload, processing, twin recalibration, and post-workout coaching message generation. This is the first time real training data flows through the system, establishing the foundational ingestion pipeline that will be expanded in Phase 2.

## Preconditions

- AthletePhysiology exists (from phase-1-3 onboarding/twin bootstrap)
- PlannedSession and GeneratedWorkout exist (from phase-1-2b)
- Object storage (MinIO) is configured
- PostgreSQL + procrastinate worker are running

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
- RawSensorStream entity creation
- ExecutionObservation or rep-level analysis
- Calibration eligibility (all sessions are `calibration_eligible = false`)
- Threshold detection or confidence level changes
- Comparable sessions functionality
- Wellness/weather modifiers on load or targets

## Steps

1. [OWNER: Coder] Create `ObjectStorageClient` service following the storage topology specification, implementing methods to store and retrieve FIT files with the pattern `fit-files/{athlete_id}/{activity_date}/{uuid}.fit`. Ensure upload failure surfaces `ObjectStorageError` without creating any database record.

2. [OWNER: Coder] Implement `FitParserService` to parse FIT files and extract HR data records (bpm per second), duration, start_time, and basic metadata. Handle common FIT file structures from Garmin, Coros, and other devices with graceful failure on unsupported formats. Raise `FitParseError` on corrupt/unparseable files.

3. [OWNER: Coder] Create `LoadComputationService` implementing the heuristic aerobic load formula from HR data using HR-reserve integration with exponential weighting (Banister TRIMP-style normalisation). For Phase 1.6: only compute `aerobic_load`; `neuromuscular_load` and `structural_load` remain null.

4. [OWNER: Coder] Implement `TwinRecalibrationService` to apply the Banister update formula to `AthleteFitness` records and create new `TwinState` snapshots with `trigger = activity_sync`. Ensure append-only behavior (never UPDATE existing TwinState).

5. [OWNER: Coder] Create `ComplianceService` to compare actual session data (duration, session type) against the linked `PlannedSession` and generate structured `ComplianceFindings` with `duration_delta_pct`, `duration_delta_descriptor`, `session_type_match`, and `session_type_descriptor`.

6. [OWNER: Coder] Implement `PostWorkoutAgent` following the three-paragraph structure specified in the vision documents, receiving pre-computed compliance findings and generating coaching messages. Ensure idempotency — calling analyse twice returns the same `CoachingMessage` without a second LLM call. Every LLM call writes a `GenerationEvent`.

7. [OWNER: Coder] Create `activity_api.py` module with the required endpoints:
   - POST `/athletes/{athlete_id}/activities/upload` — handle multipart FIT file upload, return 202 Accepted
   - GET `/athletes/{athlete_id}/activities` — list activities with pagination
   - GET `/athletes/{athlete_id}/activities/{activity_id}` — get single activity
   - POST `/athletes/{athlete_id}/activities/{activity_id}/analyse` — trigger post-workout analysis
   - GET `/athletes/{athlete_id}/activities/{activity_id}/analysis` — get analysis results

8. [OWNER: Coder] Implement `ActivityIngestionService` that orchestrates all services in the correct order: object storage upload → Activity creation → FIT parsing → load computation → twin recalibration. Events fire via `EventPublisher` (transactional outbox pattern).

9. [OWNER: Coder] Add proper error handling for FIT parsing failures, object storage failures, and service failures with appropriate HTTP status codes and retry mechanisms. See Coder Notes for specific error classes.

10. [OWNER: Coder] Generate Alembic migration for Activity schema changes.

## Context Needed

- `01-entities/activity.md` — Activity model contract
- `01-entities/twin-state.md` — TwinState append-only contract
- `01-entities/athlete-fitness.md` — AthleteFitness aggregate
- `01-entities/athlete-physiology.md` — physiology context (already exists)
- `01-entities/coaching-message.md` — CoachingMessage model
- `01-entities/generation-event.md` — GenerationEvent model
- `02-computations/load-computation.md` — heuristic formula specification
- `02-computations/banister-update.md` — Banister update formula
- `03-agents/post-workout-agent.md` — agent contract
- `04-platform/storage-topology.md` — storage layout
- `docs/vision/coach/post-workout.md` — post-workout message structure
- `docs/vision/coach/daily-view.md` — daily view constraints
- `docs/vision/twin/confidence-and-uncertainty.md` — confidence context
- `docs/vision/twin/training-zones.md` — training zones reference

## Batch Success Criteria

- Uploading a valid FIT file creates an Activity with `source = manual_upload`, non-null `fit_file_key`, and populated `aerobic_load` score
- GET `/athletes/{id}/twin/history` shows a new `TwinState` after upload with updated fitness and fatigue scores
- POST `/athletes/{id}/activities/{aid}/analyse` returns a three-paragraph post-workout coach message
- Calling the analyse endpoint twice returns the same message without a second LLM call
- Simulating object storage failure during upload does not create an Activity record
- FIT files from different devices (Garmin, Coros) are parsed successfully
- Invalid/corrupt FIT files return appropriate error responses without creating Activity records
- All LLM calls result in `GenerationEvent` records being created
- Object storage upload happens BEFORE `Activity` record creation — if upload fails, no Activity is created
- `fit_file_key` is always set for `source != manual_entry`
- `aerobic_load`, `neuromuscular_load`, `structural_load` are null at initial creation and populated by `LoadComputationService`
- `calibration_eligible` is set by `CalibrationEligibilityService` and never manually overridden. For Phase 1.6, all sessions are NOT calibration-eligible
- `TwinState` is append-only — `TwinRecalibrationService` never updates existing records
- `Activity` deduplication: `(athlete_id, external_id, source)` is unique where `external_id` is non-null

## Files Expected To Change

- `app/services/object_storage_client.py` — new object storage service
- `app/services/fit_parser_service.py` — new FIT parsing service
- `app/services/load_computation_service.py` — new load computation service
- `app/services/twin_recalibration_service.py` — new twin recalibration service
- `app/services/compliance_service.py` — new compliance service
- `app/agents/post_workout_agent.py` — new post-workout agent
- `app/services/activity_ingestion_service.py` — new ingestion orchestrator
- `app/api/v1/activity.py` — new activity routes
- `app/api/v1/__init__.py` — register activity router
- `app/models/activity.py` — Activity model
- `app/repositories/activity_repository.py` — Activity repository
- `app/worker/app.py` — `fit_ingest` task registration

## Coder Notes

- **Object storage first**: Always upload to object storage before creating any database records. `ObjectStorageFailureError` surfaces for upload failures — the ingestion pipeline must NOT create an Activity row when this surfaces.
- **HR-only processing**: Phase 1.6 only processes HR data. Ignore power, GPS, and RR interval data even if present in the FIT file.
- **Simplified load computation**: Use the heuristic formula with population norm thresholds since calibration isn't enabled yet. `BANISTER_NORMALISATION = 148.0` is the canonical reference constant.
- **No calibration eligibility**: Set `calibration_eligible = false` for all sessions in Phase 1.6, regardless of data quality.
- **Append-only TwinState**: Never update existing TwinState records. Always create new ones.
- **Idempotent analysis**: `PostWorkoutAgent.generate()` checks for existing `CoachingMessage` by `(athlete_id, activity_id, message_type=POST_WORKOUT)` before calling the LLM.
- **Three-paragraph structure**: The PostWorkoutAgent must strictly follow the vision document's three-paragraph format with no bullets, headers, or emojis.
- **Error handling**: FIT parsing should fail gracefully with descriptive errors rather than crashing.
- **Flag — missing registration**: `ActivityRepository` is NOT exported in `app/repositories/__init__.py` as of 2026-07-19. This was missed during Phase 1-6 and not caught by the original test suite.
- **Flag — stale docstring**: `run_ingestion_pipeline` docstring says it "Does NOT publish events" but the implementation DOES publish `sport_type_detected`, `activity_ingested`, and `activity_calibration_eligible`. This was updated in Phase 2 but the docstring was not fixed.
- **LLM access pattern**: `PostWorkoutAgent` creates its own `AsyncOpenAI` client directly rather than using `app.core.llm_router.get_llm()`. This predates the router pattern and should be flagged for future remediation.
