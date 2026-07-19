# app/

## Purpose
Application root — the FastAPI entry point, environment configuration, and top-level package namespace. Every subfolder here enforces the stack-truth layer architecture: `api → services → repositories → models`, with `agents → services` and `worker → services`.

## Contents
### Application Bootstrap
| File | Responsibility |
|---|---|
| `config.py` | `Settings` — Pydantic `BaseSettings` loading all environment variables (database URL, JWT secrets, S3/MinIO credentials, LLM proxy config, procrastinate DSN) |
| `main.py` | FastAPI `app` instance — lifespan context manager, API router mounting, and OpenAPI/docs endpoint registration |

## Common Entry Points
- **Application startup**: `main.py` → `config.py` (settings) → `app.api.v1` (route registration)

## Architecture Notes
- `config.py` exposes a module-level `settings` singleton — all other modules import `from app.config import settings`. No other config loading pathway exists.
- `main.py` is the only FastAPI app instance in the codebase; route inclusion is centralized via `app.api.v1.api_router`.
- The `get_procrastinate_dsn()` helper in `config.py` strips SQLAlchemy `+driver` suffixes so procrastinate's `Psycopg2Connector` receives a bare `postgresql://` URL.
- Object storage configuration supports AWS S3, MinIO, and local filesystem fallback — controlled entirely via environment variables.

## Cross-References
- [stack-truth: Layer Architecture](../.opencode/instructions/001-stack-truth.md) — authoritative layer rules enforced by all subfolders
- [stack-truth: Configuration](../.opencode/instructions/001-stack-truth.md) — environment-variables-only rule
