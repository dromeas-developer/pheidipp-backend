# Implementation Overview: Phase 1-7 Delta — Procrastinate 3.x Connector Migration
## Plan ID: phase-1-7-delta-1

## Sub-Phase Reference
Sub-Phase ID: Phase-1-7 (delta to shipped batch-1)
Sub-Phase Title: Architecture Simplification — worker startup blocker resolution

## Objective
Migrate the procrastinate worker from `Psycopg2Connector` (sync, psycopg2) to `PsycopgConnector` (async, psycopg3) and repin procrastinate 2.x→3.x so the worker process can start. All defer call sites switch from sync `defer()` to `await defer_async()`.

## Scope
- Connector swap: `Psycopg2Connector` → `PsycopgConnector` in `app/worker/app.py`
- Version repin: `procrastinate>=2.0,<3.0` → `procrastinate>=3.0,<4.0`
- Defer contract migration: `defer(...)` → `await defer_async(...)` at all 5 call sites
- `task_dispatcher` seam: sync → async on `ActivityIngestionService`
- Conftest fixture update for async connector compatibility
- Side fix: `alembic/env.py` references non-existent `settings.POSTGRES_DSN`

## Out Of Scope
- Redis/Celery migration (Path C — rejected for initial rollout)
- Custom async worker polling `procrastinate_jobs` (Path B — rejected for initial rollout)
- Alembic migration to psycopg3 (psycopg2 stays for alembic's sync engine)
- Removing psycopg2 from requirements.txt (still used by alembic)

## Batch Routing
| Batch | Focus | Depends On |
|-------|-------|------------|
| 1 | Connector migration + defer contract + seam + test fixtures + side fix | — |

## ADRs Written
- **ADR-014: Procrastinate 3.x With PsycopgConnector (psycopg3) — Async Defer** — supersedes ADR-010; async defer only, async dispatcher seam, PsycopgConnector is the connector, third driver is deliberate

## Gap Escalations
- None — all RC checks passed; minor gaps (conftest fixture, DSN format verification) resolved inline in the batch BRD
