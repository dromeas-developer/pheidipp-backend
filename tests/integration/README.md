# tests/integration/

## Purpose

Integration tests exercise service- and repository-layer code against a real PostgreSQL test database. External services (email, payment, LLM providers) are mocked; the database, ORM models, repositories, and internal service wiring are real. Tests assert transactional atomicity, event side-effects, and persistence invariants that cannot be validated at the unit layer.

## Contents

### Authentication & Onboarding
| File | Covers |
|---|---|
| `test_athlete_auth_primary_enforcement.py` | AthleteAuth: single-primary DB invariant enforced by partial unique index |
| `test_athlete_repositories.py` | Athlete + AthleteAuth: email uniqueness, is_unique_violation, password touches, email-provider join |
| `test_auth_service.py` | AuthService: register, login, rotate_refresh_token — transactional + event atomicity |
| `test_discard_refresh_token_ips.py` | IP-discard background task: idempotency, own transaction, retention_days override |
| `test_onboarding_service_integration.py` | OnboardingService: atomic seven-entity graph transaction + event/outbox rows |
| `test_onboarding_service_twin_model_ready.py` | OnboardingService: twin_model_ready event production, transactional atomicity, no direct PlanGenerationService call, generate_plan deferral, duplicate goal 409 |
| `test_refresh_token_repository.py` | RefreshTokenRepository: persistence, token rotation |

### Activity Pipeline
| File | Covers |
|---|---|
| `test_activity_endpoints.py` | Activity API: POST /upload, GET /activities, POST /analyse, GET /analysis |
| `test_activity_ingestion_signal_clean_enqueue_integration.py` | Signal-clean enqueue during activity ingestion |
| `test_activity_repository_cleaning_version_integration.py` | ActivityRepository: cleaning version update |
| `test_activity_schema.py` | Activity: ORM schema contract |

### Physiology
| File | Covers |
|---|---|
| `test_athlete_fitness_schema.py` | AthleteFitness: ORM schema contract |
| `test_athlete_physiology_repository_update_in_place_integration.py` | PhysiologyRepository: update-in-place semantics |
| `test_athlete_physiology_schema.py` | AthletePhysiology: ORM schema contract |
| `test_athlete_preferences_schema.py` | AthletePreferences: ORM schema contract |
| `test_athlete_profile_schema.py` | AthleteProfile: ORM schema contract |
| `test_physiology_measurement_repository_integration.py` | PhysiologyMeasurementRepository: persistence |
| `test_physiology_update_service_confidence_transitions_integration.py` | Confidence level transitions during update |
| `test_physiology_update_service_first_observation_integration.py` | First observation handling (bootstrap path) |
| `test_physiology_update_service_idempotency_integration.py` | Update idempotency across sessions |
| `test_physiology_update_service_integration.py` | PhysiologyUpdateService: end-to-end with real DB |

### Signal Cleaning & Threshold Detection
| File | Covers |
|---|---|
| `test_signal_clean_threshold_detection_defer_integration.py` | Signal cleaning → threshold detection deferral |
| `test_signal_cleaning_service_integration.py` | SignalCleaningService: end-to-end with real DB + object storage |
| `test_signal_cleaning_task_integration.py` | Signal cleaning background task integration |
| `test_threshold_detection_service_integration.py` | ThresholdDetectionService: end-to-end with real DB + object storage |
| `test_threshold_detection_task_integration.py` | Threshold detection background task integration |

### Plans, Workouts & Coaching
| File | Covers |
|---|---|
| `test_checkpoint_schema.py` | Checkpoint: ORM schema contract |
| `test_coach_endpoints.py` | Coach API endpoints |
| `test_coaching_message_schema.py` | CoachingMessage: ORM schema contract |
| `test_generate_first_message_task.py` | generate_first_message worker task: CoachingMessage creation, idempotency, FirstMessageAlreadyExistsError, LLM failure retry |
| `test_generate_plan_task.py` | generate_plan worker task: TrainingPlan creation, WeeklyPlans/PlannedSessions, generate_first_message deferral, idempotent supersession |
| `test_generated_workout_schema.py` | GeneratedWorkout: ORM schema contract |
| `test_generation_event_schema.py` | GenerationEvent: ORM schema contract |
| `test_plan_generation_service.py` | PlanGenerationService: phase sequences, non-overlapping date ranges, contiguity |
| `test_plan_query_service.py` | PlanQueryService: get_sessions_for_plan, get_upcoming_sessions, get_checkpoints_for_plan |
| `test_plan_repositories.py` | PlanRepository, WeeklyPlanRepository: persistence |
| `test_planned_session_schema.py` | PlannedSession: ORM schema contract |
| `test_regeneration_task_schema.py` | RegenerationTask: ORM schema contract |
| `test_secondary_event_schema.py` | SecondaryEvent: ORM schema contract |
| `test_training_goal_schema.py` | TrainingGoal: ORM schema contract |
| `test_training_plan_schema.py` | TrainingPlan: ORM schema contract |
| `test_twin_state_schema.py` | TwinState: ORM schema contract |
| `test_weekly_plan_schema.py` | WeeklyPlan: ORM schema contract |
| `test_workout_endpoints.py` | Workout API: GET /today, POST /generate-workout |
| `test_workout_step_schema.py` | WorkoutStep: ORM schema contract |

### Migrations
| File | Covers |
|---|---|
| `test_migration_phase_1_2a.py` | Phase-1.2a migration: hybrid table → hypertable data integrity |
| `test_migration_phase_1_2b.py` | Phase-1.2b migration: naming convention data integrity |
| `test_migration_phase_1_2c.py` | Phase-1.2c migration: athlete physiology data integrity |

### System Event Outbox
| File | Covers |
|---|---|
| `test_outbox_publisher_re_routed_integration.py` | OutboxPublisher re-routed: pending→published transition, idempotency, partial batch, no new events, no EventPublisher call, commit visibility, own transaction |
| `test_outbox_publisher_service_integration.py` | OutboxPublisherService: commit durability, transition count, empty queue, partial batch, idempotency |
| `test_outbox_publisher_task_integration.py` | OutboxPublisher: pending→published transition, idempotency, empty queue, partial batch, own transaction, commit visibility |
| `test_system_event_outbox_repository_get_pending_integration.py` | SystemEventOutboxRepository: get_pending returns pending ordered by created_at, excludes published/failed/dlq, respects limit, read-only, deterministic tiebreak |

### Regression
| File | Covers |
|---|---|
| `test_phase_1_1_registration_regression.py` | Phase-1.1 registration regression coverage |

## Mock Boundaries

- External services (email, payment, LLM providers, event publisher) are mocked; the database, internal services, and repositories are real. See `tests/MOCKING_CONTRACT.md` for the authoritative per-layer table.
- Task-body tests (e.g. `test_outbox_publisher_task_integration.py`, `test_discard_refresh_token_ips.py`) monkeypatch `AsyncSessionLocal` to `test_session_local` so the task session shares the test engine and event loop.
