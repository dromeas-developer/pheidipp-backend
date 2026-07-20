# Test Scenarios — Phase 2.7 — Batch 2: Outbox Publisher

## Step 1 — `SystemEventOutboxRepository.get_pending`

| # | Scenario | Input | Expected |
|---|---|---|---|
| 1 | `get_pending` returns pending rows | Insert 5 outbox rows with `status='pending'`; call `get_pending(limit=10)` | Returns 5 rows, ordered by `created_at ASC` |
| 2 | `get_pending` does not return published rows | Insert 3 `pending` rows and 2 `published` rows; call `get_pending(limit=10)` | Returns only the 3 `pending` rows |
| 3 | `get_pending` respects limit | Insert 10 `pending` rows; call `get_pending(limit=5)` | Returns 5 rows (the 5 oldest by `created_at`) |
| 4 | `get_pending` on empty queue | Insert no rows; call `get_pending(limit=10)` | Returns `[]`, no error |
| 5 | `get_pending` is read-only | Insert 3 `pending` rows; call `get_pending(limit=10)`; do not commit | Returned rows have `status='pending'` unchanged — no flush, no implicit status transition |
| 6 | `get_pending` ordering tiebreak | Insert 2 rows with identical `created_at` timestamps | Both rows returned; deterministic order (e.g., `event_id` ascending) — exact tiebreak is implementation-defined but must be stable across calls |

## Step 2 — Outbox publisher task

| # | Scenario | Input | Expected |
|---|---|---|---|
| 7 | Publisher transitions pending to published | Insert 3 `pending` rows; run the publisher task | All 3 rows have `status='published'` and `published_at` is non-null (where the model defines that field); task returns `3` |
| 8 | Publisher is idempotent | Insert 3 `pending` rows; run the publisher task twice | First run returns `3` and transitions 3 rows; second run returns `0` and modifies no rows (no `pending` rows remain) |
| 9 | Publisher handles empty queue | Run the publisher task when no `pending` rows exist | Returns `0`, no error, no rows modified |
| 10 | Publisher handles partial batch | Insert 150 `pending` rows; run the publisher task with `limit=100` | 100 rows transition to `published`; 50 remain `pending`; task returns `100` |
| 11 | Publisher handles partial batch across runs | After scenario 10, run the publisher task again with `limit=100` | Remaining 50 rows transition to `published`; task returns `50` |
| 12 | Publisher does not produce new domain events | Insert 3 `pending` rows; run the publisher task; query `SystemEvent` for events produced during the publisher run | No new `SystemEvent` rows were inserted by the publisher — the publisher is a status transitioner, not an event producer |
| 13 | Publisher does not call `EventPublisher.publish()` | Patch `EventPublisher.publish` with a spy; run the publisher task | Spy was not called — the publisher does not touch the write side |
| 14 | Publisher runs in its own transaction | Insert 1 `pending` row in session A without committing; run the publisher task in session B | Publisher returns `0` — the uncommitted row in session A is not visible to the publisher's session |
| 15 | Publisher status transition is observable after commit | Insert 3 `pending` rows; run the publisher task; in a fresh session, query the rows | All 3 rows show `status='published'` — the publisher's commit is observable to other sessions |
| 16 | Publisher is registered as a procrastinate task | Inspect `app/worker/app.py` and the registered task namespace | The publisher task appears in the procrastinate `App`'s task registry under its expected name |
| 17 | Publisher schedule interval is short | Inspect the periodic schedule registration | The interval is every 10-30 seconds (band accepted; exact value is implementation-defined within this band) |

## Step 3 — `system-event.md` documentation update

| # | Scenario | Input | Expected |
|---|---|---|---|
| 18 | `system-event.md` has no Redis references | Grep `docs/architecture/04-platform/system-event.md` for "Redis" (case-insensitive) | Zero matches — all Redis references removed and replaced with PostgreSQL-native language |
| 19 | `system-event.md` documents the insertion point | Read the updated "Runtime Flow" / "Publication" section | Contains a note describing the publisher as a status transitioner with a defined insertion point for a future external message bus (e.g., "when a bus is added, the publisher will publish to the bus before marking as published") |
| 20 | `system-event.md` mermaid diagram updated | Read the mermaid diagram in `system-event.md` | "MessageBus" participant is replaced or removed; the diagram shows the publisher transitioning outbox row status without an external bus participant |
| 21 | `event-catalogue.md` and `event-topology.md` are unchanged | `git diff` on `docs/architecture/00-foundations/event-catalogue.md` and `docs/architecture/04-platform/event-topology.md` for this branch | No changes to either file (Batch 3 owns those documents) |
