---
id: ADR-004
status: accepted
tags: [async, database, events, transaction]
supersedes: ~
superseded-by: ~
---

# ADR 004: Transactional Outbox for Event Persistence

## Rules
- **Rule: Event Persistence Atomicity** — Every `SystemEvent` row must be written in the same database transaction as the domain state change that triggers it.
- **Rule: Outbox Status Management** — Publication state is tracked in `system_event_outbox`; no other mutable fields on event rows.
- **Rule: Publication Timing** — External event publication occurs only after the producing transaction commits successfully.
- **Rule: Idempotent Consumers** — Consumers must deduplicate on `event_id` or implement idempotent handlers for at-least-once delivery.

## Decision
Create a dedicated `SystemEvent` entity with an append-only `system_events` table and a mutable `system_event_outbox` table to implement the transactional outbox pattern for reliable event-driven communication.

## Rationale
- Events drive plan generation, workout generation, and coaching messages; losing them breaks downstream functionality silently.
- Publishing events after commit but without outbox persistence risks loss on process crash.
- Publishing events inside the transaction risks consumers seeing phantom state if the transaction rolls back.
- Separating persistence (`system_events`) from publication state (`system_event_outbox`) keeps event history append-only while allowing delivery retries.
- Retention policies (90 days operational, 1 year for trigger events) align with audit and reprocessing needs.

## Alternatives Rejected

| Option | Why Rejected |
|---|---|
| Publish events inline within transaction | Consumers may see phantom state if transaction rolls back. |
| Publish events after commit without outbox | Crash between commit and publish loses events permanently; no delivery guarantees. |
| Single mutable `system_events` with status column | Violates append-only invariant; complicates retention partitioning. |

## Tradeoffs
- **Pro**: Atomic event-state coupling ensures exactly-once persistence semantics.
- **Pro**: Outbox-based retries provide at-least-once delivery without phantom-state risk.
- **Con**: Two-table design adds write overhead and requires coordinated transactions.
- **Con**: Event retention partitioning adds operational complexity for archival.

## Compliance

**Compliant**
```python
# Write domain state and event in same transaction
with db.transaction() as tx:
    tx.insert(athlete_profile, ...)
    event_id = gen_uuid()
    tx.insert(SystemEvent, event_id=event_id, type='onboarding_completed', ...)
    tx.insert(SystemEventOutbox, event_id=event_id, status='pending')
# Publisher runs after commit
```

**Non-compliant**
```python
# Publishing outside transaction — crash loses event
tx.commit()
publish_event(event)  # If this crashes, event is lost forever
```

## Cross-References
- [ADR-002: Async-First Database Access](./002-async-first-database-access.md) — transactions and async processing.
- [SystemEvent entity](./../docs/architecture/04-platform/system-event.md) — full contract and schema.