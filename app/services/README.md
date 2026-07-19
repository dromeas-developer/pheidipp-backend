# app/services/

## Purpose
Business-logic layer — the single owner of domain rules, multi-step workflows, and transactional orchestration. Services call repositories for persistence (never directly for reads outside their own transaction), invoke agents for LLM work, and coordinate cross-entity operations within a single `AsyncSession`. No service creates its own session or engine — the caller provides both.

## Contents
### Auth
| File | Responsibility |
|---|---|
| `auth_errors.py` | Domain exceptions: `DuplicateEmailError`, `InvalidCredentialsError`, `InvalidRefreshTokenError` |
| `auth_results.py` | Frozen dataclasses: `AuthResult`, `IssuedTokens` |
| `auth_service.py` | Register, login, refresh-token rotation with transactional outbox events per ADR-004 |

### Onboarding & Profile
| File | Responsibility |
|---|---|
| `onboarding_errors.py` | Domain exceptions: `OnboardingAlreadyCompleteError`, `TrainingGoalConflictError`, `InvalidGoalTypeError` |
| `onboarding_results.py` | Frozen dataclasses: `OnboardingResult`, `OnboardingStatus`, profile/twin snapshots |
| `onboarding_service.py` | Atomic onboarding transaction (profile + preferences + goal + plan generation + twin bootstrap + outbox) |

### Activity Ingestion Pipeline
| File | Responsibility |
|---|---|
| `activity_ingestion_service.py` | Two-phase FIT upload pipeline: stage (API-side) and async ingest (worker-side: parse → load → recalibrate → event) |
| `calibration_eligibility_service.py` | Gate activities for twin recalibration — Phase 1.6 hard-wired to `false`; full five-rule evaluation deferred to Phase 2 |
| `compliance_service.py` | Compare actual session to prescribed session — computes `duration_delta_pct` and `session_type_match` for post-workout agent |
| `fit_parser_service.py` | Extract raw HR/power/GPS records from FIT files via `fitparse`, returning `ParsedFitData` with signal-availability flags |
| `load_computation_service.py` | HR-only heuristic load formula (`aerobic_load`) from raw HR records — `neuromuscular_load` and `structural_load` deferred |

### Twin & Physiology
| File | Responsibility |
|---|---|
| `physiology_update_service.py` | Bayesian update of `AthletePhysiology` posterior state from threshold observations with confidence-transition events |
| `signal_cleaning_service.py` | Seven-step signal-cleaning pipeline (artifact removal, smoothing, derived metrics, rolling features) for raw sensor streams |
| `threshold_detection_service.py` | HR deflection, RR inflection, and power-to-HR ratio threshold detection for calibration-eligible running activities |
| `twin_context_assembler.py` | Translate raw `TwinState` fields into coaching-language descriptors for agent context assembly |
| `twin_recalibration_service.py` | Banister fitness/fatigue update + append-only `TwinState` snapshot after each ingested activity |

### Plan Generation
| File | Responsibility |
|---|---|
| `plan_generation_errors.py` | Domain exceptions: `PlanGenerationError`, `TrainingLengthGateError` |
| `plan_generation_service.py` | Deterministic plan generation (pure Python, no LLM) — phase allocation, weekly session synthesis, supersession of prior plans |
| `plan_generation_templates.py` | Fixed template constants: phase proportions, training-length-gate thresholds, session distribution, quality-session classification |

### Workout Generation
| File | Responsibility |
|---|---|
| `workout_generation_agent.py` | `WorkoutGenerationAgent` — idempotent day-of workout generation with LLM step synthesis and GenerationEvent audit |
| `workout_generation_errors.py` | Domain exceptions: `PlannedSessionNotFoundError`, `WorkoutAlreadyGeneratedError`, `LLMServiceUnavailableError` |
| `workout_target_types.py` | Canonical `SESSION_INTENT_MAP` (SessionType → PhysiologicalIntent) and `DATA_TIER_TARGET_TYPE` (DataTier → signal_type) |

### Coach Agents
| File | Responsibility |
|---|---|
| `first_message_agent.py` | `FirstMessageAgent` — idempotent onboarding coach message generation with context-budget enforcement |

### Platform
| File | Responsibility |
|---|---|
| `context_budget_service.py` | Token-budget enforcement for LLM agents — structured context assembly with priority-weighted truncation |
| `event_publisher.py` | `EventPublisher` — atomically writes `SystemEvent` + `SystemEventOutbox` in the caller's transaction |
| `health_service.py` | Database connectivity check for Kubernetes readiness probe |
| `object_storage_client.py` | S3-compatible object storage client for FIT files — supports AWS S3, MinIO, and local filesystem fallback |

## Common Entry Points
- **Athlete registration**: `auth_service.py` (register) → creates Athlete + AthleteAuth + AthleteProfile + RefreshToken + outbox event
- **Onboarding completion**: `onboarding_service.py` (complete_onboarding) → `plan_generation_service.py` (generate_plan) → atomic transaction with outbox event
- **FIT file ingestion (async)**: `activity_ingestion_service.py` (ingest_async) → `fit_parser_service.py` → `load_computation_service.py` → `calibration_eligibility_service.py` → `twin_recalibration_service.py` → `event_publisher.py`
- **Post-workout analysis**: `compliance_service.py` → `post_workout_agent.py` → `event_publisher.py`
- **Signal cleaning pipeline**: `signal_cleaning_service.py` (clean) → steps 1–4 in fixed order → `threshold_detection_service.py` (detect) → `physiology_update_service.py` (update)

## Architecture Notes
- Services own the transaction boundary: they call `commit()` after all writes are flushed. Agents and repositories flush but never commit.
- Domain exceptions follow a per-subsystem pattern: `*_errors.py` for exception types, `*_results.py` for frozen dataclass return values. Exceptions map to HTTP status codes at the API layer.
- `EventPublisher` must be called in the same transaction as the producing domain writes (ADR-004 atomicity). All service methods that produce events inject `EventPublisher` via constructor.
- `PlanGenerationService` is pure Python — no LLM, no external API calls. Templates live in `plan_generation_templates.py` for isolated unit testing.
- `ObjectStorageClient` is constructed once per process via `get_object_storage_client()` and reused — the underlying `boto3.client` is thread-safe.
- Several services accept repositories via TYPE_CHECKING imports to avoid circular import chains (e.g., `ContextBudgetService`, agents).

## Cross-References
- [ADR-004: Event Persistence Atomicity](../../docs/architecture/adr/ADR-004-system-events.md) — `EventPublisher` paired-write invariant
- [ADR-005: Refresh Token IP Retention](../../docs/architecture/adr/ADR-005-refresh-token-ip-retention.md) — `RefreshTokenRepository` IP sweep
- [ADR-007: LLM Provider Gateway](../../docs/architecture/adr/ADR-007-llm-provider-gateway.md) — LiteLLM proxy access pattern in all agent services
