# Test Scenarios — Phase 2.7 — Batch 4: Outbox Publisher Layering Fix

> **What this batch changes.** The Batch 2 `outbox_publisher` task
> currently constructs `SystemEventOutboxRepository` directly, opening
> its own `AsyncSession` and iterating `mark_published`. ADR-013 (Path B)
> mandates a named `OutboxPublisherService` between the worker and the
> repository. This batch re-routes the worker to call the service.
> Observable behaviour is unchanged from Batch 2 — these scenarios
> cover the layer-skip regression guard (new) plus re-verification of
> the preserved observable behaviour from Batch 2's Scenarios 7–13.

## Step 1 — `OutboxPublisherService.publish_pending(limit)`

| # | Scenario | Input | Expected |
|---|---|---|---|
| 1 | `OutboxPublisherService.publish_pending` exists with the ADR-013 signature | Import `app/services/outbox_publisher_service.py`; introspect `OutboxPublisherService.publish_pending` | The method exists, is `async`, and has signature `publish_pending(self, limit: int) -> int` |
| 2 | `publish_pending` opens its own `AsyncSession` | Patch `AsyncSessionLocal` with a spy; construct `OutboxPublisherService()`; call `publish_pending(limit=10)` | `AsyncSessionLocal` spy was invoked — the service creates its own session; the caller (e.g. the test or the worker) does not pass one in. No session argument appears on `publish_pending`'s public signature |
| 3 | `publish_pending` calls `SystemEventOutboxRepository.get_pending(limit)` | Patch `SystemEventOutboxRepository.get_pending` with a spy returning `[row1, row2, row3]`; call `OutboxPublisherService().publish_pending(limit=10)` | Spy was called with `limit=10`; service returns `3` after committing |
| 4 | `publish_pending` iterates `mark_published` per pending row | Patch `SystemEventOutboxRepository.mark_published` with a spy; insert 3 `pending` rows; call `OutboxPublisherService().publish_pending(limit=10)` | Spy was called exactly 3 times — once per pending row's `event_id`; all 3 rows show `status='published'` after the service commits |
| 5 | `publish_pending` commits the transaction | Insert 3 `pending` rows; call `OutboxPublisherService().publish_pending(limit=10)`; in a fresh session, query the rows | All 3 rows show `status='published'` — the service's commit is observable to other sessions after `publish_pending` returns |
| 6 | `publish_pending` returns the transitioned count | Insert 3 `pending` rows and 2 `published` rows; call `OutboxPublisherService().publish_pending(limit=10)` | Returns `3` (only `pending` rows transitioned; matches Batch 2 observable behaviour) |
| 7 | `publish_pending` handles empty queue | Call `OutboxPublisherService().publish_pending(limit=10)` when no `pending` rows exist | Returns `0`, no error, no rows modified |
| 8 | `publish_pending` handles partial batch | Insert 150 `pending` rows; call `OutboxPublisherService().publish_pending(limit=100)` | 100 rows transition to `published`; 50 remain `pending`; returns `100` |
| 9 | `publish_pending` idempotent across calls | Insert 3 `pending` rows; call `publish_pending(limit=10)` twice | First call returns `3`; second call returns `0` (no `pending` rows remain) |
| 10 | `OutboxPublisherService` is registered in `__all__` | Inspect `app/services/__init__.py` `__all__` | `OutboxPublisherService` appears in `__all__` |
| 11 | `OutboxPublisherService` does not import `EventPublisher` for writes | Inspect the import set of `app/services/outbox_publisher_service.py` | `EventPublisher` is not imported; the service is a status transitioner, not a write-side participant |
| 12 | `OutboxPublisherService` does not import any message bus client | Inspect the import set of `app/services/outbox_publisher_service.py` | No import references `redis`, `nats`, `kafka`, `aio_pika`, or any other message-bus client library — the service is a status transitioner only |

## Step 2 — Re-routed `outbox_publisher` worker task

| # | Scenario | Input | Expected |
|---|---|---|---|
| 13 | Worker calls `OutboxPublisherService.publish_pending` (regression guard — the original validator CRITICAL) | Import `app/worker/app.py`'s `outbox_publisher` task; patch `OutboxPublisherService.publish_pending` with a spy that returns `0`; run the `outbox_publisher` task | `OutboxPublisherService.publish_pending` spy was called — the worker delegates to the service |
| 14 | Worker does NOT construct `SystemEventOutboxRepository` (regression guard — the original validator CRITICAL) | Patch `SystemEventOutboxRepository.__init__` with a constructor spy; run the `outbox_publisher` task; inspect the spy's call frames | `SystemEventOutboxRepository.__init__` is NOT called from the worker task's frame. It may be called from inside `OutboxPublisherService.publish_pending`'s frame (acceptable — the service owns the repository). The worker's frame shows no repository construction — ADR-001 `WorkerIntegration` + ADR-013 satisfied |
| 15 | Worker does NOT open its own `AsyncSession` | Patch `AsyncSessionLocal` with a spy; run the `outbox_publisher` task | `AsyncSessionLocal` is NOT called from the worker task's frame. It is called from inside `OutboxPublisherService.publish_pending` (acceptable). The worker's frame shows no direct session construction |
| 16 | Worker preserves the procrastinate periodic schedule registration | Inspect `app/worker/app.py`'s decorator/registration on the `outbox_publisher` task | The registration (e.g. `@app.periodic(cron="*/15 * * * *")` or equivalent) and the task's registered name are identical to the shipped Batch 2 state — only the body was re-routed |
| 17 | Worker preserves task-level error handling | Mock `OutboxPublisherService.publish_pending` to raise `OperationalError`; run the worker task | The worker catches the exception, logs it at the task boundary, and returns the same diagnostic the shipped Batch 2 task returned on error — the task does not re-raise raw operational errors to the procrastinate scheduler |
| 18 | Worker returns the count from `OutboxPublisherService.publish_pending` | Mock `OutboxPublisherService.publish_pending` to return `42`; run the worker task | The worker task returns `42` — it propagates the service's count unchanged |

## Step 3 — Observable behaviour preserved from Batch 2 (regression — re-run Batch 2's behaviour scenarios against the re-routed implementation)

| # | Scenario | Input | Expected |
|---|---|---|---|
| 19 | (Batch 2 scenario 7) Publisher transitions pending to published still holds | Insert 3 `pending` rows; run the re-routed publisher task | All 3 rows have `status='published'` and `published_at` non-null; task returns `3` — identical to Batch 2's observable behaviour |
| 20 | (Batch 2 scenario 8) Idempotency still holds after re-routing | Insert 3 `pending` rows; run the re-routed publisher task twice | First run returns `3`; second run returns `0` — identical to Batch 2's observable behaviour |
| 21 | (Batch 2 scenario 10) Partial batch still holds after re-routing | Insert 150 `pending` rows; run the re-routed publisher task with `limit=100` | 100 rows transition to `published`; 50 remain `pending` — identical to Batch 2's observable behaviour |
| 22 | (Batch 2 scenario 12) No new domain events produced | Insert 3 `pending` rows; run the re-routed publisher task; query `SystemEvent` for events produced during the run | No new `SystemEvent` rows inserted — the publisher is still a status transitioner, not an event producer |
| 23 | (Batch 2 scenario 13) Publisher does not call `EventPublisher.publish()` | Patch `EventPublisher.publish` with a spy; run the re-routed publisher task | Spy was not called — the publisher still does not touch the write side after re-routing |
| 24 | Publisher status transition is observable after commit (preserved from Batch 2 scenario 15) | Insert 3 `pending` rows; run the re-routed publisher task; in a fresh session, query the rows | All 3 rows show `status='published'` — identical to Batch 2's observable behaviour |
| 25 | Publisher runs in its own transaction (preserved from Batch 2 scenario 14) | Insert 1 `pending` row in session A without committing; run the re-routed publisher task | Publisher returns `0` — the uncommitted row in session A is not visible to the `OutboxPublisherService` session. Same observable behaviour as Batch 2 — only the session-owning layer changed |

## Step 4 — Architecture inviolate (architect-owned, but coder-side assertion)

| # | Scenario | Input | Expected |
|---|---|---|---|
| 26 | Coder steps do not modify any architecture document | `git diff --name-only` on `docs/architecture/` for the commit(s) implementing this batch's coder steps | No files under `docs/architecture/` appear in the diff — the `system-event.md` update is owned by `p-vision-and-architect-author` via `batch-4-architecture.md` and is already applied |

(End of file — Scenarios 1–12 cover Step 1 (the new service contract); Scenarios 13–18 cover Step 2 (the re-routed worker); Scenarios 19–25 are regression-only re-runs of Batch 2's observable-behaviour scenarios against the re-routed implementation; Scenario 26 guards coder scope.)