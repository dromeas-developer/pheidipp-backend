# Phase 1e — Training Plan Generation: Full Test Coverage Plan

## Scope

This plan defines the full test coverage for the training plan generation feature, including:
- **Unit tests**: Isolated tests for models, enums, schemas, repositories, services, agent, prompt, and task.
- **Integration tests**: Database-backed tests for repositories, API endpoints, and model integrity.
- **Workflow tests**: End-to-end HTTP workflows covering onboarding-to-plan, retrieval, and archival.

All test files follow existing conventions: `tests/unit/` for unit tests, `tests/integration/` for integration and workflow tests. Factories are placed in `tests/factories/`.

---

## Factories

### 1. Create `TrainingPlanFactory`

- **Objective**: Provide factory functions for `TrainingPlan` model instances.
- **File**: `tests/factories/training_plan_factory.py` **[CREATE]**
- **Actions**:
  - Define `make_training_plan(athlete_id, **overrides)` returning a minimal valid `TrainingPlan` with `id`, `athlete_id`, `status=TrainingPlanStatus.ACTIVE`, `generation_metadata={}`, `created_at=datetime(2024, 1, 1)`
  - Define `make_training_plan_full(athlete_id, **overrides)` returning a fully populated `TrainingPlan` with all fields set including `training_block_id`, `plan_rationale`, `generation_metadata` containing methodology_profile, model, prompt_version
  - Define `make_training_plan_batch(n, athlete_id, **overrides)` returning a list of `n` training plans
  - Define `make_archived_training_plan(athlete_id, **overrides)` returning a plan with `status=TrainingPlanStatus.ARCHIVED` and `archived_at` set

### 2. Create `PlannedSessionFactory`

- **Objective**: Provide factory functions for `PlannedSession` model instances.
- **File**: `tests/factories/planned_session_factory.py` **[CREATE]**
- **Actions**:
  - Define `make_planned_session(training_plan_id, **overrides)` returning a minimal valid `PlannedSession` with `id`, `training_plan_id`, `scheduled_date=date(2024, 1, 15)`, `session_type=SessionType.EASY_RUN`, `dominant_physiological_intent=PhysiologicalIntent.LOW_AEROBIC`, `week_number=1`, `phase=TrainingPhase.BASE`, `created_at=datetime(2024, 1, 1)`
  - Define `make_planned_session_full(training_plan_id, **overrides)` returning a fully populated session with `target_duration_minutes`, `is_key_session=True`, `generation_metadata`
  - Define `make_planned_session_batch(n, training_plan_id, **overrides)` returning a list of `n` sessions
  - Define `make_week_sessions(training_plan_id, week_number, phase, day_assignments)` returning a list of sessions for a given week, where `day_assignments` is a dict mapping day names to session type strings

### 3. Update `tests/factories/__init__.py`

- **Objective**: Export new factory functions.
- **File**: `tests/factories/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export `make_training_plan`, `make_training_plan_full`, `make_training_plan_batch`, `make_archived_training_plan` from `tests.factories.training_plan_factory`
  - Import and export `make_planned_session`, `make_planned_session_full`, `make_planned_session_batch`, `make_week_sessions` from `tests.factories.planned_session_factory`
  - Add all new symbols to `__all__`

---

## Unit Tests — Enums

### 4. Test planning enum values and completeness

- **Objective**: Verify all new enums have correct values and are complete.
- **File**: `tests/unit/test_training_plan_enums.py` **[CREATE]**
- **Actions**:
  - Test `TrainingPlanStatus` has values `active` and `archived`
  - Test `TrainingPhase` has values `base`, `build`, `peak`, `taper`, `race`, `recovery`
  - Test `SessionType` has all 17 expected values including `rest`, `recovery_run`, `easy_run`, `long_run`, `vo2max`, etc.
  - Test `PhysiologicalIntent` has all 8 expected values
  - Test `MethodologyTrait` has all 10 expected values
  - Test all enums inherit from `str, enum.Enum`

---

## Unit Tests — Schemas

### 5. Test `plan_generation.py` schemas

- **Objective**: Verify all plan generation schemas validate correctly and reject invalid data.
- **File**: `tests/unit/test_plan_generation_schemas.py` **[CREATE]**
- **Actions**:
  - Test `MethodologyProfile` accepts valid `trait_weights` dict with `MethodologyTrait` keys and float values
  - Test `SessionAssignment` validates with all fields and defaults `is_key_session=False`, `target_duration_minutes=None`
  - Test `SessionAssignment` rejects invalid `session_type` values
  - Test `WeekPlan` validates with `week_number`, `phase`, `sessions` dict, and `week_rationale`
  - Test `WeekPlan` rejects non-lowercase day keys in sessions dict
  - Test `PlanBlueprint` validates with `weeks` list and `plan_rationale`
  - Test `PlanBlueprint` rejects empty `weeks` list
  - Test `PhaseArc` validates with `total_weeks`, `phases` list, and `recovery_weeks` list
  - Test `PhaseArcPhase` validates with `phase`, `start_week`, `end_week`
  - Test `ConstraintViolation` validates with required `rule` and `details` fields
  - Test `ValidationResult` validates with `is_valid` bool and optional `violations` list

### 6. Test `training_plan.py` schemas

- **Objective**: Verify API response schemas validate correctly.
- **File**: `tests/unit/test_training_plan_schemas.py` **[CREATE]**
- **Actions**:
  - Test `TrainingPlanBase` validates with all required fields and `from_attributes=True`
  - Test `PlannedSessionBase` validates with all required fields and `from_attributes=True`
  - Test `TrainingPlanResponse` validates with nested `training_plan` and `planned_sessions` list
  - Test `TrainingPlanListResponse` validates with `items` list and `total` int
  - Test `TrainingPlanListItem` validates with nested structures

---

## Unit Tests — Models

### 7. Test `TrainingPlan` model

- **Objective**: Verify `TrainingPlan` ORM model structure, defaults, and relationships.
- **File**: `tests/unit/test_training_plan_model.py` **[CREATE]**
- **Actions**:
  - Test `TrainingPlan` can be instantiated with minimal required fields (`athlete_id`)
  - Test `status` defaults to `TrainingPlanStatus.ACTIVE`
  - Test `generation_metadata` defaults to empty dict
  - Test `archived_at` is `None` by default
  - Test `planned_sessions` relationship is empty list by default
  - Test table name is `training_plans`
  - Test `__table_args__` contains the partial unique index and the composite index

### 8. Test `PlannedSession` model

- **Objective**: Verify `PlannedSession` ORM model structure and defaults.
- **File**: `tests/unit/test_planned_session_model.py` **[CREATE]**
- **Actions**:
  - Test `PlannedSession` can be instantiated with all required fields
  - Test `is_key_session` defaults to `False`
  - Test `generation_metadata` is `None` by default
  - Test table name is `planned_sessions`
  - Test `__table_args__` contains both indexes

---

## Unit Tests — Repositories

### 9. Test `TrainingPlanRepository`

- **Objective**: Verify repository methods against the test database.
- **File**: `tests/unit/test_training_plan_repository.py` **[CREATE]**
- **Actions**:
  - Test `create` instantiates and flushes a `TrainingPlan` returning the instance with `id` populated
  - Test `get_active_by_athlete` returns the active plan for a given athlete
  - Test `get_active_by_athlete` returns `None` when no active plan exists
  - Test `get_active_by_athlete` returns `None` when only archived plans exist
  - Test `get_active_by_athlete` returns only one plan when multiple active plans cannot exist (partial unique index enforcement)
  - Test `get_by_id` returns the plan by UUID
  - Test `get_by_id` returns `None` for non-existent ID
  - Test `archive_plan` sets `status` to `archived` and `archived_at` to current time
  - Test `archive_plan` returns `None` for non-existent plan ID
  - Test `archive_plan` on already-archived plan does not error

### 10. Test `PlannedSessionRepository`

- **Objective**: Verify repository methods against the test database.
- **File**: `tests/unit/test_planned_session_repository.py` **[CREATE]**
- **Actions**:
  - Test `create` instantiates and flushes a `PlannedSession` returning the instance
  - Test `list_by_plan` returns sessions ordered by `scheduled_date` ascending
  - Test `list_by_plan` returns empty list when no sessions exist for the plan
  - Test `bulk_create` creates multiple sessions in a single call and returns all instances with `id` populated
  - Test `bulk_create` with empty list returns empty list

---

## Unit Tests — Services

### 11. Test `PhaseArcComputer`

- **Objective**: Verify deterministic phase arc computation.
- **File**: `tests/unit/test_phase_arc_computer.py` **[CREATE]**
- **Actions**:
  - Test `compute` raises `ValueError` when `goal_event_date` is `None`
  - Test `compute` returns a `PhaseArc` with correct `total_weeks` for a marathon goal 16 weeks away
  - Test `compute` includes `BASE` phase starting at week 1 for plans >= 4 weeks
  - Test `compute` includes `TAPER` phase of 2 weeks for marathon/half_marathon/ultra goals
  - Test `compute` includes `TAPER` phase of 1 week for 5k/10k goals
  - Test `compute` includes `PEAK` phase when total weeks > 10
  - Test `compute` does not include `PEAK` phase when total weeks <= 10
  - Test `compute` generates recovery weeks every 3 weeks when `structural_capacity < 0.5`
  - Test `compute` generates recovery weeks every 4 weeks when `structural_capacity >= 0.5`
  - Test `compute` returns a compact single-phase plan when weeks_to_goal < 4
  - Test `compute` merges taper into build when total weeks <= 6
  - Test returned `PhaseArc` phases are contiguous (no gaps between end_week and next start_week)
  - Test returned `PhaseArc` last phase `end_week` equals `total_weeks`

### 12. Test `MethodologyProfileBuilder`

- **Objective**: Verify methodology weight derivation logic.
- **File**: `tests/unit/test_methodology_profile_builder.py` **[CREATE]**
- **Actions**:
  - Test `build` returns `MethodologyProfile` with all 10 `MethodologyTrait` keys present
  - Test marathon profile has `HIGH_AEROBIC_VOLUME` at 1.0 and `STRUCTURAL_DURABILITY` at 0.9
  - Test marathon profile with weeks < 12 has `CONSERVATIVE_PROGRESSION` at 1.0 and reduced `HIGH_AEROBIC_VOLUME`
  - Test half_marathon profile has elevated `THRESHOLD_DENSITY`
  - Test 5k/10k profile has `HIGH_INTENSITY_SPARSE` at 0.9 and `RACE_SPECIFICITY` at 1.0
  - Test ultra profile has `HIGH_AEROBIC_VOLUME` at 1.0, `STRUCTURAL_DURABILITY` at 1.0, `VARIETY_EMPHASIS` at 0.9
  - Test default profile (unknown event type) uses build phase weights
  - Test `training_age < 1` increases `CONSERVATIVE_PROGRESSION` and decreases `HIGH_INTENSITY_SPARSE`
  - Test `consistency_score < 0.6` increases `CONSERVATIVE_PROGRESSION`
  - Test `structural_capacity_score < 0.4` sets `STRUCTURAL_DURABILITY` and `LOW_INTENSITY_DOMINANT` to 1.0
  - Test `available_days >= 6` sets `HIGH_FREQUENCY` to 1.0
  - Test `available_days <= 4` sets `HIGH_FREQUENCY` to 0.4
  - Test all weights are normalized to <= 1.0
  - Test `build` with `None` event_type does not raise

### 13. Test `PlanGenerationBriefBuilder`

- **Objective**: Verify brief construction from domain objects.
- **File**: `tests/unit/test_plan_generation_brief_builder.py` **[CREATE]**
- **Actions**:
  - Test `build` returns `PlanGenerationBrief` with `brief_version="v1"`
  - Test `athlete_summary` contains `name`, `sport_background`, `years_structured_training`, `available_days_count`
  - Test `goal_summary` contains `goal_event_type`, `goal_event_name`, `goal_event_date`
  - Test `twin_summary` contains `fitness_score`, `structural_capacity_score`, `max_hr_estimate`, `confidence_level`, `data_tier`
  - Test `available_days` contains only days where `available=True` from preferences
  - Test `available_days` is empty dict when `weekly_schedule` is `None`
  - Test `explicit_constraints` contains all 8 constraint strings
  - Test `coaching_insights` contains `primary_methodology_trait` matching the highest-weighted trait
  - Test `methodology_profile` is passed through unchanged from input
  - Test `_count_available_days` returns correct count from preferences
  - Test `_build_available_days` returns empty dict when `weekly_schedule.days` is missing

### 14. Test `PlanConstraintValidator`

- **Objective**: Verify all hard constraint validation rules.
- **File**: `tests/unit/test_plan_constraint_validator.py` **[CREATE]**
- **Actions**:
  - Test `validate` returns `is_valid=True` for a blueprint with no violations
  - Test `validate` detects sessions on non-available days (`available_day_only` rule)
  - Test `validate` detects duplicate sessions per day (`no_duplicate_sessions_per_day` rule)
  - Test `validate` detects week phase not in phase arc (`phase_arc_alignment` rule)
  - Test `validate` detects back-to-back threshold sessions within a week (`no_back_to_back_intensity` rule)
  - Test `validate` detects back-to-back VO2max sessions within a week
  - Test `validate` allows threshold followed by easy_run (no false positive)
  - Test `validate` allows easy_run followed by threshold (no false positive)
  - Test `validate` detects more than 2 key sessions per week (`max_two_key_sessions` rule)
  - Test `validate` allows exactly 2 key sessions per week
  - Test `validate` detects recovery week with > 2 hard sessions (`recovery_week_density` rule)
  - Test `validate` allows recovery week with <= 2 hard sessions
  - Test `validate` detects long_run not followed by easy session (`long_run_recovery` rule)
  - Test `validate` allows long_run followed by rest
  - Test `validate` allows long_run followed by recovery_run
  - Test `validate` detects long_run followed by threshold session
  - Test `validate` detects medium_long_run not followed by easy session
  - Test `validate` handles long_run as last session in plan (no next day — no violation)
  - Test `validate` checks adjacency across week boundaries for long_run_recovery
  - Test `validate` returns all violations in a single pass (not just the first)
  - Test `ValidationResult.violations` contains correct `rule`, `week_number`, `day`, and `details` for each violation

### 15. Test `PlanRepairEngine`

- **Objective**: Verify deterministic repair logic.
- **File**: `tests/unit/test_plan_repair_engine.py` **[CREATE]**
- **Actions**:
  - Test `repair` returns original blueprint unchanged when `validation_result.is_valid=True`
  - Test `repair` converts second back-to-back threshold session to `easy_run` (`no_back_to_back_intensity` rule)
  - Test `repair` converts back-to-back VO2max session to `easy_run`
  - Test `repair` converts back-to-back tempo session to `easy_run`
  - Test `repair` removes session on non-available day (`available_day_only` rule)
  - Test `repair` removes `is_key_session` flag from excess key sessions beyond 2 (`max_two_key_sessions` rule)
  - Test `repair` keeps first 2 key sessions unchanged when removing excess
  - Test `repair` returns `None` for `long_run_recovery` violation (cannot insert sessions)
  - Test `repair` applies at most `MAX_REPAIR_ATTEMPTS` (1) repair
  - Test `repair` returns partially repaired blueprint when multiple violations exist but only one can be repaired
  - Test `repair` does not modify week topology or phase structure
  - Test `repair` does not alter `target_duration_minutes` when downgrading session type

### 16. Test `SESSION_TYPE_TO_DOMINANT_INTENT` mapping

- **Objective**: Verify the session type to physiological intent mapping is complete and correct.
- **File**: `tests/unit/test_session_type_intent_mapping.py` **[CREATE]**
- **Actions**:
  - Test `SESSION_TYPE_TO_DOMINANT_INTENT` contains all 17 `SessionType` values
  - Test `SessionType.REST` maps to `PhysiologicalIntent.RECOVERY_SUPPORT`
  - Test `SessionType.EASY_RUN` maps to `PhysiologicalIntent.LOW_AEROBIC`
  - Test `SessionType.LONG_RUN` maps to `PhysiologicalIntent.HIGH_AEROBIC`
  - Test `SessionType.THRESHOLD` maps to `PhysiologicalIntent.THRESHOLD`
  - Test `SessionType.VO2MAX` maps to `PhysiologicalIntent.VO2MAX`
  - Test `SessionType.RACE_SPECIFIC` maps to `PhysiologicalIntent.RACE_SPECIFIC`
  - Test `SessionType.STRIDES` maps to `PhysiologicalIntent.NEUROMUSCULAR`
  - Test `SessionType.TEST_SESSION` maps to `PhysiologicalIntent.CALIBRATION`
  - Test module raises `KeyError` at import time if any `SessionType` is missing from the mapping

### 17. Test `TrainingPlanService`

- **Objective**: Verify service orchestration logic with mocked dependencies.
- **File**: `tests/unit/test_training_plan_service.py` **[CREATE]**
- **Actions**:
  - Test `generate_plan` raises `ValueError` when athlete not found
  - Test `generate_plan` raises `ValueError` when preferences not found
  - Test `generate_plan` raises `ValueError` when training_block not found
  - Test `generate_plan` raises `ValueError` when twin_state not found
  - Test `generate_plan` calls `phase_arc_computer.compute` with correct arguments
  - Test `generate_plan` calls `methodology_profile_builder.build` with correct arguments including `event_type`, `weeks_to_goal`, `training_age`, `available_days`, `structural_capacity_score`, `adaptation_confidence_level`, `consistency_score`
  - Test `generate_plan` calls `brief_builder.build` with `methodology_profile` included
  - Test `generate_plan` calls `agent.generate` with `athlete_id` and `brief`
  - Test `generate_plan` raises `ValueError` when agent returns blueprint that fails `PlanBlueprint.model_validate`
  - Test `generate_plan` calls `validator.validate` with blueprint, available_days_map, and phase_arc
  - Test `generate_plan` calls `repair_engine.repair` when validation fails
  - Test `generate_plan` re-validates after repair and raises `ValueError` if still invalid
  - Test `generate_plan` calls `_instantiate_plan` when validation passes
  - Test `generate_plan` returns `TrainingPlanResponse` with plan and sessions
  - Test `_map_blueprint_to_sessions` derives correct dates from week_number and day strings
  - Test `_map_blueprint_to_sessions` maps `session_type` to `dominant_physiological_intent` via `SESSION_TYPE_TO_DOMINANT_INTENT`
  - Test `_map_blueprint_to_sessions` skips unknown day strings gracefully
  - Test `_instantiate_plan` creates `TrainingPlan` with `generation_metadata` containing `methodology_profile`, `phase_arc_version`, `validator_version`, and agent metadata
  - Test `_instantiate_plan` calls `planned_session_repo.bulk_create` with correct session data
  - Test `get_active_plan` returns `TrainingPlanResponse` when active plan exists
  - Test `get_active_plan` returns `None` when no active plan exists
  - Test `get_plan_by_id` returns `TrainingPlanResponse` when plan exists
  - Test `get_plan_by_id` returns `None` when plan does not exist
  - Test `archive_plan` calls `training_plan_repo.archive_plan` with correct plan_id
  - Test `_count_available_days` returns correct count from preferences.weekly_schedule
  - Test `_count_available_days` returns 0 when `weekly_schedule` is `None`
  - Test `_count_available_days` returns 0 when `weekly_schedule.days` is missing
  - Test `_build_response` correctly serializes plan and sessions into `TrainingPlanResponse`

---

## Unit Tests — Agent

### 18. Test `PlanGenerationAgent`

- **Objective**: Verify agent LLM interaction, parsing, validation, and error handling.
- **File**: `tests/unit/test_plan_generation_agent.py` **[CREATE]**
- **Actions**:
  - Test `generate` calls `client.chat.completions.create` with correct model, max_tokens, temperature=0.2, messages (system + user), and response_format json_object
  - Test `generate` returns tuple of `(blueprint_dict, metadata_dict)` on success
  - Test returned metadata contains `model`, `prompt_version`, `brief_version`, `outcome=success`, `input_tokens`, `output_tokens`, `latency_ms`, `stop_reason`
  - Test `generate` raises `ValueError` when agent returns empty content
  - Test `generate` raises `ValueError` when agent returns invalid JSON
  - Test `generate` raises `ValueError` when agent returns JSON that fails `PlanBlueprint.model_validate`
  - Test `generate` logs `MALFORMED` event when content is empty
  - Test `generate` logs `MALFORMED` event when JSON is invalid
  - Test `generate` logs `MALFORMED` event when schema validation fails
  - Test `generate` logs `SUCCESS` event on successful generation
  - Test `generate` catches `APITimeoutError`, logs `TIMEOUT` event, and re-raises
  - Test `generate` catches `APIStatusError` with status 429, logs `RATE_LIMITED` event, and re-raises
  - Test `generate` catches `APIStatusError` with non-429 status, logs `PROVIDER_ERROR` event, and re-raises
  - Test `generate` catches unexpected exceptions, logs `INTERNAL_ERROR` event, and re-raises
  - Test `generate` always calls `log_generation_event` before returning or raising
  - Test `generate` computes `latency_ms` using `time.monotonic()`
  - Test `_build_user_message` (from prompt module) serializes brief into JSON string containing athlete_summary, goal_summary, twin_summary, available_days, phase_arc, explicit_constraints, coaching_insights, and methodology_profile
  - Test `_build_user_message` converts `MethodologyTrait` enum keys to string values in methodology_profile trait_weights

---

## Unit Tests — Prompt

### 19. Test `plan_generation_v1.py` prompt registration

- **Objective**: Verify prompt is correctly registered in the registry.
- **File**: `tests/unit/test_plan_generation_prompt_v1.py` **[CREATE]**
- **Actions**:
  - Test importing `app.agents.prompts.plan_generation_v1` registers the prompt under agent `plan_generation` version `v1`
  - Test `PromptRegistry.get("plan_generation", "v1")` returns a `PromptRecord` with correct `system_prompt` and `max_output_tokens=4000`
  - Test `PromptRegistry.current("plan_generation")` resolves to `v1`
  - Test `SYSTEM_PROMPT` contains references to session types, constraints, methodology tendencies, and phase arc
  - Test `SYSTEM_PROMPT` mentions methodology tendencies as soft guidance not rigid rules

---

## Unit Tests — Task

### 20. Test `generate_training_plan` background task

- **Objective**: Verify task idempotency, data fetching, service construction, and error handling.
- **File**: `tests/unit/test_plan_generation_task.py` **[CREATE]**
- **Actions**:
  - Test task checks `uow.training_plans.get_active_by_athlete` first and returns early if active plan exists
  - Test task logs `MISSING_DATA` event and returns when athlete not found
  - Test task logs `MISSING_DATA` event and returns when preferences missing
  - Test task logs `MISSING_DATA` event and returns when training_block missing
  - Test task logs `MISSING_DATA` event and returns when twin_state missing
  - Test task calls `service.generate_plan` with `athlete_id` and `uow` when all data is present
  - Test task catches exceptions and does not re-raise
  - Test task closes session in `finally` block
  - Test task constructs `TrainingPlanService` with all required dependencies

---

## Unit Tests — Prompt Registry

### 21. Update prompt registry tests

- **Objective**: Verify `plan_generation` is registered in `CURRENT_VERSIONS`.
- **File**: `tests/unit/test_prompt_registry.py` **[MODIFY]**
- **Actions**:
  - Append test verifying `CURRENT_VERSIONS["plan_generation"] == "v1"`
  - Append test verifying `PromptRegistry.current("plan_generation")` returns the v1 prompt record

---

## Unit Tests — Unit of Work

### 22. Update UnitOfWork tests

- **Objective**: Verify UoW exposes `training_plans` and `planned_sessions` repositories.
- **File**: `tests/unit/test_unit_of_work.py` **[MODIFY]**
- **Actions**:
  - Append test verifying `uow.training_plans` returns a `TrainingPlanRepository` instance
  - Append test verifying `uow.planned_sessions` returns a `PlannedSessionRepository` instance

---

## Integration Tests — API

### 23. Test training plan API endpoints

- **Objective**: Verify HTTP endpoints for plan retrieval.
- **File**: `tests/integration/test_training_plans_api.py` **[CREATE]**
- **Actions**:
  - Test `GET /athletes/{athlete_id}/training-plans/active` returns 404 when no active plan exists
  - Test `GET /athletes/{athlete_id}/training-plans/active` returns 200 with `TrainingPlanResponse` when active plan exists
  - Test `GET /athletes/{athlete_id}/training-plans/active` response includes `training_plan` and `planned_sessions` fields
  - Test `GET /athletes/{athlete_id}/training-plans/{plan_id}` returns 404 when plan does not exist
  - Test `GET /athletes/{athlete_id}/training-plans/{plan_id}` returns 403 when plan belongs to a different athlete
  - Test `GET /athletes/{athlete_id}/training-plans/{plan_id}` returns 200 with correct plan when plan belongs to athlete
  - Test `GET /athletes/{athlete_id}/training-plans/{plan_id}` returns planned sessions ordered by `scheduled_date`

---

## Integration Tests — Model Integrity

### 24. Test training plan model integrity

- **Objective**: Verify database-level constraints and relationships.
- **File**: `tests/integration/test_training_plan_model_integrity.py` **[CREATE]**
- **Actions**:
  - Test partial unique index prevents two active plans for the same athlete (database-level enforcement)
  - Test an athlete can have one active and one archived plan simultaneously
  - Test `CASCADE` delete on `training_plans.athlete_id` deletes plan when athlete is deleted
  - Test `CASCADE` delete on `planned_sessions.training_plan_id` deletes sessions when plan is deleted
  - Test `SET NULL` on `training_plans.training_block_id` sets to NULL when training block is deleted
  - Test `planned_sessions` relationship orders sessions by `scheduled_date` ascending
  - Test `TrainingPlan` and `PlannedSession` can be created and queried via async session
  - Test indexes exist on `training_plans` for `athlete_id` and `athlete_id, created_at`
  - Test indexes exist on `planned_sessions` for `training_plan_id, scheduled_date` and `training_plan_id, week_number`

---

## Integration Tests — Onboarding Trigger

### 25. Test onboarding triggers plan generation

- **Objective**: Verify onboarding endpoint queues the plan generation background task.
- **File**: `tests/integration/test_onboarding_plan_generation.py` **[CREATE]**
- **Actions**:
  - Test completing onboarding adds `generate_training_plan` to `BackgroundTasks`
  - Test onboarding still triggers `generate_first_coach_message` alongside `generate_training_plan`
  - Test onboarding response does not include plan data (plan generation is async)

---

## Workflow Tests

### 26. Test full onboarding-to-plan-generation workflow

- **Objective**: End-to-end test of athlete creation through plan generation via HTTP.
- **File**: `tests/integration/test_workflows.py` **[MODIFY]**
- **Actions**:
  - Append test class `TestTrainingPlanWorkflow` with test `test_onboarding_triggers_plan_generation` that:
    - Creates athlete via `POST /athletes/`
    - Creates profile via `PUT /athletes/{id}/profile`
    - Completes onboarding via `POST /athletes/{id}/onboarding` with valid preferences and training_block
    - Verifies onboarding response is 201
    - Polls `GET /athletes/{id}/training-plans/active` until plan is available (with timeout and retry)
    - Verifies returned plan has `status=active`, non-empty `planned_sessions`, and `generation_metadata` containing `methodology_profile`
    - Verifies planned sessions have correct `session_type`, `dominant_physiological_intent`, `week_number`, and `phase` values
    - Verifies session count matches expected number from the blueprint

### 27. Test plan retrieval and archival workflow

- **Objective**: End-to-end test of plan retrieval and archival.
- **File**: `tests/integration/test_workflows.py` **[MODIFY]**
- **Actions**:
  - Append test `test_plan_retrieval_and_archival_workflow` that:
    - Creates an athlete with an existing training plan (via direct DB insert or by triggering onboarding)
    - Retrieves active plan via `GET /athletes/{id}/training-plans/active` and verifies 200
    - Retrieves plan by ID via `GET /athletes/{id}/training-plans/{plan_id}` and verifies 200
    - Archives the plan via direct DB update (or API if endpoint exists) — note: no archive API endpoint exists yet, so use DB
    - Verifies `GET /athletes/{id}/training-plans/active` returns 404 after archival
    - Creates a new plan for the same athlete (via direct DB insert)
    - Verifies `GET /athletes/{id}/training-plans/active` returns the new plan

### 28. Test plan idempotency workflow

- **Objective**: Verify that triggering plan generation twice does not create duplicate active plans.
- **File**: `tests/integration/test_workflows.py` **[MODIFY]**
- **Actions**:
  - Append test `test_plan_generation_idempotency` that:
    - Creates an athlete with all required onboarding data
    - Triggers onboarding (which queues plan generation)
    - Waits for plan to be generated
    - Triggers onboarding a second time (simulating duplicate call)
    - Verifies only one active plan exists via `GET /athletes/{id}/training-plans/active`
    - Verifies the plan ID is the same as the first generation

---

## Integration Tests — Dependencies

### 29. Test `get_training_plan_service` dependency factory

- **Objective**: Verify the dependency factory correctly instantiates all service components.
- **File**: `tests/integration/test_dependency_factories.py` **[MODIFY]**
- **Actions**:
  - Append test verifying `get_training_plan_service` returns a `TrainingPlanService` instance
  - Append test verifying the service has all dependencies instantiated (repos, computers, builders, validator, repair_engine, agent)

---

## Migration

### 30. No migration test changes required

- **Objective**: The migration for training plan tables was already created in the implementation plan. No additional migration test steps needed.
- **Note**: The existing `test_db_engine` fixture in `conftest.py` runs Alembic migrations automatically, so all integration and workflow tests will run against the migrated schema.
