# app/repositories/

## Purpose
Persistence layer — each repository wraps a single database table (or closely related tables) and exposes read/write operations via `AsyncSession`. No business logic, no commits, no direct ORM session creation. Repositories `flush()` inside the caller's transaction and leave the commit boundary to the service layer.

## Contents
### Identity & Auth
| File | Responsibility |
|---|---|
| `athlete_auth_repository.py` | AthleteAuth: credential lookups by provider and email, last-login timestamp updates |
| `athlete_repository.py` | Athlete: by-id/by-email lookups, email-exists check, insert, and `IntegrityError` classification helper |
| `refresh_token_repository.py` | RefreshToken: append-only insert, token-hash lookup, IP-address retention sweep, and static `is_active` helper |

### Athlete Profile & Physiology
| File | Responsibility |
|---|---|
| `athlete_fitness_repository.py` | AthleteFitness: one-row-per-athlete Banister fitness/fatigue reads and inserts |
| `athlete_physiology_repository.py` | AthletePhysiology: one-row-per-athlete threshold posterior reads, inserts, and in-place JSONB column mutations |
| `athlete_preferences_repository.py` | AthletePreferences: one-row-per-athlete mutable training configuration reads and inserts |
| `athlete_profile_repository.py` | AthleteProfile: one-row-per-athlete demographic profile reads and inserts |
| `physiology_measurement_repository.py` | PhysiologyMeasurement: append-only insert and parameter-filtered observation history lookups |

### Training Plan
| File | Responsibility |
|---|---|
| `checkpoint_repository.py` | Checkpoint: bulk insert and plan-scoped joins through `PlannedSession → WeeklyPlan` |
| `planned_session_repository.py` | PlannedSession: read-only lookup by id and today-path join through `WeeklyPlan → TrainingPlan → TrainingGoal` |
| `training_goal_repository.py` | TrainingGoal: active-goal lookup, insert, and DB-enforced one-active-per-athlete invariant |
| `training_plan_repository.py` | TrainingPlan: active-plan lookups by goal/athlete, insert, and `supersede` in-place mutation |
| `weekly_plan_repository.py` | WeeklyPlan and WeeklySession: bulk insert and plan-scoped week/session catalog reads |

### Activity & Workout
| File | Responsibility |
|---|---|
| `activity_repository.py` | Activity: append-only insert, load-score/calibration/cleaning-version mutations, and date-filtered athlete lookups |
| `generated_workout_repository.py` | GeneratedWorkout: append-only insert and idempotency lookup by `(planned_session_id, generation_date)` |
| `raw_sensor_stream_repository.py` | RawSensorStream: append-only insert, one-to-one activity lookup, and exists check for cleaning-task idempotency |
| `twin_state_repository.py` | TwinState: append-only insert, latest-by-athlete, by-activity, and by-activity+trigger lookups |
| `workout_step_repository.py` | WorkoutStep: append-only batch insert and step-order-ordered workout lookup |

### Platform
| File | Responsibility |
|---|---|
| `coaching_message_repository.py` | CoachingMessage: append-only insert, type-filtered athlete feed, and per-activity idempotency lookups |
| `generation_event_repository.py` | GenerationEvent: append-only LLM audit log insert and per-athlete history feed |
| `system_event_outbox_repository.py` | SystemEventOutbox: insert, `get_pending` batch read, and `mark_published` mutation — only mutable event table per ADR-004 |
| `system_event_repository.py` | SystemEvent: append-only insert — always paired with `SystemEventOutboxRepository` in the same transaction |

## Architecture Notes
- Every repository accepts `AsyncSession` via `__init__`, stores it as `self.session`, and never creates a session or engine itself
- No repository method calls `commit()` — the service layer owns the transaction boundary. All writes `flush()` and `refresh()` only
- The `add`/`insert` convention: `session.add()`, `flush()`, `refresh()` — consistent across all repositories. Bulk variants (`add_many`, `insert_many`) flush once for the batch then refresh each row
- Append-only contracts (no `update`/`delete`): `CoachingMessageRepository`, `GeneratedWorkoutRepository`, `GenerationEventRepository`, `PhysiologyMeasurementRepository`, `RawSensorStreamRepository`, `TwinStateRepository`, `WorkoutStepRepository`
- `SystemEventRepository` and `SystemEventOutboxRepository` must be called in the same transaction (ADR-004 atomicity). Producers should use `app.services.event_publisher.publish_event` to guarantee this
- `SystemEventOutboxRepository.get_pending` is a read-only batch query (no flush, no commit) ordered by `created_at` so the outbox publisher transitions rows in insertion order, backed by `ix_system_event_outbox_status_created`
- `WeeklyPlanRepository` and `WeeklySessionRepository` coexist in `weekly_plan_repository.py` — they share the plan-generation transaction lifecycle
- `AthleteRepository.is_unique_violation` is a static helper for mapping PostgreSQL `23505` errors to application-level `409 Conflict` responses
- `RefreshTokenRepository.is_active` is a pure static function — no session dependency, safe to call after the transaction closes
- `AthletePhysiologyRepository` uses a module-level `UNSET_SENTINEL` to distinguish "caller omitted the argument" from "caller passed `None`" for nullable JSONB columns
- Several repositories use local imports inside method bodies to avoid circular import chains (e.g., `checkpoint_repository`, `planned_session_repository`, `training_plan_repository`, `weekly_plan_repository`)

## Cross-References
- [ADR-004: Event Persistence Atomicity](../docs/architecture/adr/ADR-004-system-events.md) — `SystemEventRepository` + `SystemEventOutboxRepository` paired-write invariant
- [ADR-005: Refresh Token IP Retention](../docs/architecture/adr/ADR-005-refresh-token-ip-retention.md) — `RefreshTokenRepository.discard_old_ips` storage-retention window
