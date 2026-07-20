> **Baseline — test companion for** `batch-1-simple-fit-import.md`, migrated from `docs/implementation/phase-1/phase-1-6-p1-simple-fit-import.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements and verified against existing test files in the codebase.

### Object Storage
- Given a valid FIT file upload, the file is stored in MinIO with key `fit-files/{athlete_id}/{activity_date}/{uuid}.fit`
- Given object storage is unreachable during upload, the endpoint returns 5xx and NO Activity record is created in the database
- Given an existing file at the same key, `ObjectStorageConflictError` is raised

### FIT Parsing
- Given a valid Garmin FIT file with HR records, `FitParserService.parse()` returns `ParsedFitData` with correct `start_time`, `duration_seconds`, and `hr_records`
- Given a valid Coros FIT file with HR records, parsing succeeds with correct HR data
- Given a corrupt or unparseable FIT file, `FitParseError` is raised and no Activity is created
- Given a FIT file with zero HR records, `FitParseEmptyError` or equivalent is raised

### Load Computation
- Given HR records at steady-state LT1 (HRR% ≈ 0.85) for 1 hour, `compute_aerobic_load()` returns ~100 units (Banister normalisation reference)
- Given zero HR records input, `MissingHeartRateError` is raised
- Given HR records with `max_hr_estimate = 200` and `resting_hr = 60`, load scores scale correctly
- Given `DataTier.TIER_4` (no profile), population-norm thresholds are used for `max_hr_estimate` fallback
- Given Phase 1.6 constraints, `neuromuscular_load` and `structural_load` remain null

### Twin Recalibration
- Given a new athlete with zero prior fitness, applying Banister update with `aerobic_load = 50` produces `fitness > 0` and `fatigue > 0`
- Given zero load on first update, both fitness and fatigue decay to 0
- Given every recalibration, a new `TwinState` is created with `trigger = activity_sync`
- Given existing `TwinState` records, NONE are mutated — all are append-only
- Given missing `AthleteFitness` row, `MissingAthleteFitnessError` is raised
- Given missing `TrainingGoal`, `MissingTrainingGoalError` is raised

### Compliance Service
- Given a planned session of 60 minutes and actual duration of 60 minutes, `duration_delta_pct ≈ 0.0`
- Given a planned session of 60 minutes and actual duration of 30 minutes, `duration_delta_pct = -50.0` and descriptor indicates shorter session
- Given a planned session of 60 minutes and actual duration of 75 minutes, `duration_delta_pct = 25.0` and descriptor indicates longer session
- Given no linked `PlannedSession` (planned_session_id is null), `has_prescribed_session = False` and descriptor is neutral
- Given `source = manual_entry` and prescribed rest, `session_type_match = True`

### Post-Workout Agent
- Given a POST to `/activities/{aid}/analyse` for an activity without an existing message, a new `CoachingMessage` is created and a `GenerationEvent` is written
- Given a POST to `/activities/{aid}/analyse` for the SAME activity again, the EXISTING `CoachingMessage` is returned and NO new LLM call is made (idempotency)
- Given the LLM returns a single-paragraph response, `PostWorkoutContractError` is raised (three-paragraph validation)
- Given `aerobic_load = null`, `describe_load()` returns "no load recorded"
- Given `aerobic_load = 15`, `describe_load()` returns "light aerobic load"
- Given `aerobic_load = 45`, `describe_load()` returns "moderate aerobic load"
- Given `aerobic_load = 80`, `describe_load()` returns "steady aerobic load"
- Given `aerobic_load = 150`, `describe_load()` returns "heavy aerobic load"
- Given no linked planned session, `format_phase_position()` returns "early in the current training block"
- Given a planned session in week 3 of threshold build, `format_phase_position()` returns "week 3 of the threshold build phase"

### API Endpoints
- Given `POST /athletes/{id}/activities/upload` with valid FIT file, returns 202 with `activity_id` and `task_id`
- Given `GET /athletes/{id}/activities`, returns paginated activity list with correct `total` count
- Given `GET /athletes/{id}/activities/{aid}`, returns the activity or 404
- Given `POST /athletes/{id}/activities/{aid}/analyse`, returns `PostWorkoutAnalysisResponse` with message content
- Given `GET /athletes/{id}/activities/{aid}/analysis`, returns existing analysis or 404
- Given `GET /athletes/{id}/activities/{aid}` for a non-existent activity, returns 404

### Storage + DB Invariants
- Given `Activity` with `source != manual_entry`, `fit_file_key` is always non-null
- Given `Activity` at initial creation (before `LoadComputationService`), `aerobic_load`, `neuromuscular_load`, `structural_load` are all null
- Given any Phase 1.6 ingestion, `calibration_eligible = false`
- Given two activities with the same `(athlete_id, external_id, source)`, a uniqueness violation occurs
- Given activity with `external_id = null`, the uniqueness constraint does not apply

### No Regressions
- Given no new Alembic migration is pending (`alembic check` passes — existing migration covers all schema changes)
