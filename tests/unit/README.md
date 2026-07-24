# tests/unit/

## Purpose

Unit tests exercise individual service classes, pure helper functions, ORM column contracts, and enum ontologies in isolation. External services, repository interfaces, and service dependencies are mocked with `AsyncMock` or `MagicMock`. No real database connections are used — all persistence boundaries are replaced by mocks. These tests pin branching logic, error handling, and data contracts without the overhead of a live test DB.

## Contents

### Activity Pipeline
| File | Covers |
|---|---|
| `test_activity_columns.py` | Activity: ORM column contracts |
| `test_activity_ingestion_service.py` | ActivityIngestionService: pipeline orchestration, event publishing, idempotency |
| `test_activity_ingestion_service_signal_clean.py` | Signal-clean coupling during activity ingestion |
| `test_activity_repository_update_cleaning_version.py` | ActivityRepository: cleaning-version update logic |
| `test_fit_parser_service.py` | FitParserService: parse entry point, error handling |
| `test_run_ingestion_pipeline_docstring.py` | ActivityIngestionService: run_ingestion_pipeline docstring accuracy (sport_type_detected, activity_ingested, activity_calibration_eligible, EventPublisher, transactional outbox) |

### Athlete Profile
| File | Covers |
|---|---|
| `test_athlete_fitness_columns.py` | AthleteFitness: ORM column contracts |
| `test_athlete_profile_columns.py` | AthleteProfile: ORM column contracts |

### Physiology
| File | Covers |
|---|---|
| `test_athlete_physiology_columns.py` | AthletePhysiology: ORM column contracts, JSONB per-dimension storage |
| `test_athlete_physiology_repository_update_in_place.py` | PhysiologyRepository: update-in-place logic |
| `test_physiology_measurement_model.py` | PhysiologyMeasurement: model contract |
| `test_physiology_measurement_repository.py` | PhysiologyMeasurementRepository: persistence interface |
| `test_physiology_parameter_enum.py` | PhysiologyParameter: enum contract |
| `test_physiology_update_service_bayesian.py` | Bayesian posterior update logic |
| `test_physiology_update_service_orchestration.py` | Update orchestration branching |
| `test_physiology_update_service_pure_helpers.py` | Pure helper functions for update service |

### Coaching & Workouts
| File | Covers |
|---|---|
| `test_coaching_message_columns.py` | CoachingMessage: ORM column contracts |
| `test_coaching_repositories.py` | Repository append-only invariants (no update/delete) |
| `test_generated_workout_columns.py` | GeneratedWorkout: ORM column contracts |
| `test_generated_workout_repository.py` | GeneratedWorkoutRepository: persistence interface |
| `test_post_workout_agent.py` | PostWorkoutAgent: LLM-based post-workout analysis |
| `test_workout_generation_agent.py` | WorkoutGenerationAgent: idempotency, pre-conditions, LLM failure |
| `test_workout_step_columns.py` | WorkoutStep: ORM column contracts |
| `test_workout_step_repository.py` | WorkoutStepRepository: persistence interface |
| `test_workout_target_types.py` | WorkoutTargetType: enum contract |

### Plans
| File | Covers |
|---|---|
| `test_checkpoint_columns.py` | Checkpoint: ORM column contracts |
| `test_plan_generation_errors.py` | PlanGeneration: error types |
| `test_plan_generation_templates.py` | Plan generation template logic |
| `test_plan_router_layer_fix.py` | PlanQueryService: plan router delegates, no direct SQL (session.execute, select) in route handlers |
| `test_planned_session_columns.py` | PlannedSession: ORM column contracts |
| `test_planned_session_repository.py` | PlannedSessionRepository: persistence interface |
| `test_regeneration_task_columns.py` | RegenerationTask: ORM column contracts |
| `test_training_goal_columns.py` | TrainingGoal: ORM column contracts |
| `test_training_plan_columns.py` | TrainingPlan: ORM column contracts |

### Twin State
| File | Covers |
|---|---|
| `test_generation_event_columns.py` | GenerationEvent: ORM column contracts |
| `test_secondary_event_columns.py` | SecondaryEvent: ORM column contracts |
| `test_twin_context_assembler.py` | TwinContextAssembler: readiness, confidence, fitness-form descriptors |
| `test_twin_state_columns.py` | TwinState: ORM column contracts |
| `test_weekly_plan_columns.py` | WeeklyPlan: ORM column contracts |

### Auth & Onboarding
| File | Covers |
|---|---|
| `test_onboarding_errors.py` | Onboarding error types |
| `test_onboarding_service.py` | OnboardingService: pure helper functions (age, bootstrap, error mapping) |
| `test_password_hasher.py` | Password hashing (Argon2) |
| `test_token_service.py` | TokenService: JWT access tokens, opaque refresh tokens, verification |

### Signal & Threshold
| File | Covers |
|---|---|
| `test_signal_cleaning_object_storage.py` | Object storage signal cleaning |
| `test_signal_cleaning_service.py` | SignalCleaningService: branching logic |
| `test_threshold_detection_service.py` | ThresholdDetectionService: branching logic |

### Twin Recalibration
| File | Covers |
|---|---|
| `test_twin_recalibration_service.py` | TwinRecalibrationService |
| `test_twin_recalibration_service_calibration.py` | Calibration-specific logic |
| `test_twin_recalibration_service_calibration_pure_helpers.py` | Calibration pure helper functions |
| `test_twin_recalibration_service_event_firing.py` | Event-firing logic |
| `test_twin_recalibration_service_insert_if_not_exists.py` | Insert-if-not-exists logic |

### LLM & Agents
| File | Covers |
|---|---|
| `test_first_message_agent.py` | FirstMessageAgent: initial coaching message generation |
| `test_infer_data_tier.py` | Data-tier inference from LLM metadata |
| `test_prompt_registry.py` | PromptRegistry: template loading |

### Infrastructure & Utilities
| File | Covers |
|---|---|
| `test_compliance_service.py` | ComplianceService: session compliance checks |
| `test_context_budget_service.py` | Context budget computation |
| `test_enum_values.py` | Enum contract values across all schemas |
| `test_ip_utils.py` | IP address utilities |
| `test_load_computation_service.py` | Load computation service |
| `test_logging_utils.py` | Logging utilities |
| `test_object_storage_client.py` | ObjectStorageClient: MinIO interaction |

### System Event Outbox
| File | Covers |
|---|---|
| `test_event_catalogue_twin_model_ready_producer.py` | event-catalogue.md: twin_model_ready producer is OnboardingService, consumer is plan-generation path |
| `test_event_topology_plan_flow.py` | event-topology.md: plan generation event chain (twin_model_ready → training_plan_generated → coaching_message_generated), OnboardingService as producer |
| `test_outbox_publisher_registration.py` | OutboxPublisher: procrastinate task registration, periodic schedule interval |
| `test_outbox_publisher_service.py` | OutboxPublisherService: publish_pending signature, session ownership, get_pending delegation, mark_published iteration, no EventPublisher import, no message bus import, registered in __all__ |
| `test_outbox_publisher_worker_routing.py` | outbox_publisher worker: delegates to OutboxPublisherService, no direct repository/session, decorators preserved, error handling, count propagation |
| `test_system_event_md_no_redis.py` | system-event.md: zero Redis references, status transitioner pattern, future-bus insertion point, mermaid diagram, event catalogue/topology unchanged |

## Mock Boundaries

- External services (email, LLM providers, event publisher) and repository interfaces are mocked with `AsyncMock` for async methods and `MagicMock` for sync methods. See `tests/MOCKING_CONTRACT.md` for the authoritative per-layer table.
- No real database connections are used — unit tests rely on constructor-injected mocks for all persistence boundaries.
