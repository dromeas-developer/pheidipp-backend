# Failure Handling — Error Taxonomy and Recovery Patterns

## Purpose
- Defines how each failure mode is classified, handled, and surfaced
- Prevents silent failures that corrupt the twin model or coaching layer

## Failure Taxonomy

### Class A — Data Integrity Failures
Failures that would corrupt the twin model or create inconsistent state. These cause hard stops.

| Failure | Response |
|---|---|
| Object storage upload fails during FIT ingestion | Task retries (up to 5×). No Activity created. If all retries fail → DLQ + alert. |
| Activity created without `fit_file_key` (non-manual) | Application-layer validation blocks this. If DB constraint violated → rollback + alert. |
| TwinState write fails | Task retries. Previous TwinState remains current. Alert after 3 failures. |
| Onboarding transaction partial failure | Full rollback. `onboarding_complete` remains false. 500 with retry guidance. |

### Class B — Analysis Failures
Failures in analytical computation. Degrade gracefully; do not block the athlete experience.

| Failure | Response |
|---|---|
| `LoadComputationService` failure | Activity exists with null load scores. Retry scheduled (up to 3×). `calibration_eligible = false` until recomputed. `activity.load_compute.failures` incremented. After max retries → `activity.load_compute.stuck.count` incremented + DLQ entry. |
| `ExecutionAnalysisService` failure | No `ExecutionObservation`. Post-workout message proceeds with compliance-only context. Retry up to 3×. |
| `SegmentationTask` failure | No `PhysiologicalSegment` records. Execution analysis falls back to lap data. Retry. |
| FIT file fetch failure during analysis | Retry up to 3×. If all fail → alert; manual investigation required. |

### Class C — LLM Failures
Failures in agent calls. Always write a `GenerationEvent`; never silently swallow.

| Failure | Response |
|---|---|
| LLM API timeout | `GenerationEvent` written with `success=false`. 503 to caller. Retry available. |
| LLM API rate limit | Exponential backoff (15s, 30s, 60s). Up to 3 retries. DLQ after. |
| LLM produces invalid output (missing paragraphs, too short) | Output validation in agent. Retry with same context up to 2×. If still invalid → DLQ + alert. |
| Context budget exceeded | `ContextBudgetService` truncates before API call. Never discovered from response. |

### Class D — External Integration Failures
Third-party API failures. Degrade gracefully.

| Failure | Response |
|---|---|
| intervals.icu API unavailable | Sync retried on next scheduled cycle. Last successful cursor retained. No athlete-visible impact. |
| Weather API unavailable | `WeatherForecast` not created. Workout generated with `adjusted_targets = theoretical_targets`. Reason noted. |
| Weather API returns data for wrong location | Validates `athlete_id` in forecast; discards if mismatch. |

## Dead-Letter Queue

Tasks that exceed max retries are moved to the DLQ. The DLQ:
- Persists failed task payloads for manual inspection
- Fires an alert (PagerDuty or equivalent) when a task enters the DLQ
- Is replayed manually after the root cause is fixed

```typescript
type DLQEntry = {
  task_name: string
  payload: unknown
  failure_reason: string
  retry_count: number
  first_failed_at: string
  last_failed_at: string
  athlete_id: string | null
}
```

## Invariant: GenerationEvent Is Never Skipped

Every LLM API call attempt writes a `GenerationEvent` record, whether successful or failed. If the `GenerationEvent` write itself fails, the failure is logged to the application log and the LLM response (if any) is not discarded. The `GenerationEvent` write never blocks the `CoachingMessage` write.

A `CoachingMessage` without a corresponding `GenerationEvent` is a monitored alert condition.

## Athlete-Visible vs Silent Failures

```typescript
// Athlete-visible (surfaces as error or degraded experience):
// - FIT upload returns 503 after retries
// - First message generation fails → 503; retry button shown
// - Post-workout analysis unavailable → "Analysis coming soon" placeholder

// Silent (never surfaced to athlete):
// - Weather fetch failure → targets silently fall back to theoretical
// - Segmentation failure → execution analysis uses lap data
// - Baseline computation failure → wellness modifier defaults to green
// - Comparable session not found → message omits historical comparison
```

## Cross-References
- Async pipeline task definitions: `04-platform/async-pipeline.md`
- GenerationEvent invariant: `01-entities/generation-event.md`
- Activity fit_file_key invariant: `00-foundations/principles.md`
