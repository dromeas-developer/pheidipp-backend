---
id: ADR-006
status: accepted
tags: [async, database, transaction, error-handling]
supersedes: ~
superseded-by: ~
---

# ADR 006: Explicit Rollback After Caught Database Exceptions

## Rules
- **Rule: Catch-And-Translate Rollback** — When a service method catches a database-level exception (e.g. `IntegrityError`) in order to translate it into a domain error, it MUST call `await session.rollback()` before raising the domain error.
- **Rule: Session Returned Clean** — After the explicit rollback, the `AsyncSession` must be in a usable state (no pending transaction, no stale ORM identity map) so that callers may continue using it if needed.
- **Rule: No Silent Swallow** — The rollback must always be followed by a raise. A caught database exception must never be swallowed — if the translation condition is not met, re-raise the original exception.

## Decision
All service methods that catch SQLAlchemy database exceptions inside a transaction boundary and translate them into domain errors must perform an explicit `await session.rollback()` before raising. This returns the session to a clean, usable state at the point of translation rather than relying on the framework or outer caller to eventually close a broken session. The rule applies only where the service itself catches the database exception — uncaught exceptions that propagate to the framework are handled by the session dependency's teardown.

## Rationale
- A caught `IntegrityError` leaves the `AsyncSession` in an unusable state; any subsequent ORM operation on that session raises `PendingRollbackError`.
- Domain-error translation happens *inside* the service method, between the DB failure and the re-raise. Leaving the session broken at that point forces every caller that catches the domain error to know about SQLAlchemy session mechanics — a layering violation.
- Explicit rollback at the catch site documents intent clearly to readers: "this database operation failed, the transaction is terminated, a domain error follows."
- Explicit rollback is idempotent and low-cost on an already-failed transaction; the risk of doing it when not strictly needed is near zero.
- Future service composition (e.g., saga-style orchestration across two repositories within one session) requires a clean session between operations. The explicit rollback keeps that path open without retrofitting.

## Alternatives Rejected

| Option | Why Rejected |
|--------|-------------|
| Rely on framework auto-rollback on exception propagation | Pushes transaction-lifecycle knowledge into the framework layer; callers that catch domain errors cannot safely use the session if it was not pre-rolled-back. |
| Rely on the service method's top-level `try/finally` to rollback | Adds a second rollback responsibility at the method boundary; when an `IntegrityError` is caught in a nested block, the outer finally cannot distinguish "cleanly handled" from "still broken." |
| Leave the rollback to the repository layer | Violates singular ownership: repositories perform write operations; they do not own transaction boundary lifecycle. |

## Tradeoffs
- **Pro**: Session state is deterministic at every catch point; domain-error callers never encounter `PendingRollbackError`.
- **Pro**: Pattern is self-documenting — each catch block visibly terminates its own transaction.
- **Pro**: Composes cleanly with future multi-repository service methods.
- **Con**: Adds one extra `await session.rollback()` call per catch-and-translate block; marginally more code than auto-rollback.
- **Con**: If the rollback itself fails (connection dropped), the original exception may be masked — mitigated by wrapping in a `try/except` if the failure path is diagnostic-critical.
- **Con**: Coders must remember to include the rollback in every catch-and-translate block; forgetting it recreates the original inconsistency.

## Compliance

Compliant:
```python
try:
    await self.training_goals.add(goal_row)
except IntegrityError as exc:
    await self.session.rollback()
    if TrainingGoalRepository_unique_violation(exc):
        raise TrainingGoalConflictError(
            "athlete already has an active training goal"
        ) from exc
    raise
```

Non-compliant:
```python
try:
    await self.training_goals.add(goal_row)
except IntegrityError as exc:
    if TrainingGoalRepository_unique_violation(exc):
        raise TrainingGoalConflictError(
            "athlete already has an active training goal"
        ) from exc
    raise
    # session is in PendingRollback state here — caller cannot use it
```

## Cross-References
[ADR-004: Transactional Outbox for Event Persistence](./004-transactional-outbox-for-event-persistence.md) — Defines the commit boundary; ADR-006 governs what happens when that commit is prevented by a caught database exception inside the transaction.
