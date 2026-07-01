# Async Pipeline — Worker Queue Architecture

## Purpose
- Defines the worker queue topology, task definitions, and execution guarantees
- All heavy processing runs async — API responses never wait for analysis

## Infrastructure

```typescript
// Queue backend: PostgreSQL (via procrastinate 2.x)
// Worker framework: Procrastinate (async Python)
// Connector: Psycopg2Connector (sync-compatible, built on psycopg2)
// Version constraint: procrastinate>=2.0,<3.0
//   - Procrastinate 2.x and 3.x both use connector-based API (keyword-only constructor).
//   - Pinned to 2.x to use Psycopg2Connector (psycopg2-based) rather than 3.x's PsycopgConnector (psycopg3-based).
//   - Worker tasks run in separate process; sync connector acceptable for current scale.
// Migration path: Redis/Celery is planned replacement if queue contention appears
// Task visibility: task_id returned from async-triggering API endpoints (202 Accepted)
```

## Task Inventory

### Ingestion Tasks

**`FitIngestionTask`**
Trigger: FIT file uploaded or sync batch item received
Steps: parse → upload to object storage → create Activity → compute load → evaluate calibration → if eligible: enqueue TwinRecalibrationTask → clean signal → store RawSensorStream → enqueue SegmentationTask
Idempotent: yes (deduplicated by `external_id`)
Retry: up to 5 times with exponential backoff
Timeout: 120s

**Note on signal cleaning dependency:** `TwinRecalibrationTask` is enqueued BEFORE signal cleaning completes. `ThresholdDetectionService` within that task uses raw HR data for HR deflection algorithms (Tiers 2–4). For RR inflection detection (Tiers 1–3), the task waits for `RawSensorStream` to be available. If `RawSensorStream` is not yet stored, RR inflection is skipped for that session — the HR deflection result is still applied.

**`IntervalsIcuSyncTask`**
Trigger: scheduled (every 4h) + on-demand
Steps: for each connected athlete → fetch new activities since cursor → enqueue FitIngestionTask per activity → update sync cursor
Retry: up to 3 times
Timeout: 300s

**`IntervalsIcuWellnessSyncTask`**
Trigger: scheduled (daily 03:00 UTC)
Steps: for each connected athlete → fetch wellness since cursor → upsert AthleteWellness records
Retry: up to 3 times
Timeout: 120s

### Analysis Tasks

**`TwinRecalibrationTask`**
Trigger: `activity_calibration_eligible` event
Steps: run ThresholdDetectionService → run BayesianUpdate → insert new TwinState → if confidence upgraded: fire `twin_confidence_upgraded` event
Idempotent: yes (TwinState insert is append-only; duplicate triggers create duplicate records but are benign)
Retry: up to 3 times
Timeout: 30s

**`SignalCleaningTask`**
Trigger: after Activity created with `fit_file_key`
Steps: run 7-step cleaning pipeline → upload cleaned stream → create RawSensorStream → update Activity.cleaning_pipeline_version
Retry: up to 3 times
Timeout: 60s

**`SegmentationTask`**
Trigger: after RawSensorStream created
Steps: create PlannedSegments from WorkoutSteps → create DeviceSegments from FIT laps → run segmentation pipeline → create PhysiologicalSegments
Retry: up to 3 times
Timeout: 120s

**`ExecutionAnalysisTask`**
Trigger: `activity_calibration_eligible` event (parallel with TwinRecalibrationTask)
Steps: fetch FIT from object storage → run ExecutionAnalysisService → create ExecutionObservation
Retry: up to 3 times; if FIT fetch fails all 3 times → alert
Timeout: 30s

### Coaching Tasks

**`PostWorkoutTask`**
Trigger: `session_completed` event
Steps: wait for `execution_analysis_completed` event → run ObjectiveUpdateService → run ComparableSessionService → assemble context → call PostWorkoutAgent → write CoachingMessage
Dependencies: ExecutionAnalysisTask must complete first. PostWorkoutTask waits for `execution_analysis_completed` event with a 2-minute timeout. If timeout expires, the task proceeds without ExecutionObservation (agent uses compliance-only context).
Retry: up to 2 times (LLM calls are not idempotent; limited retries)
Timeout: 60s

**`WorkoutPrefetchTask`**
Trigger: scheduled (18h before each athlete's training window start in athlete local time)
Steps: for each athlete with a pending session tomorrow (athlete local date) → fetch weather (for athlete local date) → run WorkoutGenerationAgent → store GeneratedWorkout
Retry: up to 2 times
Timeout: 30s per athlete

### Maintenance Tasks

**`BaselineComputationTask`**
Trigger: scheduled (nightly 01:00 UTC)
Steps: for each athlete with new wellness data in past 24h → compute baselines → upsert AthleteWellnessBaseline records
Timeout: 2h batch window
Retry: per-athlete; failed athletes skipped and retried next night

**`MissedSessionSweepTask`**
Trigger: scheduled (daily 06:00 UTC)
Steps:
  - For each athlete with `generated` sessions:
    - Compute athlete's current local date: `now().setZone(athlete.timezone).toISODate()`
    - Transition sessions where `target_date < athlete_local_date` to `missed`
  - Create wellness_alert CoachingMessage for affected athletes
Timeout: 60s batch

**`GapCurveFittingTask`**
Trigger: after FitIngestionTask when athlete reaches 20+ outdoor sessions
Steps: run GapCurveFittingService → if R²≥0.70: update AthleteProfile.gap_curve_model
Retry: up to 2 times
Timeout: 60s

**`CyclePersonalisationTask`**
Trigger: `cycle_day_one_logged` when ≥3 complete cycles exist
Steps: run CyclePersonalisationService → update AthleteProfile.cycle_personal_model
Timeout: 10s

**`AdaptationBlockDetectionTask`**
Trigger: scheduled (nightly)
Steps: identify completed hard blocks → run AdaptationObservationService for each
Timeout: 60s per athlete batch

**`LibraryPromotionTask`**
Trigger: scheduled (nightly)
Steps: find GeneratedWorkout entries with times_offered≥3 and acceptance_rate≥0.6 → promote to WorkoutLibraryEntry
Timeout: 30s

## Execution Guarantees

```typescript
// At-least-once delivery: tasks may execute more than once
// All tasks must be idempotent or have idempotency checks
// Dead-letter queue: failed jobs tracked in procrastinate failure log; mirrored to system_event_outbox for alerting

// Task visibility for athlete-facing operations:
// FIT upload → 202 Accepted + task_id
// POST /athletes/{id}/activities/upload → { task_id: "uuid" }
// GET /tasks/{task_id} → { status: "pending"|"running"|"completed"|"failed", result_url?: string }
```

## Cross-References
- FitIngestionTask full pipeline: `01-entities/activity.md`
- Segmentation pipeline: `02-computations/signal-cleaning.md`
- TwinRecalibration: `01-entities/twin-state.md`
- Event topology (how tasks are triggered): `04-platform/event-topology.md`
- Failure handling: `04-platform/failure-handling.md`
