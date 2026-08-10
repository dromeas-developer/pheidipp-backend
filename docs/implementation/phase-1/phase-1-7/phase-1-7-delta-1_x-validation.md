# Cross-Validation Report — phase-1-7-delta-1
Date: 2026-08-08
Plan: docs/implementation/phase-1/phase-1-7/overview.md

## RC1 Contract Saturation
| Contract | Status | Detail |
|----------|--------|--------|
| ADR-010 (sync defer on Psycopg2Connector) | ✓ | Superseded by ADR-014 — the sync-only rule, sync dispatcher seam, and Psycopg2Connector constraint are all replaced by async equivalents |
| async-pipeline.md Infrastructure block | ✓ | Connector type, version pin, and worker mechanism updated in batch-1-architecture.md handoff |
| storage-topology.md "Why PostgreSQL for the task queue" | ✓ | Updated to reflect 3.x connector as the chosen path; Redis/Celery remains the longer-term migration target |
| ADR-009 (signal cleaning decoupled async task) | ✓ | Decoupling principle unchanged; only the defer call shape changes from sync `defer()` to `await defer_async()`. Precision note added to ADR-009 cross-reference in ADR-014 |
| ADR-002 (async-first database access) | ✓ | The sync procrastinate connector was the one documented exception to the async-first rule; this migration eliminates the exception, moving toward stack-truth compliance |
| ADR-013 (outbox publisher service ownership) | ✓ | Worker tasks still route through services; OutboxPublisherService ownership unchanged |
| principles.md #7 (all heavy processing is async) | ✓ | Queue backend remains PostgreSQL-backed; only the connector type changes |

## RC2 Vision Constraints
| Vision Principle | Status | Detail |
|------------------|--------|--------|
| — | — N/A | No vision constraints touch the connector type or defer mechanism. Vision defines what the system computes, not how tasks are dispatched. The worker is infrastructure, not product. |

## RC3 Entity Collision
| Entity | Status | Detail |
|--------|--------|--------|
| `app/worker/app.py` | ✓ | EXISTS — modified (connector swap + 2 defer call sites) |
| `app/services/activity_ingestion_service.py` | ✓ | EXISTS — modified (seam signature + _defer_signal_clean) |
| `app/services/onboarding_service.py` | ✓ | EXISTS — modified (defer call inside _defer_generate_plan) |
| `app/api/v1/activity.py` | ✓ | EXISTS — modified (defer call site) |
| `app/config.py` | ✓ | EXISTS — modified (get_procrastinate_dsn verification) |
| `tests/conftest.py` | ✓ | EXISTS — modified (_open_procrastinate_app fixture) |
| `requirements.txt` | ✓ | EXISTS — modified (version repin) |
| `docker-compose.yml` | ✓ | EXISTS — modified (worker command verification) |
| `alembic/env.py` | ✓ | EXISTS — modified (side fix: POSTGRES_DSN → DATABASE_URL) |

## RC4 Modification Safety
| Entity | Status | Detail |
|--------|--------|--------|
| `app/worker/app.py` | ✓ | Connector swap affects all tasks that use `defer` (signal_clean L200, generate_plan L365). Both call sites are in the batch BRD. The `@app.task` decorators and task bodies are unchanged. |
| `app/api/v1/activity.py` | ✓ | The defer at L155 is called after `session.commit()` at L140. Changing to `await defer_async` requires the route handler to be `async def` (it already is — FastAPI route). No downstream consumer broken. |
| `app/services/activity_ingestion_service.py` | ✓ | `task_dispatcher` seam changes from sync to async. State Explorer confirmed no test file directly references `task_dispatcher`. The `_defer_signal_clean` method is already `async def` — only the `dispatcher(...)` call inside becomes `await dispatcher(...)`. |
| `app/services/onboarding_service.py` | ✓ | `_defer_generate_plan` is already `async def`. The `defer` call inside becomes `await defer_async`. The test fake in `test_onboarding_service.py:375` is already `async def failing_defer` — no change needed. |
| `tests/conftest.py` | ✓ | `_open_procrastinate_app` fixture uses `procrastinate_app.open()` (sync context manager) and `schema_manager.apply_schema()`. With PsycopgConnector, `app.open()` may need to become `await app.open_async()` — verification step included in batch BRD. |
| `app/config.py` | ✓ | `get_procrastinate_dsn()` strips `postgresql+psycopg2://` → `postgresql://`. PsycopgConnector accepts libpq-format DSNs — the strip output is compatible. Verification step included. |

## RC5 Event Flow
| Event | Status | Detail |
|-------|--------|--------|
| All events | ✓ | No events changed. The connector migration and defer style change do not alter event produce→consume chains. Events are published via `EventPublisher` through the transactional outbox, independent of the defer mechanism. The defer-transaction-boundary (connector uses its own connection, not the caller's AsyncSession) is an existing characteristic preserved by the migration — sync `defer()` and async `defer_async()` both use the connector's own connection pool. |

## RC6 Invariant Enforcement
| Invariant | Enforcement Layer | Detail |
|-----------|-------------------|--------|
| At-least-once delivery | application (procrastinate) | Unchanged — property of the procrastinate PostgreSQL queue, not the connector type |
| All tasks must be idempotent | application | Unchanged — task-level idempotency checks, not connector-dependent |
| All heavy processing is async | api | Unchanged — API responses never wait for worker tasks |
| Defer after commit (4 of 5 call sites) | application | Preserved — 4 of 5 defer call sites are after commit; the 5th (`_defer_signal_clean` inside `run_ingestion_pipeline`) defers before the worker commits, but this is existing behavior and the swallow-and-log pattern handles defer failure |
| Failure isolation (swallow-and-log) | application | Preserved — `_defer_signal_clean` and `_defer_generate_plan` both swallow defer failures after logging so the commit path survives |
| Transactional outbox (event + outbox row in same transaction) | database | Unchanged — events are published via `EventPublisher`, not via defer. The defer mechanism is separate from the outbox. |
| `fit_file_key` prerequisite | application | Unchanged — not touched by this migration |

## RC7 ADR Re-Check
| ADR | Status | Detail |
|-----|--------|--------|
| ADR-014 | ✓ | Required and written — supersedes ADR-010, documents the connector migration, async defer rule, async dispatcher seam, and third-driver decision |

## Computational Invariant Fixtures
None — this migration does not introduce or modify computational invariants. All changes are structural (connector type, defer call style, seam signature).

## Gap Escalations
None — all RC checks passed. Two minor gaps found and resolved inline:
1. Conftest fixture compatibility with async connector — resolved as a verification step in the batch BRD (Step 6)
2. DSN format compatibility with PsycopgConnector — resolved as a verification step in the batch BRD (Step 3)
