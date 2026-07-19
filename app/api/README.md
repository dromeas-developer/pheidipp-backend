# app/api/

## Purpose
Request-handling layer for Pheidipp's REST API. All endpoints under `/api/v1` are assembled from feature routers in `app/api/v1/` and aggregated into a single `APIRouter`. This layer owns HTTP concerns exclusively — it translates domain exceptions into status codes, injects dependencies via FastAPI `Depends`, and delegates all business logic to the service layer.

## Contents
| File | Responsibility |
|---|---|
| `deps.py` | Shared FastAPI dependency factories: `get_db`, `get_current_athlete_id`, `require_self`, and service builders (`build_auth_service`, `build_onboarding_service`, `build_onboarding_service_with_plan`). |

## Architecture Notes
- All athlete-scoped endpoints under `v1/` depend on `require_self`, which compares the JWT `athlete_id` against the path parameter and raises 403 (not 404) on mismatch, keeping authentication and authorization failures distinguishable.
- The `v1/` subdirectory contains per-domain routers (`auth.py`, `onboarding.py`, `plan.py`, `coach.py`, `workout.py`, `activity.py`, `health.py`) aggregated in `v1/__init__.py` under the `/api/v1` prefix.
- Transaction ownership lives in route handlers: agents and services flush but do not commit. Each handler calls `session.commit()` after the service/agent returns, ensuring all writes become durable atomically before the response is sent.
- Dependency factories are defined per-router-module (e.g. `build_post_workout_agent` in `activity.py`) rather than in `deps.py`, keeping router-specific wiring co-located with its endpoints.

## Cross-References
- [ADR-001: Layer Architecture](../docs/adr/001-layer-architecture.md) — the `api → services` boundary this folder enforces
- [stack-truth: Layer Architecture](../../.opencode/instructions/001-stack-truth.md) — authoritative layer rules
