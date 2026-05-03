# Stack Truth

## Runtime
Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2

## Layer Architecture (Non-Negotiable)
api → services → repositories → models
agents → services
worker → services

Rules:
- No business logic in api
- No direct repository access outside services
- No layer skipping or reversal

## Layers
- api/ → request handling only
- models/ → ORM schema source of truth
- schemas/ → Pydantic contracts
- services/ → business logic
- repositories/ → DB access only
- worker/ → ARQ jobs
- agents/ → LangGraph DAGs

## Database
- PostgreSQL + TimescaleDB + pgvector
- Schema defined in ORM models
- Migrations via Alembic ONLY

## Async Rules
- All DB access uses AsyncSession
- No sync SQLAlchemy
- CPU tasks → asyncio.to_thread()

## Background Jobs
- ARQ + Redis
- async def only
- separate worker service

## Storage
- MinIO (S3-compatible)
- Bucket: pheidipp-fit-files
- FIT parsing → asyncio.to_thread()

## Services
- api:8000
- worker
- postgres:5432
- redis:6379
- minio:9000

Rules:
- Frontend → API only
- Worker triggered via Redis

## Timescale / Hypertables

### Rule
Any table storing daily or time-series samples MUST be a TimescaleDB
hypertable. Standard tables are forbidden for time-series data.

### Currently implemented hypertables
(none yet — will be added as features are built)

### Planned hypertables (to be created when implementing these features)
- `activity_samples` (ts: `timestamp`) — per-second activity data
- `athlete_wellness` (ts: `metric_date`) — daily wellness metrics
- `athlete_fitness` (ts: `metric_date`) — daily fitness/form metrics

### Standard tables (not hypertables)
- `athlete_physiology` — versioned records with date ranges, not time-series

### Migration pattern for hypertables
Always in this exact sequence inside `upgrade()`:
1. `op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")`
2. `op.execute("CREATE EXTENSION IF NOT EXISTS vector;")`
3. `op.create_table(...)` — table creation
4. `op.execute("SELECT create_hypertable('table', 'ts_col', if_not_exists => TRUE);")`

## Configuration
- Environment variables only
- No hardcoded values

## Pydantic v2
- model_validate()
- model_dump()

## LLM Access (STRICT)
ONLY app.core.llm_router.get_llm()

Forbidden:
- Provider SDKs
- Custom retries
- Rate limiting logic
- Provider-specific configs
