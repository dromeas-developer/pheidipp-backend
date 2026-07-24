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
                    ▼                           ▼
          FirstMessageAgent              WeatherForecast prefetch
          (reads WeeklyPlan)
                    │
                    ▼
        coaching_message_generated
```

**Producer:** `OnboardingService` (fires `twin_model_ready` after bootstrap TwinState insert)

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
4. Publisher (post-commit) reads pending outbox entries and transitions their status to 'published' (no external bus in the current implementation; see `system-event.md` for the publication state machine and the future bus insertion point)
5. On successful delivery, outbox row updated to status = 'published'

This ensures:
- Events are never lost due to process crash (persisted before publish)
- Consumers never see state that wasn't committed (event linked to committed transaction)
- Publication failures are retryable (outbox tracks attempts)

## Event Firing Timing Clarification

The codebase uses two different labels to describe when `EventPublisher.publish()` is called relative to a transaction commit. Both describe the same transactional outbox pattern; the difference is only in *who* commits the producing transaction and *who* performs the publication status transition.

### `[after_commit]` — the service owns the commit

Used by synchronous domain services that manage their own `AsyncSession` and call `await session.commit()` themselves, such as `AuthService`, `OnboardingService`, and `PlanGenerationService`.

In this pattern:

1. The service writes domain state and writes the matching `SystemEvent` + `SystemEventOutbox` rows inside one transaction.
2. The service calls `await session.commit()`.
3. The platform publisher worker (a separate process) reads the pending outbox rows and transitions their status to 'published'. No external message bus is in the path today; the publisher task is the documented insertion point for a future bus (see `system-event.md`).

The event is therefore *observed* by consumers only after the producing transaction has committed, even though the outbox write happened before `commit()` returned.

### `[uncommitted]` — the caller (or worker) owns the commit

Used by asynchronous workers where the service does not commit, such as `ActivityIngestionService` when invoked from the `fit_ingest` procrastinate task, and by agent services such as `FirstMessageAgent`, `WorkoutGenerationAgent`, and `PostWorkoutAgent`.

In this pattern:

1. The service writes domain state and writes the matching `SystemEvent` + `SystemEventOutbox` rows inside the transaction that the worker opened.
2. The service returns; the worker calls `commit()`.
3. The platform publisher worker reads the pending outbox rows and transitions their status to 'published'. No external message bus is in the path today; the publisher task is the documented insertion point for a future bus (see `system-event.md`).

Because the external publish happens in a separate process, the service method itself "fires" the event before its transaction is committed. The label `[uncommitted]` marks the fact that the service method does not close the transaction; it does *not* mean the event is published before the transaction commits.

### Both patterns preserve the same invariant

- **Consumers never see uncommitted state.** In both cases, the status transition to 'published' is performed by the platform publisher worker after the database transaction that wrote the outbox row has committed; no external message bus is required for this guarantee.
- **Events are never lost.** The outbox row is written in the same database transaction as the domain state, so a rollback of the domain transaction also rolls back the outbox row.
- **No phantom reads.** Because publication is driven by the outbox table and not by an in-process callback, a crashed producer cannot leave consumers with an event whose state was never committed.

The apparent inconsistency between `[after_commit]` and `[uncommitted]` is a labeling artifact. It reflects who owns the calling transaction (the service vs. the worker/agent), not a difference in the transactional outbox semantics.

See also:
- [ADR-004: Transactional Outbox for Event Persistence](../../docs/adr/004-transactional-outbox-for-event-persistence.md) — defines the outbox pattern
- [System Events](system-event.md) — persistence schema, outbox lifecycle, and the future bus insertion point
