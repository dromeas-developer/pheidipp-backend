# tests/integration/

## Purpose
Verifies that services, repositories, and ORM models interact correctly against a real
PostgreSQL test database. External APIs and the message bus are mocked, but the database
session, transaction boundaries, and constraint enforcement are exercised end-to-end through
the `db_session` fixture.

## Contents
### Authentication
| File | Covers |
|---|---|
| `test_auth_db.py` | Athlete email uniqueness (duplicate email IntegrityError pgcode 23505, case-insensitive matching via normalize_email before the functional lower(email) index fires) |

### Coaching & Workout
| File | Covers |
|---|---|
| `test_coaching_workout_db.py` | CoachingMessage (first_message singleton, post_workout singleton, post_workout null activity exempt, content empty rejected), GeneratedWorkout (unique plan+date, theoretical_targets not object, adjusted_targets null, recovery_modifier invalid), WorkoutStep (unique workout+step_order, physiological_intent NOT NULL, step_order < 1 rejected, description empty rejected, duration_seconds negative rejected, duration_seconds null accepted) |

### Coaching Agents
| File | Covers |
|---|---|
| `test_first_message_agent.py` | FirstMessageAgent: success path (message generated, row persisted, generation event success=true, outbox event), idempotency (409 on second call, LLM not called, no new generation event), LLM failure handling (timeout, connection error, 429 rate_limit, empty response, invalid output, no silent failures), content shape (exactly four paragraphs), athlete context (sport_background persisted in prompt, different backgrounds produce different contexts), precondition gates (no twin state→unavailable, no active goal→unavailable) |
| `test_workout_generation_agent.py` | WorkoutGenerationAgent: success path (workout generated, steps persisted with physiological_intent, one-indexed unique orders, non-empty description, outbox event, generation event with agent name), idempotency (existing returned when allow_existing=true, 409 when false, no new generation event), target type by data tier (T1 power, T3 gap, T5 description), two-column target structure (theoretical+adjusted NOT NULL, recovery_modifier=green, twin_state_id version), LLM failure handling (timeout, connection error, invalid JSON), precondition gates (unknown session→404), agent name consistency |

### Fitness & Physiology
| File | Covers |
|---|---|
| `test_fitness_physiology_db.py` | AthleteFitness (unique athlete_id, aggregate form invariant valid/invalid, dimensional form invariant valid/invalid/null-skips, time_constants.source validation), AthletePhysiology (unique athlete_id) |

### Onboarding & Profile Patch
| File | Covers |
|---|---|
| `test_onboarding_rollback.py` | TestOnboardingMidTransactionRollback (failure after physiology insert or fitness insert rolls back all entities + no outbox event; pre-onboarding profile state preserved) |
| `test_onboarding_service.py` | TestOnboardingAtomicCreate (6-entity transaction, onboarding_complete flag, data_tier on TwinState, profile enrichment, structural_risk_flag, goal ACTIVE), TestOnboardingTwinBootstrapValues (trigger=QUESTIONNAIRE, confidence=LOW, model_version=v1-questionnaire-bootstrap, fitness/fatigue/form=0, lt1<lt2<max_hr=184, metric_confidence only lt1/lt2_hr low, physiology max_hr=184, lt1/lt2 prior_weight=0.5, cp/vo2max null, time_constants population_default 42/7 21/3 56/14), TestOnboardingFailurePaths (re-onboarding 409, athlete not found 404, second active goal 409), TestOnboardingEventsPublished (onboarding_completed + twin_model_ready payloads, outbox PENDING, same transaction, generate_plan defer failure tolerated) |
| `test_profile_preferences_patch.py` | TestProfilePatchMutable (height_cm/location_lat_lng/training_window update, no-args no-op), TestProfilePatchImmutability (date_of_birth/sex/timezone/unknown rejected), TestPreferencesPatchMerge (day-level weekly_schedule merge, top-level overwrite, idempotent, unknown key silently ignored), TestPreferencesPatchSchema (partial weekday accepted, non-canonical weekday rejected, empty weekly_schedule accepted) |

### Profile, Preferences & Activity
| File | Covers |
|---|---|
| `test_profile_preferences_activity_db.py` | AthleteProfile (unique athlete_id), AthletePreferences (unique athlete_id, years_structured_training negative), Activity (external_id dedup, null external_id manual-entry exempt) |

### System Events
| File | Covers |
|---|---|
| `test_system_event_db.py` | SystemEvent (athlete_id NOT NULL) |

### Training Goal & Plan
| File | Covers |
|---|---|
| `test_plan_generation_service.py` | TestPlanGenerationGoalTypeValidation: generate_plan goal type validation (race_event, target_performance, unsupported type, no active goal, no twin state, no preferences, missing goal event date) · TestPlanSupersession: plan supersession (active plan superseded, superseded not deleted, sessions retain old plan id) · TestTargetPerformanceGapClassification: target performance gap classification (small, medium, large gap) · TestSessionStructureRules: session structure rules (no consecutive quality, long run recovery, threshold sandwiched, full duration) · TestCheckpointScheduling: checkpoint scheduling (calibration, benchmark week 4, progress review, race simulation, sorted) · TestPlanGenerationPurity: plan generation purity (no LLM calls, training_plan_generated event published) |
| `test_training_goal_plan_db.py` | TrainingGoal (single active per athlete, multiple inactive allowed, fitness_level range, weekly_volume_hours/km negative), WeeklyPlan (unique plan+week), Checkpoint (planned_session_id one-to-one) |

## Mock Boundaries
- External APIs and message bus are mocked; DB (test_pheidipp) is real — see `tests/MOCKING_CONTRACT.md` for the authoritative layer table
- Uses the `db_session` fixture from `tests/conftest.py` (function-scoped, auto-rollback + post-test truncation)
- No shared conftest.py at this level; fixtures are defined per-file
