---
id: ADR-005
status: accepted
tags: [database, async, sqlalchemy]
supersedes: ~
superseded-by: ~
---

# ADR 005: Async-First Database Access

## Rules
**AsyncSession**: All database access MUST use SQLAlchemy's `AsyncSession`.

**No Sync SQLAlchemy**: Synchronous SQLAlchemy usage is forbidden.

**CPU-Bound Tasks**: CPU-bound tasks (e.g., FIT file parsing) MUST use `asyncio.to_thread()`.

**Layer Compliance**: Database access MUST only occur in the `repositories` layer. No direct repository access outside `services`.

**Migration Safety**: Alembic migrations MUST use async-compatible patterns.

**Testing**: Database tests MUST use async test clients and async database fixtures.

## Decision
Pheidipp enforces async-first database access using SQLAlchemy 2.0's `AsyncSession`. This decision ensures non-blocking I/O for all database operations, aligning with FastAPI's async architecture and improving scalability under load.

## Rationale
- **Performance**: Async I/O prevents thread starvation and improves concurrency for I/O-bound operations.
- **Stack Consistency**: FastAPI is async-native, and sync database access would block the event loop.
- **Scalability**: Async database access allows Pheidipp to handle more concurrent requests without increasing thread count.
- **Future-Proofing**: Async is the standard for modern Python web frameworks and databases.
- **TimescaleDB Compatibility**: Async access is fully supported by TimescaleDB and PostgreSQL.

## Alternatives Rejected
| Option | Why Rejected |
|--------|--------------|
| Sync SQLAlchemy | Blocks the event loop, reducing scalability and performance. |
| Mixed sync/async | Increases complexity and risk of event loop blocking. |
| ORM alternatives (e.g., TortoiseORM) | SQLAlchemy is already the stack standard and supports async. |

## Tradeoffs
**Pro**:
- Improved scalability and performance for I/O-bound workloads.
- Consistent async stack from API to database.
- Better resource utilization under load.

**Con**:
- Async code is slightly more complex to write and debug.
- Requires async-compatible libraries for all database interactions.
- Testing async code requires async test clients and fixtures.

## Compliance
### Compliant
```python
from sqlalchemy.ext.asyncio import AsyncSession

async def get_athlete(db: AsyncSession, athlete_id: int):
    result = await db.execute(select(Athlete).where(Athlete.id == athlete_id))
    return result.scalars().first()
```

### Non-Compliant
```python
from sqlalchemy.orm import Session

def get_athlete(db: Session, athlete_id: int):  # Sync Session blocks the event loop
    return db.query(Athlete).filter(Athlete.id == athlete_id).first()
```

## Cross-References
[ADR-001: Layer Architecture](./001-layer-architecture.md) — Enforces async rules and layer boundaries.
[stack-truth.md](../../stack-truth.md) — Async database access rules and stack fundamentals.