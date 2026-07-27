# Memory

## Project Overview
See @README.md for project overview and @package.json for available npm/pnpm commands for this project.

## MCP — pheidipp-codebase-context
Configured at `.mcp.json`. 68 tools across 8 domains + 5 cross-domain orchestrators.
Use these for codebase research, architecture lookups, and documentation retrieval
instead of raw file reads or grep where possible.

**Core (10):** `search_codebase`, `get_files`, `find_files`, `grep_files`,
`search_symbols`, `reindex`/`reindex_code`, `refresh_code`, `check_index_health`,
`get_index_stats`

**Architecture (10):** `search_architecture`, `search_invariants`, `list_entities`,
`get_entity_context`, `get_event_context`, `get_related_contracts`,
`get_computation_pipeline`, `get_agent_dependencies`, `reindex_architecture`,
`refresh_architecture`

**Vision (5):** `search_vision`, `list_vision_entities`, `get_vision_context`,
`reindex_vision`, `refresh_vision`

**Release Plan (7):** `search_release_plan`, `list_release_plan_phases`,
`list_release_plan_features`, `get_phase_context`, `get_feature_context`,
`reindex_release_plan`, `refresh_release_plan`

**ADR (7):** `search_adr`, `list_adrs`, `get_adr_context`, `get_adrs_for_entity`,
`get_related_adrs`, `reindex_adr`, `refresh_adr`

**Implementation (7):** `search_implementation`, `list_implementation_batches`,
`get_batch_context`, `get_entity_implementation_status`, `list_implementation_findings`,
`reindex_implementation`, `refresh_implementation`

**Testing (5):** `search_testing`, `list_test_packs`, `get_test_pack_context`,
`reindex_testing`, `refresh_testing`

**Code — AST (12):** `list_modules`, `list_classes`, `list_functions`, `list_imports`,
`get_class_context`, `get_function_context`, `get_module_context`, `get_module_docs`,
`get_module_deps`, `get_importers`, `get_dependency_chain`, `multi_code_query`

**Orchestrators (5):** `multi_search`, `multi_context`, `get_change_impact`,
`get_code_for_entity`, `get_arch_for_code`

## Stack Truth

### Runtime
Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2

### Layer Architecture (Non-Negotiable)
api → services → repositories → models
agents → services
worker → services
- No business logic in api
- No direct repository access outside services
- No layer skipping or reversal

### Layers
- api/ → request handling only
- models/ → ORM schema source of truth
- schemas/ → Pydantic contracts
- services/ → business logic
- repositories/ → DB access only
- worker/ → procrastinate jobs
- agents/ → LangGraph DAGs

### Database
- PostgreSQL + TimescaleDB + pgvector
- Schema defined in ORM models
- Migrations via Alembic ONLY

### Async Rules
- All DB access uses AsyncSession
- No sync SQLAlchemy
- CPU tasks → asyncio.to_thread()

### Background Jobs
- procrastinate (PostgreSQL-native async queue)
- async def only, separate worker service
- No Redis; job state lives in PostgreSQL alongside application data

### Storage
- MinIO (S3-compatible), bucket: pheidipp-fit-files
- FIT parsing → asyncio.to_thread()

### Services
- api:8000, worker, postgres:5432, minio:9000, litellm-proxy:4000
- Frontend → API only. Worker triggered via procrastinate.

### List Endpoints (Non-Negotiable)
- list_* service methods MUST return `tuple[list[Model], int]` (items + total)
- Route handlers MUST NOT call repositories directly for any reason
- Route handlers MUST NOT execute SQLAlchemy queries directly

### Timescale / Hypertables
A table is a hypertable candidate iff ALL THREE hold:
1. Rows are samples at a fixed cadence (daily, hourly, per-second)
2. The row's value IS the measurement itself
3. Dominant query is a time-windowed scan across many entities

### Configuration
- Environment variables only. No hardcoded values.

### Pydantic v2
- model_validate(), model_dump()

### LLM Access (STRICT)
All LLM calls route through LiteLLM proxy (see ADR-007). Use
`AsyncOpenClient(base_url=settings.LITELLM_BASE_URL, api_key=settings.LITELLM_API_KEY)`.
Forbidden: direct provider SDKs, custom retries/rate-limiting, provider-specific configs.

## Code Style
- Use descriptive variable names
- Extract complex conditions into meaningful boolean variables
- No inline comments unless code is genuinely surprising
- No docstrings that restate the function/class name
- Merge new imports into existing import blocks (no duplicate `from X import` lines)
- `__table_args__` after column definitions, before relationships

## Agent Behaviour Rules
- Tool Pre-Validation: confirm tool exists, required fields present, types match exactly, native structures not JSON strings
- Batching: batch independent reads/searches into one call. Never call the same tool twice in a row for different inputs.
- Truncation: expected — don't re-fetch. Note assumption and continue.
- Edit Discipline: read before editing, targeted edits, no full rewrites on existing files
- One logical change per edit call. Consolidate same-file edits across steps.
- Complete task → STOP. No unsolicited follow-ups or speculative improvements.
- Prefer simplest valid solution. No new abstractions unless required.
- NEVER run system commands directly if a `scripts/` wrapper exists.
