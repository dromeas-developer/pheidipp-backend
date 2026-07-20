# Batch BRD: Phase 2.7 — Batch 2 — Outbox Publisher
## Source: docs/implementation/phase-2/phase-2-7/overview.md

## Batch Objective
Add the outbox publisher worker that transitions `SystemEventOutbox` rows from `pending` to `published`, closing G-04. After this batch, the transactional outbox pattern is complete: the write side (services inserting event + outbox row in the producing transaction) was already correct; the publish side now exists. This batch also updates `docs/architecture/04-platform/system-event.md` to remove stale Redis references and align the documentation with the PostgreSQL-native reality.

## Preconditions
Batch 1 is complete; its Batch Success Criteria hold. Specifically, the agent relocation is done and the test suite passes.

No DevOps prerequisites for this batch. The original TimescaleDB-extension prerequisite has been removed — the hypertable conversion that required it was retracted per the G-02 retraction (see `docs/implementation/gap-analysis-phase-1-2.md` §5 G-02 and the updated stack-truth `## Timescale / Hypertables` block).

## Scope
- `SystemEventOutboxRepository` extension: method to fetch pending rows in batches (`get_pending(limit)`)
- Outbox publisher procrastinate task in `app/worker/app.py`: periodically reads pending outbox rows and transitions them to `published` without an external message bus
- Documentation update: `docs/architecture/04-platform/system-event.md` — remove Redis references, align with PostgreSQL-native reality, document the insertion point for a future external bus

## Out Of Scope
- **No external message bus.** The publisher marks rows as published without publishing to Redis, NATS, or any external system. The insertion point for a future bus is documented but not implemented.
- **No `LISTEN/NOTIFY` mechanism.** The publisher uses periodic polling. A `LISTEN/NOTIFY`-driven approach is a future optimization.
- **No changes to event production code.** Services that call `EventPublisher.publish()` are not modified — the write side of the outbox is already correct.
- **No changes to event payloads or event catalogue entries.** This batch is infrastructure-only.
- **No hypertable migration.** The hypertable-conversion portion of the originally-planned Batch 2 is retracted per G-02. None of the six flagged tables (`twin_states`, `raw_sensor_streams`, `physiology_measurements`, `system_events`, `generation_events`, `coaching_messages`) are hypertable candidates per the corrected stack-truth discriminator (fixed cadence + row-is-measurement + fleet-wide window-scan). They remain standard append-only tables. The single true hypertable in the model (`athlete_wellness`) is unimplemented and correctly deferred to the wellness ingestion phase. **No migration is produced in this batch.**
- **No TimescaleDB extension install.** `CREATE EXTENSION IF NOT EXISTS timescaledb;` will be installed by whichever future phase introduces `athlete_wellness` as a hypertable (likely the Phase 3 wellness ingestion batch). It is NOT installed in this batch.
- **Batch 3** (event-flow, plan-router, cleanups) is not in this batch.

## Steps

### Step 1 — Extend the outbox repository with `get_pending`

1. [OWNER: Coder] Add a method to `SystemEventOutboxRepository` to fetch pending outbox rows in batches: `get_pending(limit: int) -> list[SystemEventOutbox]` — selects rows where `status = 'pending'`, ordered by `created_at`, limited to `limit`. This method is read-only (no flush, no commit). It mirrors the existing repository's read patterns; do not introduce a new session or a different transaction boundary.

### Step 2 — Create the outbox publisher procrastinate task

2. [OWNER: Coder] Create an outbox publisher procrastinate task in `app/worker/app.py`. The task:
   - Opens its own `AsyncSession`
   - Constructs `SystemEventOutboxRepository`
   - Calls `get_pending(limit=100)` to fetch a batch of pending rows
   - For each row, calls the existing `mark_published(event_id)` method (or equivalent) to transition status to `published` and stamp `published_at`
   - Commits
   - Returns the count of rows transitioned
   - Is registered as a periodically-scheduled task (using procrastinate's periodic scheduling mechanism, or an external cron deferral — the coder chooses the approach that fits the existing worker setup)
   - The schedule interval should be short (every 10-30 seconds) to keep event publication latency low
   - The task is idempotent: rows already `published` are not fetched (the `get_pending` query filters on `status = 'pending'`)

### Step 3 — Update `system-event.md` architecture documentation

3. [OWNER: Coder] Update `docs/architecture/04-platform/system-event.md` to remove Redis references and align with the PostgreSQL-native reality:
   - In the "Runtime Flow" mermaid diagram, the "MessageBus" participant is replaced with "StatusTransition" (or removed, since there is no external bus)
   - The "Publisher reads pending outbox entries and publishes to Redis/message bus" language is replaced with "Publisher reads pending outbox entries and transitions status to 'published'. The insertion point for a future external message bus is the publisher task — when a bus is added, the publisher will publish to the bus before marking as published."
   - The "Consumers subscribe to the message bus (Redis)" language is replaced with "Consumers are currently triggered by procrastinate task deferral, not by outbox publication. The outbox publication state machine is maintained for audit and future external consumer support."
   - Add a note: "The Redis-based publication model was superseded by the PostgreSQL-native procrastinate migration (Phase 1-7). The outbox table and state machine remain; the publication target is a status transition, not an external bus."

## Context Needed
Step 1:
  Primary:    `app/repositories/system_event_outbox_repository.py` (existing `mark_published` method, existing read patterns, session handling convention)
  Secondary:  `app/models/system_event.py` for `SystemEventOutbox` column names (`status`, `created_at`, `published_at`, `event_id`)
  Fallback:   `docs/architecture/04-platform/system-event.md` for the outbox state machine contract
  Forbidden:  Do not modify `EventPublisher.publish()` — the write side is already correct

Step 2:
  Primary:    `app/worker/app.py` (existing procrastinate `App` setup, existing task registration pattern, existing `AsyncSession` construction pattern in other tasks)
  Secondary:  output of Step 1 (`get_pending` method)
  Fallback:   procrastinate documentation for periodic task scheduling
  Forbidden:  Do not modify `EventPublisher.publish()` — the write side is already correct. Do not produce new domain events from the publisher — it only transitions outbox row status

Step 3:
  Primary:    `docs/architecture/04-platform/system-event.md` (the file to update)
  Secondary:  —
  Fallback:   —
  Forbidden:  Do not modify `event-catalogue.md` or `event-topology.md` in this batch — those are Batch 3's scope. Do not modify other `04-platform/*.md` documents

(This is everything relevant to the steps above. Primary items are fetched together in Pre-Flight Step 3; Secondary and Fallback are requested only on demand.)

## Batch Success Criteria
Batch 2 complete when:
- `SystemEventOutboxRepository.get_pending(limit)` exists and returns rows with `status='pending'` ordered by `created_at`
- `get_pending` does not return rows with `status='published'`
- `get_pending` respects the `limit` argument (returns at most `limit` rows)
- The outbox publisher procrastinate task is registered in `app/worker/app.py` and appears in the procrastinate job namespace
- Running the publisher task transitions pending outbox rows to `published` (status changes; `published_at` is non-null where the model defines that field)
- The publisher is idempotent: running it twice on the same row set transitions rows on the first run and transitions 0 rows on the second run (no `pending` rows remain)
- The publisher handles an empty pending queue gracefully (returns 0, no error, no rows modified)
- The publisher handles a partial batch: when pending rows exceed `limit`, the first run transitions `limit` rows and leaves the rest `pending`; subsequent runs transition the rest
- The publisher does not modify `EventPublisher.publish()` or any event-producing service
- `docs/architecture/04-platform/system-event.md` no longer references Redis as the publication target (zero grep matches for "Redis")
- `system-event.md` documents the insertion point for a future external message bus
- `event-catalogue.md` and `event-topology.md` are unchanged by this batch (Batch 3 owns those)
- The full existing test suite passes (no test logic changes required for this batch — the additions are net-new code paths)

## Relevant Architecture Contracts
- `04-platform/system-event.md` → "Publisher (post-commit) reads pending outbox entries and publishes" — IMPLEMENTS: outbox publisher worker
- `04-platform/system-event.md` → "Transactional outbox pattern" — DEPENDS ON: the publisher must not break the atomicity invariant (event + outbox row in same transaction; publication only after commit)
- `04-platform/event-topology.md` → "Publication Mechanics" — IMPLEMENTS: publisher process (status transition without external bus)

## Relevant Invariants
- **Transactional outbox atomicity:** Event and outbox row are inserted in the same database transaction as the domain state change; rollback removes both. Publication occurs only after the producing transaction commits successfully. — The publisher reads only `status='pending'` rows, which are only visible after the producing transaction has committed. The publisher's own commit transitions the status; this is a separate transaction from the producing one, which is correct — the publisher does not participate in the producing transaction.
- **Append-only tables remain append-only:** The publisher's status transition is the only UPDATE in the outbox system and applies to `system_event_outbox` only, which is NOT one of the append-only event-log tables. The append-only tables (`system_events`, `twin_states`, `raw_sensor_streams`, `physiology_measurements`, `generation_events`, `coaching_messages`) remain append-only — this batch does not introduce any UPDATE or DELETE path on them.

## Relevant Event Contracts
None produced or consumed by this batch's code. The outbox publisher reads `SystemEventOutbox` rows and transitions status; it does not produce new domain events.

## Relevant Notes
**Implementation Clarifications** — The publisher task runs in its own transaction, separate from the producing transaction. This is correct and required by the transactional outbox pattern: the publisher must not see `pending` rows from transactions that have not yet committed, and must not participate in the producing transaction's commit/rollback. The `status='pending'` filter naturally enforces this — uncommitted rows are not visible to the publisher's session.

**Known Risks** — The publisher runs every 10-30 seconds, so event publication latency is bounded by the polling interval. If lower latency is ever required, a `LISTEN/NOTIFY`-driven publisher is the natural next step (out of scope here). Until then, consumers that need to react to an event should be triggered by procrastinate task deferral from the producer (the existing pattern), not by polling the outbox. The outbox's role is audit + future external consumer support, not low-latency fanout.

**Implementation Clarifications** — The `mark_published` method (or its equivalent) already exists on `SystemEventOutboxRepository` per the original Phase 1 implementation of the outbox write side. The coder should reuse it, not reimplement it. If the existing method signature differs from what the publisher needs (e.g., it expects a different argument shape), widen the existing method rather than creating a parallel one.

## Files Expected To Change
- `[EXISTING — modified] app/repositories/system_event_outbox_repository.py` — add `get_pending`
- `[EXISTING — modified] app/worker/app.py` — add outbox publisher task
- `[EXISTING — modified] docs/architecture/04-platform/system-event.md` — remove Redis references, document insertion point

## Coder Notes
- **No migration this batch.** All schema work for the hypertable conversion is removed. The DB schema is untouched. If any test imports assume composite primary keys or removed FKs, those imports are wrong — Batch 2 does not change the schema.
- **Outbox publisher scheduling.** The existing worker setup uses procrastinate. For periodic scheduling, use whatever mechanism procrastinate provides for periodic tasks (check the procrastinate 2.x docs). If procrastinate 2.x does not support periodic tasks natively, an external cron job that defers the publisher task on a schedule is acceptable. The key requirement: the publisher runs every 10-30 seconds.
- **`mark_published` reuse.** Before adding a new transition method, grep `SystemEventOutboxRepository` for the existing publish-side method. The original Phase 1 outbox implementation included a status transition helper — reuse it. Do not silently duplicate the transition logic.
- **`system-event.md` update scope.** Only update the Redis references in `system-event.md`. Do not change the event catalogue, event topology, or any other architecture document in this batch. Batch 3 touches `event-catalogue.md` and `event-topology.md` for the `twin_model_ready` implementation.
- **Do not introduce external bus dependencies.** The publisher must not import or require Redis, NATS, Kafka, or any message bus client. The publisher is a status transitioner. The architecture document update should make the future-bus insertion point explicit so that adding a bus later is a localized change to one task, not a redesign.
