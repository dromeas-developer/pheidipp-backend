# Event Topology — Event Routing and Pipeline Wiring

## Purpose
- Defines how events flow between producers and consumers
- The authoritative wiring diagram for the async pipeline

## Event Flow Diagram

```
Athlete Action
    │
    ▼
API Layer (FastAPI)
    │
    ├── POST /activities/upload ──────────────────► FitIngestionTask
    │                                                    │
    │                                          ┌─────────┴──────────┐
    │                                          ▼                    ▼
    │                               activity_ingested    fit_file stored
    │                                          │
    │                               ┌──────────┴──────────┐
    │                               ▼                     ▼
    │                    activity_calibration_eligible  SignalCleaningTask
    │                               │                     │
    │                    ┌──────────┴──────────┐         ▼
    │                    ▼                     ▼    RawSensorStream created
    │          TwinRecalibrationTask  ExecutionAnalysisTask    │
    │                    │                     │         ▼
    │                    ▼                     │   SegmentationTask
    │             twin_recalibrated            │         │
    │                    │                     ▼         ▼
    │           twin_confidence_upgraded  ExecutionObservation  PhysiologicalSegments
    │                    │                     │
    │           ┌─────────┴──────────┐         │
    │           ▼                    ▼         │
    │   PlanGenerationService  ProactiveMsg    │
    │                               │         │
    │                               ▼         ▼
    │                        session_completed event
    │                               │
    │                    ┌──────────┴──────────┐
    │                    ▼                     ▼
    │          ObjectiveUpdateService  ComparableSessionService
    │                    │                     │
    │                    └──────────┬──────────┘
    │                               ▼
    │                        PostWorkoutTask
    │                               │
    │                               ▼
    │                        CoachingMessage created
    │
    ├── POST /onboarding ──────────────────────► onboarding_completed
    │                                                    │
    │                                          ┌─────────┴──────────┐
    │                                          ▼                    ▼
    │                               PlanGenerationService  FirstMessageAgent
    │
    ├── POST /cycle ───────────────────────────► cycle_day_one_logged
    │                                                    │
    │                                                    ▼
    │                                          CyclePersonalisationTask
    │                                          (if ≥3 complete cycles)
    │
    └── POST /sessions/{id}/skip ─────────────► session_skipped
                                                         │
                                                         ▼
                                                SkipConversationAgent
```

## Scheduled Event Triggers

```typescript
const SCHEDULED_TASKS = [
  { task: 'IntervalsIcuSyncTask',         cron: '0 */4 * * *' },      // every 4h
  { task: 'IntervalsIcuWellnessSyncTask', cron: '0 3 * * *' },        // 03:00 UTC daily
  { task: 'BaselineComputationTask',      cron: '0 1 * * *' },        // 01:00 UTC daily
  { task: 'MissedSessionSweepTask',       cron: '0 6 * * *' },        // 06:00 UTC daily
  { task: 'WorkoutPrefetchTask',          cron: '0 */1 * * *' },      // hourly; filter by window
  { task: 'AdaptationBlockDetectionTask', cron: '0 2 * * *' },        // 02:00 UTC daily
  { task: 'LibraryPromotionTask',         cron: '0 4 * * *' },        // 04:00 UTC daily
  { task: 'ProactiveMessageCheck',        cron: '0 7 * * *' },        // 07:00 UTC daily
]
```

## Event Consumer Fanout

Events that trigger multiple consumers:

**`activity_calibration_eligible`:**
1. `TwinRecalibrationTask` (parallel)
2. `ExecutionAnalysisTask` (parallel)
Both run concurrently. `PostWorkoutTask` waits for both to complete.

**`twin_recalibrated`:**
1. `RacePredictionService.compute()` (if confidence ≥ medium)
2. Next `WorkoutGenerationAgent` call reads the new TwinState

**`twin_confidence_upgraded`:**
1. `PlanGenerationService.regenerate()` (if old plan was at LOW confidence)
2. `ProactiveMessageService.check_confidence_upgrade()`

**`session_completed`:**
1. `ObjectiveUpdateService.evaluate_post_session()` (must complete first)
2. `ComparableSessionService.find()` (can run in parallel with ObjectiveUpdateService)
3. `PostWorkoutTask` (waits for both above)

## Ordering Constraints

```typescript
// PostWorkoutTask must wait for:
// - ExecutionObservation to exist (or 3 retries exhausted)
// - ObjectiveUpdateService.evaluate_post_session() to complete
// - ComparableSessionService.find() to complete
// Order guaranteed by: PostWorkoutTask polls for ExecutionObservation existence
// with 5s intervals, up to 60s total wait

// PlanGenerationService on confidence_upgrade must:
// - Complete before the next WorkoutGenerationAgent call reads plan context
// - Order guaranteed by: plan is regenerated synchronously on confidence_upgrade event
//   before the event is considered processed

// SegmentationTask must wait for:
// - RawSensorStream to exist (SignalCleaningTask must complete first)
// - Order guaranteed by: SegmentationTask triggered by RawSensorStream creation event
```

## Cross-References
- All events and their schemas: `00-foundations/event-catalogue.md`
- Task definitions and retry policies: `04-platform/async-pipeline.md`
- Failure handling per task type: `04-platform/failure-handling.md`
