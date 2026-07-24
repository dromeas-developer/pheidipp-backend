---
id: ADR-013
status: accepted
tags: [architecture, events, outbox, worker]
supersedes: ~
superseded-by: ~
---

# ADR 013: Outbox Publisher Service Ownership

## Rules
**OutboxPublisherService**: The publish-side transaction for `system_event_outbox` status transitions is owned by `OutboxPublisherService.publish_pending(limit)`, not by the worker task directly.
**WorkerIntegration**: Infrastructure-plumbing worker tasks (polling daemons, status transitioners, retention pruners, DLQ replayers) are NOT an exception to ADR-001 — they still route through a service.
**SessionOwnership**: `OutboxPublisherService` creates its own `AsyncSession` internally; the worker does not pass or manage sessions.

## Decision
Introduce `OutboxPublisherService` as the publish-side owner for `system_event_outbox` status transitions, separating it from `EventPublisher` which owns the producer-side transactional boundary.

## Rationale
- **ADR-001 compliance**: Worker → repository layer-skip is unambiguously forbidden; a named service prevents future Plan Defects from re-litigating this boundary.
- **Transactional separation**: Producer-side (`EventPublisher.publish()`) and publish-side (`OutboxPublisherService.publish_pending()`) are deliberately distinct transactional regions; separate services clarify the boundary.
- **Precedent for infrastructure tasks**: Polling daemons and status transitioners are not exceptions to layer architecture; explicit service ownership makes this discoverable for future reviewers.

## Alternatives Rejected
| Option | Why Rejected |
|---|---|
| Extend `EventPublisher` with `publish_pending()` | Conflates two distinct transactional regions inside one service; producer-side and publish-side have different session lifecycles and failure semantics. |
| Leave worker → repository as implicit exception | No ADR documents the exception; the architecture diagram invites the next reviewer to repeat the layer-skip question. |

## Tradeoffs
- **Pro**: Explicit ownership boundary prevents future Plan Defects.
- **Pro**: Clear separation of producer and publish transaction semantics.
- **Con**: Additional service file for a simple polling task.
- **Con**: Two services touching the same outbox table (one for writes, one for status transitions).

## Compliance
**Compliant**
```python
# OutboxPublisherService owns the publish-side transaction
class OutboxPublisherService:
    async def publish_pending(self, limit: int) -> int:
        async with AsyncSessionLocal() as session:
            repo = SystemEventOutboxRepository(session)
            pending = await repo.get_pending(limit)
            for row in pending:
                await repo.mark_published(row.event_id)
            await session.commit()
            return len(pending)
```

**Non-compliant**
```python
# Worker calling repository directly — violates ADR-001
@app.task
async def outbox_publisher():
    async with AsyncSessionLocal() as session:
        repo = SystemEventOutboxRepository(session)
        pending = await repo.get_pending(100)
        for row in pending:
            await repo.mark_published(row.event_id)
        await session.commit()
```

## Cross-References
- [ADR-001: Layer Architecture](./001-layer-architecture.md) — WorkerIntegration and RepositoryAccess rules.
- [ADR-004: Transactional Outbox for Event Persistence](./004-transactional-outbox-for-event-persistence.md) — Outbox pattern atomicity and timing.