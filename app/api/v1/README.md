# app/api/v1/

## Purpose
The public HTTP API surface for client applications. Every router in this folder is registered under the `/api/v1` prefix via `__init__.py`. Route modules delegate all business logic to services and agents; they own only request parsing, dependency wiring, error translation (domain exceptions → HTTP status codes), and transaction commit boundaries.

## Contents
### Auth
| File | Responsibility |
|---|---|
| `auth.py` | Athlete registration, login, and refresh-token rotation |

### Athlete
| File | Responsibility |
|---|---|
| `activity.py` | FIT file upload (stage + async ingest), activity list/detail, and post-workout analysis trigger/retrieval |
| `onboarding.py` | Onboarding completion (profile + preferences + goal + plan generation), profile/preferences CRUD, and twin-state read |

### Training
| File | Responsibility |
|---|---|
| `plan.py` | Read-only access to the active training plan, its sessions, upcoming sessions, and checkpoints |
| `workout.py` | Today's workout view (with auto-generation) and explicit per-session workout generation |

### Coach
| File | Responsibility |
|---|---|
| `coach.py` | First-message generation and paginated coaching message history |

### Infrastructure
| File | Responsibility |
|---|---|
| `health.py` | Kubernetes-style liveness (`/live`) and readiness (`/ready`) probes |

## Common Entry Points
- **Athlete onboarding**: `onboarding.py` → plan generation during `complete_onboarding`
- **Today's workout with auto-generation**: `workout.py` (GET `/today`) → auto-triggers `WorkoutGenerationAgent` on first view
- **Post-workout analysis**: `activity.py` (POST `/{activity_id}/analyse`) → `PostWorkoutAgent` → idempotent coaching message

## Architecture Notes
- All entity routes under `/athletes/{athlete_id}` enforce `require_self`: the JWT `athlete_id` must match the path parameter. Mismatches return 403, never 404, so authentication and authorization failures stay distinguishable.
- Every route module defines its own FastAPI `Depends` factories for agent and repository construction, keeping each endpoint a thin wrapper. Shared dependencies (`get_db`, `require_self`, `build_auth_service`, `build_onboarding_service`) live in `app/api/deps.py`.
- Transaction ownership mirrors the agent pattern: agent/service calls flush but never commit. Each route handler commits after receiving the result so all writes (ORM rows, outbox events) become durable atomically before the response is returned.
- Error mapping follows a consistent convention: catch the service-layer domain exception in the endpoint body and translate it to an `HTTPException` with a stable, non-technical detail string. Internal cause/traceback never leaves the service.
- `GET /plan/*` endpoints query repositories directly through `get_db` — no service class wraps the read path since it is read-only.

## Cross-References
- [Phase 1 Implementation docs](../../docs/implementation/phase-1/) — each router module references the specific phase BRD it implements
- [Stack Truth: Layer Architecture](../../../.opencode/instructions/001-stack-truth.md) — the api → services → repositories rule that constrains all route handlers
