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
     │           twin_confidence_upgraded  execution_analysis_completed  PhysiologicalSegments
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
     │                         (waits on execution_analysis_completed)
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
Both run concurrently. `PostWorkoutTask` is not triggered by this event — it waits for `execution_analysis_completed` instead.

**`twin_recalibrated`:**
1. `RacePredictionService.compute()` (if confidence ≥ medium)
2. Next `WorkoutGenerationAgent` call reads the new TwinState

**`twin_confidence_upgraded`:**
1. `PlanGenerationService.regenerate()` (if old plan was at LOW confidence)
2. `ProactiveMessageService.check_confidence_upgrade()`

**`twin_model_ready`:**
1. `PlanGenerationService.generate()` (creates TrainingPlan + first WeeklyPlan)
2. `FirstMessageAgent.generate()` (after plan is persisted)

**`checkpoint_completed`:**
1. `PlanGenerationService.evaluate_replan()` (if replan_triggered = true)
2. `ProactiveMessageService.check_checkpoint_result()` (athlete notification)

**`secondary_event_registered`:**
1. `PlanGenerationService.validate_and_redistribute()` (check if plan adjustment needed)
2. `RacePredictionService.update()` (recalculate race prediction)

**`secondary_event_removed`:**
1. `PlanGenerationService.validate_and_redistribute()` (check if plan adjustment needed)
2. `RacePredictionService.update()` (recalculate race prediction)

**`session_skipped` / `session_missed`:**
1. `WeeklyPlanService.update_session_status()` (update WeeklyPlan session counts)
2. Next `PreWeekReviewAgent` run reads accumulated data (NOT full plan regeneration)

**`execution_analysis_completed`:**
1. `PostWorkoutTask` (waits for this event before proceeding)

**`session_completed`:**
1. `ObjectiveUpdateService.evaluate_post_session()` (must complete first)
2. `ComparableSessionService.find()` (can run in parallel with ObjectiveUpdateService)
3. `PostWorkoutTask` (waits for both above + `execution_analysis_completed`)

**`week_completed`:**
1. `PreWeekReviewAgent` reviews next week's intent
2. `WeeklySynthesisAgent` produces next WeeklyPlan (after pre-week review)

**`pre_week_review_completed`:**
1. `WeeklySynthesisAgent` produces WeeklyPlan for the reviewed week

**`weekly_plan_created`:**
1. Daily `WorkoutGenerationAgent` reads today's session from the new WeeklyPlan
2. `PreWeekReviewAgent` (for next week, scheduled trigger)

## Ordering Constraints

```typescript
// PostWorkoutTask must wait for:
// - execution_analysis_completed event (or 2-minute timeout)
// - ObjectiveUpdateService.evaluate_post_session() to complete
// - ComparableSessionService.find() to complete
// Order guaranteed by: PostWorkoutTask receives execution_analysis_completed event
// via async pipeline; 2-minute timeout if event never arrives (degrades gracefully)

// PlanGenerationService on confidence_upgrade must:
// - Complete before the next WorkoutGenerationAgent call reads plan context
// - Order guaranteed by: plan is regenerated synchronously on confidence_upgrade event
//   before the event is considered processed

// SegmentationTask must wait for:
// - RawSensorStream to exist (SignalCleaningTask must complete first)
// - Order guaranteed by: SegmentationTask triggered by RawSensorStream creation event
```

## Plan Generation Event Flows

### Initial Plan Generation
```
twin_model_ready ──────────────────┐
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ PlanGenerationService   │
                    │ (phase definitions +   │
                    │  first WeeklyPlan       │
                    │  created)              │
                    └─────────────────────────┘
                                   │
                                   ▼
                         training_plan_generated
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                              ▼
          FirstMessageAgent              WeatherForecast prefetch
          (reads WeeklyPlan)
```

### Plan Regeneration (Confidence Upgrade)
```
twin_confidence_upgraded ──────────┐
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ PlanGenerationService   │
                    │ (re-runs hypothesis +   │
                    │  phase definitions)     │
                    └─────────────────────────┘
                                   │
                                   ▼
                         training_plan_generated
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ PreWeekReviewService    │
                    │ (evaluates next week's  │
                    │  intent — deterministic)│
                    └─────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ WeeklySynthesisAgent    │
                    │ (produces WeeklyPlan)   │
                    └─────────────────────────┘
```

### Checkpoint Replan Flow
```
session_completed ─────────────────┐
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ SessionLifecycleService │
                    └─────────────────────────┘
                                   │
                                   ▼
                         checkpoint_completed
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ PlanGenerationService   │
                    │ (evaluates replan need) │
                    └─────────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                    replan_triggered    no_replan
                          │                 │
                          ▼                 │
                 training_plan_generated    │
                          │                 │
                          ▼                 ▼
                 ProactiveMessageService   (no action)
```

### Secondary Event Flow
```
secondary_event_registered ────────┐
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ PlanGenerationService   │
                    │ (validates, redistributes)│
                    └─────────────────────────┘
                                   │
                          ┌────────┴────────┐
                          │                 │
                    redistribution    regeneration
                    possible          needed
                          │                 │
                          ▼                 ▼
                 session_redistributed   training_plan_generated
```

### Session Dropout Monitoring
```
session_skipped / session_missed ──┐
                                   │
                                   ▼
                    ┌─────────────────────────┐
                    │ PlanGenerationService   │
                    │ (monitors dropout rate) │
                    └─────────────────────────┘
                                   │
                                   ▼
                    Dropout > 20% in 3-week window?
                                   │
                          ┌────────┴────────┐
                          │                 │
                         Yes               No
                          │                 │
                          ▼                 ▼
                 training_plan_generated   (no action)
```

## Cross-References

- All events and their schemas: `00-foundations/event-catalogue.md`
- Event persistence (append-only log + transactional outbox): `04-platform/system-event.md`
- Task definitions and retry policies: `04-platform/async-pipeline.md`
- Failure handling per task type: `04-platform/failure-handling.md`

---

## Publication Mechanics

Event emission follows the transactional outbox pattern to prevent phantom state:

1. Domain service writes state change to database
2. Same transaction writes `SystemEvent` row to `system_events` and `SystemEventOutbox` row with status = 'pending'
3. Transaction commits atomically
4. Publisher (post-commit) reads pending outbox entries and publishes to Redis/message bus
5. On successful delivery, outbox row updated to status = 'published'

This ensures:
- Events are never lost due to process crash (persisted before publish)
- Consumers never see state that wasn't committed (event linked to committed transaction)
- Publication failures are retryable (outbox tracks attempts)
