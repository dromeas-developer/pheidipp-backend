# stack-truth

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
- worker/ → procrastinate jobs
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
- procrastinate (PostgreSQL-native async queue)
- async def only
- separate worker service
- No Redis; job state lives in PostgreSQL alongside application data

## Storage
- MinIO (S3-compatible)
- Bucket: pheidipp-fit-files
- FIT parsing → asyncio.to_thread()

## Services
- api:8000
- worker
- postgres:5432
- minio:9000
- litellm-proxy:4000

Rules:
- Frontend → API only
- Worker triggered via procrastinate (PostgreSQL-backed)

## List Endpoints (Non-Negotiable)
- list_* service methods MUST return `tuple[list[Model], int]` — items and total count together
- Route handlers MUST NOT call repositories directly for any reason, including counts
- Route handlers MUST NOT execute SQLAlchemy queries directly

## Timescale / Hypertables
- A table is a TimescaleDB hypertable candidate iff ALL THREE hold:
  1. Rows are samples taken at a fixed cadence (daily, hourly, per-second) — not triggered, not one-per-activity, not one-per-event.
  2. The row's value IS the measurement itself — not metadata, not a derived snapshot, not a versioned state.
  3. The dominant query is a time-windowed scan across many entities (fleet-wide), not a single-entity lookup or per-athlete pagination.
- Tables that MUST be hypertables: only those passing all three criteria. 
- Tables that are NOT hypertables despite having timestamps:
  - Versioned records with date ranges (`effective_from`/`effective_to`, `superseded_at` semantics) — standard tables.
  - Event/audit logs with mutable companion tables — standard tables.
  - One-row-per-activity metadata pointing at MinIO blobs — standard tables; the per-second samples live in MinIO, not PG.
  - Per-athlete feed pagination — standard tables; time-chunking hurts the dominant query.
  - Sparse high-value observations — standard tables.
  - Eventually-consistent async audit side-channels — standard tables.
  - Derived state recomputed against a hypertable — standard table (mutable, one row per athlete per signal).
- For the current authoritative registry of implemented and planned hypertables, use the dynamic codebase-state retrieval subagent (it queries the live codebase for `create_hypertable` calls and migration history).
- For the migration sequence see the alembic SKILL.

## Configuration
- Environment variables only
- No hardcoded values

## Pydantic v2
- model_validate()
- model_dump()

## LLM Access (STRICT)
All LLM calls route through the LiteLLM proxy. See ADR-007.

Agents construct an OpenAI-compatible client bound to the proxy:
`AsyncOpenAI(base_url=settings.LITELLM_BASE_URL, api_key=settings.LITELLM_API_KEY)`.
The proxy is the sole gateway to all providers; no agent or service
ever calls a provider API directly.

The proxy owns: provider routing, cross-provider retry, rate limiting,
message-history cleaning, and token/cost tracking. Agents do not
implement any of these — they call the proxy and record the result
in `GenerationEvent`.

Model names use the `<provider>/<model>` logical identifier
(e.g. `cohere/command-a-plus`); the proxy strips the provider prefix
when routing to the actual API.

Forbidden:
- Direct provider SDKs (OpenAI, Anthropic, Cohere, etc.) — use the
  OpenAI-compatible client against the proxy instead
- Custom retries, rate limiting, or circuit-breaker logic in agents
- Provider-specific configs or branching in agent code
- Bypassing the proxy by reading provider API keys directly