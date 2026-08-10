---
id: ADR-009
status: accepted
tags: [async-pipeline, signal-cleaning, transaction-boundary, reprocessing]
supersedes: ~
superseded-by: ~
---

# ADR 009: Signal Cleaning As A Decoupled Async Task

## Rules
**Decoupled transaction**: Signal cleaning runs in its own procrastinate task with its own `AsyncSession`; it never runs inline inside `ActivityIngestionService._run_ingestion_pipeline`'s transaction.
**Enqueue gate**: The `signal_clean` task is enqueued only when `activity.calibration_eligible = true AND activity.sport_type = 'running'`; non-running and manual-entry activities never enqueue it.
**Failure isolation**: A signal-cleaning failure MUST NOT roll back the already-committed `Activity` row; the task raises so procrastinate retries it; `Activity.cleaning_pipeline_version` stays `null` until a retry succeeds.
**Atomic persist**: The cleaned-stream object-storage upload and the `RawSensorStream` insert are committed in the same transaction so a half-written state is impossible; the cleaned-stream key is never persisted before the upload returns.
**Version transition**: `Activity.cleaning_pipeline_version` transitions `null → <version>` only after the cleaned stream is uploaded AND the `RawSensorStream` row is flushed in the same transaction.

## Decision
Signal cleaning is implemented as a standalone procrastinate task (`signal_clean`) enqueued by `ActivityIngestionService._run_ingestion_pipeline` after calibration eligibility is confirmed, rather than as an inline step inside the ingestion transaction. The task downloads the raw FIT, runs the 7-step `SignalCleaningService` pipeline (steps 1–4 active for Phase-2.2; 5–7 deferred to segmentation phases), uploads the cleaned stream to `cleaned-streams/{athlete_id}/{activity_id}/stream.gz`, inserts the `RawSensorStream` metadata row, and sets `Activity.cleaning_pipeline_version` from `null` to the pipeline version — all in its own transaction. The decoupling is mandated by the sub-phase invariant that signal-cleaning failure must not block Activity creation.

## Rationale
- The sub-phase explicitly requires "Signal cleaning failure does not block Activity creation — retry mechanism in place." An inline call inside `_run_ingestion_pipeline`'s transaction would either roll back the Activity on cleaning failure (violating the invariant) or swallow the exception (losing the retry signal). A separate task is the only structure that satisfies both halves of the invariant.
- `04-platform/async-pipeline.md` already documents `FitIngestionTask` as enqueuing "clean signal → store `RawSensorStream` → enqueue `SegmencationTask`" as steps that run after the Activity is durable. A dedicated procrastinate task realises this directly rather than smuggling heavy work into the ingestion transaction.
- The async-pipeline note that `TwinRecalibrationTask` may run before `RawSensorStream` is available — and that `ThresholdDetectionService` skips RR inflection when the stream is missing — requires the cleaning task to publish its result independently, so downstream consumers can observe "not yet ready" vs "failed permanently." A decoupled task with its own committed `RawSensorStream` row is the cleanest surface for that observation.
- `Activity` storage model declares `cleaning_pipeline_version` null → non-null as the readiness signal for `RawSensorStream`. Performing that transition in a separate, post-commit transaction keeps the ingestion transaction latency at p95 < 30s (architecture performance constraint) by moving the object-storage upload and the 7-step computation off the ingestion critical path.
- Idempotent retry is needed: a cleaning task that dies after uploading the cleaned stream but before committing `RawSensorStream` must be safe to re-run. A standalone task with the cleaned-stream key derived deterministically from `activity_id` (not a fresh UUID) lets the object-storage immutability check (`ObjectStorageConflictError`) act as the idempotency gate on retry.

## Alternatives Rejected
| Option | Why Rejected |
| Inline `SignalCleaningService.clean()` call inside `_run_ingestion_pipeline` before twin recalibration | Violates the sub-phase invariant: a cleaning failure would roll back the Activity row or require exception swallowing; also stretches ingestion latency past the p95 < 30s budget for activities with long streams. |
| Inline call AFTER twin recalibration but still in the ingestion transaction | Same invariant violation; the transaction boundary is the problem, not the call ordering within it. |
| Event-driven: emit `cleaning_requested` and let a consumer enqueue the task | Introduces a new event contract (`cleaning_requested`) that is not in `00-foundations/event-catalogue.md`; creating events is an architecture decision, not an implementation one — escalate rather than improvise. |
| Inline + commit-twice (commit Activity, then commit cleaning in same handler) | Two commits per worker task breaks the single-transaction-per-task convention used by `fit_ingest` and `recalibrate_twin`; also leaves the worker responsible for partial-failure recovery logic that a dedicated task handles for free. |

## Tradeoffs
- **Pro**: Activity creation latency is independent of stream length; cleaning can take >30s on a long trail run without stalling the ingestion pipeline.
- **Pro**: Cleaning failures retry independently via procrastinate's existing backoff/DLQ; the ingestion pipeline is unaffected and the Activity remains queryable.
- **Pro**: The `RawSensorStream` row is the single durable signal that cleaning succeeded — consumers can treat its presence as authoritative, matching the architecture's `cleaning_pipeline_version` transition contract.
- **Con**: There is a window where `calibration_eligible = true` but `RawSensorStream` does not yet exist; downstream consumers (Phase-2.3 `ThresholdDetectionService`) must handle this explicitly by skipping RR inflection, as `async-pipeline.md` already notes.
- **Con**: The cleaned-stream object key must be deterministic (derived from `activity_id`) for retry idempotency, which means the same key can never be reused for a re-cleaned stream of the same activity; a future "re-clean with a new pipeline version" flow would need a versioned key suffix.

## Compliance
Compliant:
```python
# worker task owns its own session and commits once; failure retries independently
@app.task()
async def signal_clean(*, activity_id: str) -> dict[str, Any]:
    async with AsyncSessionLocal() as session:
        service = SignalCleaningService(session=session, ...)
        await service.clean(uuid.UUID(activity_id))
        await session.commit()
```
Non-compliant:
```python
# inline inside the ingestion transaction — failure rolls back Activity
await self._run_ingestion_pipeline(...)  # commits Activity + twin
await self.signal_cleaning.clean(activity)  # if this raises, the
                                             # already-committed Activity
                                             # is fine BUT if it ran inside
                                             # the same tx the Activity would
                                             # be lost too — avoid this shape
```

## Cross-References
[ADR-004: Transactional Outbox For Event Persistence](./004-transactional-outbox-for-event-persistence.md) — the outbox pattern already used by `EventPublisher` is the model for "commit domain row + side effect in the same transaction"; ADR-009 applies the same principle to `RawSensorStream` + cleaned-stream upload.

The `signal_clean` defer context changes from sync `defer()` to `await defer_async()` per ADR-014. The decoupling principle (separate task, own session, failure isolation) is unchanged; only the defer call shape changes. ADR-010's sync-only constraint on the `task_dispatcher` seam is superseded by ADR-014's async seam.
