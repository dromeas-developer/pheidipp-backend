# app/db/

## Purpose
Database infrastructure layer — the SQLAlchemy async engine, session factory, and declarative base class used by all ORM models. This folder owns database connectivity and session lifecycle; it does not own schema definitions (those live in `app/models/`).

## Contents
| File | Responsibility |
|---|---|
| `base.py` | Defines `Base`, the single `DeclarativeBase` that all ORM model classes extend |
| `session.py` | Provides the async SQLAlchemy `engine`, an `async_sessionmaker` factory (`AsyncSessionLocal`), and the `get_db` async generator for FastAPI dependency injection |

## Architecture Notes
- `engine` is created once at module import time from `app.config.get_postgres_url()` — connection pooling is managed by SQLAlchemy's built-in `AsyncEngine` pool.
- `AsyncSessionLocal` is configured with `expire_on_commit=False` so that ORM objects remain usable after a transaction commits without requiring a re-query.
- `get_db` yields an `AsyncSession` per request via FastAPI `Depends`; the session is automatically closed when the request scope ends.
- All database access throughout the application goes through this session factory — there is no other engine or session pathway.

## Cross-References
- [stack-truth: Database](../../.opencode/instructions/001-stack-truth.md) — PostgreSQL + TimescaleDB + pgvector, migrations via Alembic only
