# Phase 1e — LLM-Guided Training Plan Generation

## Final Implementation Plan

---

## Analysis of Draft Plan Violations

| # | Violation | Severity | Resolution in this plan |
|---|-----------|----------|------------------------|
| 1 | LLM access uses `app.core.llm.get_litellm_client()` directly; stack-truth mandates `app.core.llm_router.get_llm()` | High | Create `app/core/llm_router.py` wrapper; new agent uses it |
| 2 | `TrainingPlan.goal_event_id` references non-existent field; existing domain uses `training_block_id` | High | Use `training_block_id` FK instead |
| 3 | `TrainingPlan` status enum undefined | High | Create `TrainingPlanStatus` enum |
| 4 | `SessionType`, `PhysiologicalIntent`, `TrainingPhase` enums undefined | High | Create all three in `app/models/enums.py` |
| 5 | `PlannedSession.phase` references `TrainingPhase` which does not exist | High | Create `TrainingPhase` enum |
| 6 | `PlanBlueprint`, `WeekPlan`, `SessionAssignment` schemas have no file location | Medium | Create `app/schemas/plan_generation.py` |
| 7 | No repository files specified for new domain entities | Medium | Create dedicated repository files |
| 8 | No service files specified for `PhaseArcComputer`, `Validator`, `RepairEngine`, `Instantiator` | Medium | Create dedicated service files |
| 9 | No agent file, prompt file, or registry entry specified | Medium | Create all three |
| 10 | No background task file specified | Medium | Create `app/tasks/plan_generation_task.py` |
| 11 | No API routes specified for plan retrieval | Medium | Create `app/api/routes/training_plans.py` |
| 12 | `UnitOfWork` missing `training_plans` and `planned_sessions` repositories | High | Modify `app/core/unit_of_work.py` |
| 13 | Onboarding route not wired to trigger plan generation | High | Modify `app/api/routes/athletes.py` |
| 14 | `Athlete` and `TrainingBlock` models missing relationships to `TrainingPlan` | Medium | Add relationships |
| 15 | `plan_metadata` field name inconsistent with existing `generation_metadata` pattern | Low | Use `generation_metadata` JSONB |
| 16 | `llm_model`, `prompt_version` as top-level fields inconsistent with `CoachMessage` pattern | Low | Nest inside `generation_metadata` |
| 17 | Draft mixes agent output schemas with API schemas without separation | Low | Separate into `app/schemas/plan_generation.py` and `app/schemas/training_plan.py` |
| 18 | `SportBackground` enum exists as `preferences.sport_background`; draft uses `training_background` | Low | Use existing `SportBackground` enum |

---

## Models

### 1. Add planning enums to `app/models/enums.py`

- **Objective**: Define all enums required by the planning domain.
- **File**: `app/models/enums.py` **[MODIFY]**
- **Actions**:
  - Append `TrainingPlanStatus` string enum with values: `active`, `archived`
  - Append `TrainingPhase` string enum with values: `base`, `build`, `peak`, `taper`, `race`, `recovery`
  - Append `SessionType` string enum with values: `rest`, `recovery_run`, `easy_run`, `long_run`, `medium_long_run`, `steady_state`, `tempo`, `threshold`, `vo2max`, `hill_repeats`, `fartlek`, `race_specific`, `strides`, `drills_mobility`, `cross_training`, `test_session`, `optional_run`
  - Append `PhysiologicalIntent` string enum with values: `low_aerobic`, `high_aerobic`, `threshold`, `vo2max`, `race_specific`, `neuromuscular`, `recovery_support`, `calibration`
  - **NEW**: Append `MethodologyTrait` string enum with values: `HIGH_AEROBIC_VOLUME`, `LOW_INTENSITY_DOMINANT`, `THRESHOLD_DENSITY`, `HIGH_INTENSITY_SPARSE`, `HIGH_FREQUENCY`, `STRUCTURAL_DURABILITY`, `RACE_SPECIFICITY`, `VARIETY_EMPHASIS`, `NEUROMUSCULAR_SUPPORT`, `CONSERVATIVE_PROGRESSION`

### 2. Create `TrainingPlan` model

- **Objective**: Persist versioned training-plan containers.
- **File**: `app/models/training_plan.py` **[CREATE]**
- **Actions**:
  - Define `TrainingPlan` ORM class with tablename `training_plans`
  - Columns: `id` (UUID, PK, server_default gen_random_uuid), `athlete_id` (UUID, FK athletes.id ondelete CASCADE, index, nullable=False), `training_block_id` (UUID, FK training_blocks.id ondelete SET NULL, nullable=True, index), `status` (TrainingPlanStatus enum, default active, nullable=False), `created_at` (DateTime tz, server_default func.now), `archived_at` (DateTime tz, nullable=True), `generation_metadata` (JSONB, nullable=False, default empty dict), `plan_rationale` (Text, nullable=True)
  - Relationship: `athlete` many-to-one back_populates `training_plans`
  - Relationship: `training_block` many-to-one
  - Relationship: `planned_sessions` one-to-many back_populates `training_plan`, cascade all delete-orphan, order_by `PlannedSession.scheduled_date.asc()`
  - Table args: partial unique index on `(athlete_id)` where `status = 'active'` named `uq_training_plans_active_per_athlete`; index on `(athlete_id, created_at)`
  - **NEW**: Ensure `generation_metadata` includes `methodology_profile` key for storing `MethodologyProfile.trait_weights`

### 3. Create `PlannedSession` model

- **Objective**: Persist individual planned training sessions.
- **File**: `app/models/planned_session.py` **[CREATE]**
- **Actions**:
  - Define `PlannedSession` ORM class with tablename `planned_sessions`
  - Columns: `id` (UUID, PK, server_default gen_random_uuid), `training_plan_id` (UUID, FK training_plans.id ondelete CASCADE, index, nullable=False), `scheduled_date` (Date, nullable=False), `session_type` (SessionType enum, nullable=False), `dominant_physiological_intent` (PhysiologicalIntent enum, nullable=False), `target_duration_minutes` (Integer, nullable=True), `is_key_session` (Boolean, default=False, server_default false), `week_number` (Integer, nullable=False), `phase` (TrainingPhase enum, nullable=False), `generation_metadata` (JSONB, nullable=True), `created_at` (DateTime tz, server_default func.now)
  - Relationship: `training_plan` many-to-one back_populates `planned_sessions`
  - Table args: index on `(training_plan_id, scheduled_date)` named `ix_planned_sessions_plan_date`; index on `(training_plan_id, week_number)`

### 4. Add `training_plans` relationship to `Athlete`

- **Objective**: Enable navigation from athlete to their plans.
- **File**: `app/models/athlete.py` **[MODIFY]**
- **Actions**:
  - Add `from app.models.training_plan import TrainingPlan` to TYPE_CHECKING block
  - Add `training_plans: Mapped[list["TrainingPlan"]]` relationship with back_populates `athlete`, cascade all delete-orphan, order_by `TrainingPlan.created_at.desc()`

### 5. Add `training_plans` relationship to `TrainingBlock`

- **Objective**: Enable navigation from training block to associated plans.
- **File**: `app/models/training_block.py` **[MODIFY]**
- **Actions**:
  - Add `from app.models.training_plan import TrainingPlan` to TYPE_CHECKING block
  - Add `training_plans: Mapped[list["TrainingPlan"]]` relationship with back_populates `training_block`, cascade all delete-orphan

### 6. Update `app/models/__init__.py`

- **Objective**: Export new models and enums.
- **File**: `app/models/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export `TrainingPlanStatus`, `TrainingPhase`, `SessionType`, `PhysiologicalIntent`, `**MethodologyTrait**` from `app.models.enums`
  - Import and export `TrainingPlan` from `app.models.training_plan`
  - Import and export `PlannedSession` from `app.models.planned_session`
  - Add all new symbols to `__all__`

---

## Schemas

### 7. Create agent blueprint schemas

- **Objective**: Define structured LLM output contracts.
- **File**: `app/schemas/plan_generation.py` **[CREATE]**
- **Actions**:
  - Define `SessionAssignment` Pydantic model with fields: `session_type` (SessionType), `target_duration_minutes` (int | None), `is_key_session` (bool)
  - Define `WeekPlan` Pydantic model with fields: `week_number` (int), `phase` (TrainingPhase), `sessions` dict[Weekday, SessionAssignment] where keys are lowercase day names), `week_rationale` (str)
  - Define `PlanBlueprint` Pydantic model with fields: `weeks` (list[WeekPlan]), `plan_rationale` (str)
  - Define `PhaseArc` Pydantic model with fields: `total_weeks` (int), `phases` (list[dict] with keys `phase`, `start_week`, `end_week`), `recovery_weeks` (list[int])
  - Define `ConstraintViolation` Pydantic model with fields: `rule` (str), `week_number` (int | None), `day` (str | None), `details` (str)
  - Define `ValidationResult` Pydantic model with fields: `is_valid` (bool), `violations` (list[ConstraintViolation])
  - **NEW**: Define `MethodologyProfile` Pydantic model with field: `trait_weights: dict[MethodologyTrait, float]`

### 8. Create API response schemas

- **Objective**: Define schemas for API responses.
- **File**: `app/schemas/training_plan.py` **[CREATE]**
- **Actions**:
  - Define `TrainingPlanBase` Pydantic model with fields: `id`, `athlete_id`, `training_block_id`, `status`, `created_at`, `archived_at`, `plan_rationale`
  - Define `PlannedSessionBase` Pydantic model with fields: `id`, `training_plan_id`, `scheduled_date`, `session_type`, `dominant_physiological_intent`, `target_duration_minutes`, `is_key_session`, `week_number`, `phase`, `created_at`
  - Define `TrainingPlanResponse` Pydantic model with fields: `training_plan` (TrainingPlanBase), `planned_sessions` (list[PlannedSessionBase])
  - Define `TrainingPlanListResponse` Pydantic model with fields: `items` (list[TrainingPlanResponse]), `total` (int)

### 9. Update `app/schemas/__init__.py`

- **Objective**: Export new schemas.
- **File**: `app/schemas/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export all models from `app/schemas/plan_generation.py` and `app/schemas/training_plan.py`
  - Add all new symbols to `__all__`

---

## Dynamic Methodology Influence Layer

### Philosophy

Plans should not follow a single rigid methodology such as:

- polarized,
- pyramidal,
- 80/20,
- or threshold-heavy.

Real coaching evolves dynamically based on:

- athlete durability,
- adaptation state,
- race phase,
- confidence,
- consistency,
- fatigue,
- and engagement.

Methodology should therefore be represented as:

- weighted planning tendencies,

not:

- fixed plan identities.

The system should support blending and evolving coaching philosophies across the lifecycle of a plan.

---

## Repositories

### 10. Create `TrainingPlanRepository`

- **Objective**: Database access for training plans.
- **File**: `app/repositories/training_plan_repository.py` **[CREATE]**
- **Actions**:
  - Define `TrainingPlanRepository` extending `BaseRepository[TrainingPlan]`
  - Override `create` to accept kwargs, instantiate `TrainingPlan`, add to session, flush, and return instance
  - Add `get_active_by_athlete(athlete_id)` method returning `TrainingPlan | None`
  - Add `get_by_id(plan_id)` method returning `TrainingPlan | None`
  - Add `archive_plan(plan_id)` method setting `status` to `archived` and `archived_at` to current time

### 11. Create `PlannedSessionRepository`

- **Objective**: Database access for planned sessions.
- **File**: `app/repositories/planned_session_repository.py` **[CREATE]**
- **Actions**:
  - Define `PlannedSessionRepository` extending `BaseRepository[PlannedSession]`
  - Override `create` to accept kwargs, instantiate `PlannedSession`, add to session, flush, and return instance
  - Add `list_by_plan(training_plan_id)` method returning list[PlannedSession] ordered by `scheduled_date`
  - Add `bulk_create(sessions_data)` method accepting list of dicts, instantiating all, adding to session, flushing, and returning list[PlannedSession]

### 12. Update `app/repositories/__init__.py`

- **Objective**: Export new repositories.
- **File**: `app/repositories/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export `TrainingPlanRepository` and `PlannedSessionRepository`
  - Add to `__all__`

---

## Services

### 13. Create `PhaseArcComputer`

- **Objective**: Deterministically compute mesocycle structure.
- **File**: `app/services/phase_arc_computer.py` **[CREATE]**
- **Actions**:
  - Define `PhaseArcComputer` class
  - Define `compute(training_block, twin_state, preferences)` method that:
    - Calculates `weeks_to_goal` from `training_block.goal_event_date` and today
    - Reads `goal_event_type` from `training_block.goal_event_type`
    - Reads `fitness_score` and `structural_capacity_score` from `twin_state`
    - Reads `sport_background` from `preferences.sport_background`
    - Applies deterministic heuristics: minimum base phase duration (4 weeks), mandatory taper (2 weeks for races), durability-aware recovery spacing (every 3-4 weeks), event-specific phase composition
    - Returns `PhaseArc` Pydantic model

### 14. Create `PlanGenerationBriefBuilder`

- **Objective**: Construct compact structured brief for LLM.
- **File**: `app/services/plan_generation_brief_builder.py` **[CREATE]**
- **Actions**:
  - Define `PlanGenerationBrief` Pydantic model with fields: `brief_version` (str, default "v1"), `athlete_summary` (dict), `goal_summary` (dict), `twin_summary` (dict), `available_days` (dict[str, dict]), `phase_arc` (PhaseArc), `explicit_constraints` (list[str]), `coaching_insights` (dict), `**methodology_profile` (MethodologyProfile)**
  - Define `PlanGenerationBriefBuilder` class with `build(athlete, profile, preferences, training_block, twin_state, phase_arc, methodology_profile)` async method
  - The method constructs `available_days` from `preferences.weekly_schedule`
  - The method populates `explicit_constraints` with deterministic rules: no back-to-back threshold or VO2 sessions, long runs must be followed by rest or recovery run, hard sessions require easy day before, maximum two key sessions per week, respect available days exactly, recovery weeks reduce overall load
  - The method progression rules: Long runs should generally progress gradually, Recovery weeks should reduce stress exposure, Race specificity should increase near the event, Taper weeks should reduce overall load, Key session density should evolve progressively
  - **NEW**: Include `methodology_profile` in the brief, with tendencies as soft guidance (e.g., "Favor high aerobic volume. Use conservative progression.")
  - Returns `PlanGenerationBrief`

### 15. Create `MethodologyProfileBuilder`

- **Objective**: Deterministically derive methodology tendencies from athlete state.
- **File**: `app/services/methodology_profile_builder.py` **[CREATE]**
- **Actions**:
  - Define `MethodologyProfileBuilder` class
  - Define `build(event_type, weeks_to_goal, training_age, available_days, structural_capacity_score, adaptation_confidence_level, consistency_score)` method
  - **Inputs**:
    - `event_type` (from `TrainingBlock.goal_event_type`)
    - `weeks_to_goal` (derived from `TrainingBlock.goal_event_date`)
    - `training_age` (from `AthletePreferences.years_structured_training`)
    - `available_days` (from `AthletePreferences.weekly_schedule`)
    - `structural_capacity_score` (from `TwinState`)
    - `adaptation_confidence_level` (from `TwinState.confidence_level`)
    - `consistency_score` (derived from historical adherence)
  - **Outputs**:
    - `MethodologyProfile(trait_weights={...})`
  - **Logic**:
    - Base phase: `HIGH_AEROBIC_VOLUME: 0.9`, `CONSERVATIVE_PROGRESSION: 0.8`, `THRESHOLD_DENSITY: 0.2`
    - Build phase: `RACE_SPECIFICITY: 0.9`, `THRESHOLD_DENSITY: 0.7`, `HIGH_INTENSITY_SPARSE: 0.5`
    - Taper phase: `NEUROMUSCULAR_SUPPORT: 0.7`, `VARIETY_EMPHASIS: 0.6`, `CONSERVATIVE_PROGRESSION: 1.0`
  - **Constraints**:
    - Weights must sum to ≤ 1.0 per trait
    - **Never** override deterministic physiological constraints

### 16. Create `PlanConstraintValidator`

- **Objective**: Validate plan blueprints against explicit constraints.
- **File**: `app/services/plan_constraint_validator.py` **[CREATE]**
- **Actions**:
  - Define `PlanConstraintValidator` class
  - Define `validate(blueprint, available_days, phase_arc)` method returning `ValidationResult`
  - **Hard constraints to enforce**:
    - Flatten all planned sessions chronologically before validation
    - Validate adjacency and recovery constraints **across week boundaries**
    - Sessions may only occur on available days (keys in `blueprint.weeks[*].sessions` must match `available_days` keys)
    - No duplicate sessions per day
    - Week structure must align with phase arc (`week_number` must fall within a phase's `start_week` and `end_week`)
    - No back-to-back threshold or VO2 sessions **across adjacent days within a week**
    - Long runs must be followed by `rest` or `recovery_run` in the next scheduled day
    - Maximum two key sessions per week
    - Recovery weeks (identified by `phase_arc.recovery_weeks`) must have reduced hard-session density
  - Each violation produces a `ConstraintViolation` with `rule` name, `week_number`, `day`, and `details`

### 17. Create `PlanRepairEngine`

- **Objective**: Deterministically repair minor validation violations.
- **File**: `app/services/plan_repair_engine.py` **[CREATE]**
- **Actions**:
  - Define `PlanRepairEngine` class
  - Define `repair(blueprint, validation_result, available_days)` method that returns repaired `PlanBlueprint`
  - Allowed repairs:
    - Convert illegal back-to-back threshold or VO2 session to `easy_run`
    - Add `rest` or `recovery_run` after `long_run` if missing
    - Repair by changing session_type to a lower-stress session type (e.g. THRESHOLD → EASY_RUN)
    - Never repair topology violations through metadata-only changes
    - Remove sessions on non-available days
  - Forbidden repairs (must not implement):
    - Redesigning week structure
    - Inventing new strategic structure
    - Altering mesocycle intent
  - If repairs cannot resolve all violations, return the partially repaired blueprint and let the caller decide on regeneration
  - Repairs must be deterministic.
  - Repairs must be logged.
  - Recursive repair loops are forbidden.
  - MAX_REPAIR_ATTEMPTS = 1

### 18. Create `TrainingPlanService`

- **Objective**: Orchestrate plan generation, retrieval, and instantiation.
- **File**: `app/services/training_plan_service.py` **[CREATE]**
- **Actions**:
  - Define module-level constant `SESSION_TYPE_TO_DOMINANT_INTENT` mapping every `SessionType` to exactly one `PhysiologicalIntent`; missing mappings must raise KeyError at import time
  - Define `TrainingPlanService` class accepting `training_plan_repo`, `planned_session_repo`, `phase_arc_computer`, `brief_builder`, `agent`, `validator`, `repair_engine`, `**methodology_profile_builder**` in constructor
  - Define `generate_plan(athlete_id, uow)` async method that:
    - Fetches athlete, profile, preferences, training_block, twin_state from uow
    - Raises `ValueError` if any required data is missing
    - Calls `phase_arc_computer.compute(...)`
    - **NEW**: Calls `methodology_profile_builder.build(...)` with required inputs
    - Calls `brief_builder.build(..., methodology_profile)` to include methodology in brief
    - Calls `agent.generate(...)` to get blueprint dict and metadata
    - Validates blueprint with `validator.validate(...)`
    - If invalid, calls `repair_engine.repair(...)` once
    - Re-validates repaired blueprint; if still invalid, raises `ValueError` with violation details
    - Calls `_instantiate_plan(...)` to persist
    - Returns `TrainingPlanResponse`
  - Define `_instantiate_plan(athlete_id, training_block, blueprint, metadata, uow)` private async method that:
    - Creates `TrainingPlan` with `generation_metadata` containing model, prompt_version, phase_arc_version, validator_version, **methodology_profile**, and timestamp
    - Derives `dominant_physiological_intent` for each session from `SESSION_TYPE_TO_DOMINANT_INTENT`
    - Maps day names to actual dates using the current date as week 1 start
    - Bulk creates `PlannedSession` records via `planned_session_repo.bulk_create(...)`
    - Returns created `TrainingPlan`
  - Define `get_active_plan(athlete_id, uow)` async method returning `TrainingPlanResponse` with sessions loaded, or None
  - Define `get_plan_by_id(plan_id, uow)` async method returning `TrainingPlanResponse` with sessions loaded, or None
  - Define `archive_plan(plan_id, uow)` async method calling `training_plan_repo.archive_plan(...)`

### 19. Update `app/services/__init__.py`

- **Objective**: Export new services.
- **File**: `app/services/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export `PhaseArcComputer`, `PlanGenerationBriefBuilder`, `PlanConstraintValidator`, `PlanRepairEngine`, `TrainingPlanService`, `**MethodologyProfileBuilder**`
  - Add to `__all__`

---

## Agents

### 20. Create LLM router wrapper

- **Objective**: Comply with stack-truth LLM access rule.
- **File**: `app/core/llm_router.py` **[CREATE]**
- **Actions**:
  - Import `get_litellm_client` from `app.core.llm`
  - Define `get_llm()` function that returns the result of `get_litellm_client()`

### 21. Create plan generation prompt

- **Objective**: Register versioned system prompt for plan generation agent.
- **File**: `app/agents/prompts/plan_generation_v1.py` **[CREATE]**
- **Actions**:
  - Define `SYSTEM_PROMPT` string constant containing instructions for the LLM:
    - Reason about session spacing, athlete durability, available-day topology, phase progression, recovery sequencing, and mesocycle structure
    - **NEW**: Interpret methodology tendencies as **soft guidance, not rigid rules**. Favor structured variation, adherence, and psychological freshness.
    - Do not generate detailed workouts, pacing, intervals, or long narrative prose
    - Output must be valid JSON matching the PlanBlueprint schema
    - Respect all explicit constraints provided in the brief
  - Create `PromptRecord(version="v1", system_prompt=SYSTEM_PROMPT, max_output_tokens=4000)`
  - Register via `PromptRegistry.register("plan_generation", prompt_record)`

### 22. Update prompt registry

- **Objective**: Wire current version for plan generation agent.
- **File**: `app/agents/prompts/registry.py` **[MODIFY]**
- **Actions**:
  - Add `"plan_generation": "v1"` to `CURRENT_VERSIONS` dict
  - Add import of `app.agents.prompts.plan_generation_v1` at bottom of file to trigger registration

### 23. Create `PlanGenerationAgent`

- **Objective**: LLM agent that produces structured plan blueprints.
- **File**: `app/agents/plan_generation_agent.py` **[CREATE]**
- **Actions**:
  - Import `get_llm` from `app.core.llm_router`
  - Import `settings` from `app.config`
  - Import `PromptRegistry` from `app.agents.prompts.registry`
  - Import `GenerationEvent`, `log_generation_event` from `app.core.telemetry`
  - Import `GenerationOutcome` from `app.models.enums`
  - Define `AGENT_NAME = "plan_generation"`
  - Define `_build_user_message(brief)` function that serializes `PlanGenerationBrief` into compact text, **including methodology tendencies**
  - Define `PlanGenerationAgent` class with `__init__` calling `get_llm()`
  - Define `generate(athlete_id, brief)` async method that:
    - Fetches current prompt record from registry
    - Builds user message
    - Calls `chat.completions.create` with `model=settings.LLM_MODEL`, `max_tokens=prompt_record.max_output_tokens`, `temperature=0.2`, `response_format={"type": "json_object"}`, system and user messages
    - Records latency, input_tokens, output_tokens, stop_reason
    - Parses JSON content
    - Validates parsed dict against `PlanBlueprint` Pydantic model
    - Logs `GenerationEvent` with outcome `SUCCESS` or `MALFORMED`
    - On timeout, API error, or unexpected exception, logs appropriate `GenerationEvent` and re-raises
    - Returns tuple of `(blueprint_dict, metadata_dict)` where metadata contains model, prompt_version, brief_version, outcome, tokens, latency

### 24. Update `app/agents/__init__.py`

- **Objective**: Export new agent.
- **File**: `app/agents/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export `PlanGenerationAgent`

---

## Tasks

### 25. Create plan generation background task

- **Objective**: Idempotent background plan generation after onboarding.
- **File**: `app/tasks/plan_generation_task.py` **[CREATE]**
- **Actions**:
  - Import `AsyncSessionLocal` from `app.db.session`
  - Import `UnitOfWork` from `app.core.unit_of_work`
  - Import `TrainingPlanService` and all its dependencies
  - Import `GenerationEvent`, `log_generation_event` from `app.core.telemetry`
  - Import `GenerationOutcome` from `app.models.enums`
  - Define `generate_training_plan(athlete_id)` async function that:
    - Creates session from `AsyncSessionLocal`
    - Inside `async with session`, inside `async with UnitOfWork(session) as uow`:
      - Checks if active plan already exists via `uow.training_plans.get_active_by_athlete(athlete_id)`
      - If exists, log info and return
      - Fetches athlete; if missing, log `GenerationEvent` with `MISSING_DATA` and return
      - Fetches profile, preferences, training_block, twin_state; if any missing, log `GenerationEvent` with `MISSING_DATA` and return
      - Constructs `TrainingPlanService` with repositories from uow
      - Calls `service.generate_plan(athlete_id, uow)`
      - Logs success
    - Catches exceptions, logs error, does not re-raise
    - Closes session in finally block

### 26. Update `app/tasks/__init__.py`

- **Objective**: Export new task.
- **File**: `app/tasks/__init__.py` **[MODIFY]**
- **Actions**:
  - Import and export `generate_training_plan`

---

## API

### 27. Create training plan routes

- **Objective**: Expose plan retrieval endpoints.
- **File**: `app/api/routes/training_plans.py` **[CREATE]**
- **Actions**:
  - Define router with prefix `/athletes` and tags `["training_plans"]`
  - Define `GET /{athlete_id}/training-plans/active` handler:
    - Uses `get_training_plan_service` dependency
    - Uses `UnitOfWork` with `get_db` session
    - Calls `service.get_active_plan(athlete_id, uow)`
    - Returns 404 if no active plan
    - Returns `TrainingPlanResponse`
  - Define `GET /{athlete_id}/training-plans/{plan_id}` handler:
    - Calls `service.get_plan_by_id(plan_id, uow)`
    - Validates plan belongs to athlete; returns 403 if not
    - Returns 404 if not found
    - Returns `TrainingPlanResponse`

### 28. Update `app/main.py`

- **Objective**: Register training plan router.
- **File**: `app/main.py` **[MODIFY]**
- **Actions**:
  - Import `router as training_plans_router` from `app.api.routes.training_plans`
  - Add `app.include_router(training_plans_router)` before existing routers

### 29. Update API dependencies

- **Objective**: Provide `TrainingPlanService` via FastAPI Depends.
- **File**: `app/api/dependencies/services.py` **[MODIFY]**
- **Actions**:
  - Import `TrainingPlanService`, `PhaseArcComputer`, `PlanGenerationBriefBuilder`, `PlanConstraintValidator`, `PlanRepairEngine`, `**MethodologyProfileBuilder**` from `app.services`
  - Import `TrainingPlanRepository`, `PlannedSessionRepository` from `app.repositories`
  - Import `PlanGenerationAgent` from `app.agents`
  - Define `get_training_plan_service(db: AsyncSession = Depends(get_db))` dependency factory that:
    - Instantiates `TrainingPlanRepository(db)`, `PlannedSessionRepository(db)`
    - Instantiates `PhaseArcComputer()`, `PlanGenerationBriefBuilder()`, `PlanConstraintValidator()`, `PlanRepairEngine()`, `**MethodologyProfileBuilder()**`, `PlanGenerationAgent()`
    - Returns `TrainingPlanService(...)` with all dependencies

### 30. Update onboarding route to trigger plan generation

- **Objective**: Automatically generate plan after onboarding completes.
- **File**: `app/api/routes/athletes.py` **[MODIFY]**
- **Actions**:
  - Import `generate_training_plan` from `app.tasks.plan_generation_task`
  - In `onboard_athlete` handler, after `background_tasks.add_task(generate_first_coach_message, athlete_id)`, add `background_tasks.add_task(generate_training_plan, athlete_id)`

---

## Core

### 31. Update `UnitOfWork` with new repositories

- **Objective**: Enable UoW access to planning repositories.
- **File**: `app/core/unit_of_work.py` **[MODIFY]**
- **Actions**:
  - Import `TrainingPlanRepository` and `PlannedSessionRepository`
  - Add `"training_plans": TrainingPlanRepository(self.session)` and `"planned_sessions": PlannedSessionRepository(self.session)` to the `_repos` dict inside `__aenter__`

---

## Migration

### 32. Create migration for new models

- **Objective**: Add database tables for training plans and planned sessions.
- **File**: `alembic/versions/<hash>_create_training_plan_tables.py` **[CREATE]**
- **Actions**:
  - `op.create_table('training_plans', ...)` with all columns matching the ORM model, including `generation_metadata` JSONB
  - `op.create_table('planned_sessions', ...)` with all columns matching the ORM model
  - Add indexes:
    - `op.create_index('ix_training_plans_athlete_status', 'training_plans', ['athlete_id', 'status'], unique=False)`
    - `op.create_index('ix_training_plans_athlete_created_at', 'training_plans', ['athlete_id', 'created_at'], unique=False)`
    - `op.create_index('ix_planned_sessions_plan_date', 'planned_sessions', ['training_plan_id', 'scheduled_date'], unique=False)`
    - `op.create_index('ix_planned_sessions_plan_week', 'planned_sessions', ['training_plan_id', 'week_number'], unique=False)`
    - `op.create_index('uq_training_plans_active_per_athlete', 'training_plans', ['athlete_id'], unique=True, postgresql_where=sa.text("status = 'active'"))`

---

---

## Validation Against stack-truth.md


| **Rule**                                                        | **Compliance** | **Notes**                                                                                               |
| --------------------------------------------------------------- | -------------- | ------------------------------------------------------------------------------------------------------- |
| **Layer Architecture (api → services → repositories → models)** | ✅              | All new components follow strict layering. `MethodologyProfileBuilder` is stateless and in `services/`. |
| **No business logic in API**                                    | ✅              | All logic in services; routes only call service methods.                                                |
| **No direct repository access outside services**                | ✅              | Repositories only accessed via `TrainingPlanService`.                                                   |
| **Async DB access**                                             | ✅              | All repositories use `AsyncSession`.                                                                    |
| **LLM Access via `app.core.llm_router.get_llm()**`              | ✅              | `PlanGenerationAgent` uses the router.                                                                  |
| **No provider SDKs in services**                                | ✅              | LLM access abstracted via router.                                                                       |
| **Pydantic v2**                                                 | ✅              | All schemas use `model_validate()` and `model_dump()`.                                                  |
| **No sync SQLAlchemy**                                          | ✅              | All DB access is async.                                                                                 |


---

## Validation Against Current Architecture


| **Component**                                   | **Fit** | **Notes**                                                |
| ----------------------------------------------- | ------- | -------------------------------------------------------- |
| **MethodologyTrait Enum**                       | ✅       | Added to `app/models/enums.py` alongside existing enums. |
| **MethodologyProfile Schema**                   | ✅       | Added to `app/schemas/plan_generation.py`.               |
| **MethodologyProfileBuilder**                   | ✅       | Stateless service; no DB access. Fits in `services/`.    |
| **Integration with PlanGenerationBriefBuilder** | ✅       | Builder pattern maintained; no layer skipping.           |
| **Persistence in `generation_metadata**`        | ✅       | Uses existing JSONB field; no schema changes.            |
| **Background Task Trigger**                     | ✅       | Wired to onboarding via `generate_training_plan`.        |


---

---

## Key Architectural Decisions

1. **Methodology as Soft Guidance**
  - The LLM interprets `MethodologyProfile` as **tendencies**, not rules.
  - Ensures flexibility while maintaining deterministic constraints.
2. **Stateless MethodologyProfileBuilder**
  - No repository dependencies; pure computation from existing data.
3. **No New Database Columns**
  - `methodology_profile` stored in `generation_metadata` JSONB to avoid schema bloat.
4. **Phase-Aware Weights**
  - Weights evolve deterministically based on `TrainingPhase` (base/build/peak/taper).
5. **Variety as First-Class Objective**
  - Explicitly included in `MethodologyTrait.VARIETY_EMPHASIS`.

---

## Done Criteria

- All model, schema, repository, service, agent, task, API, and migration files created and wired
- `UnitOfWork` exposes `training_plans` and `planned_sessions`
- Onboarding automatically triggers plan generation via `BackgroundTasks`
- `dominant_physiological_intent` is deterministically derived from `SESSION_TYPE_TO_DOMINANT_INTENT` mapping
- Partial unique index enforces one active plan per athlete
- Plan generation is idempotent (skips if active plan exists)
- `app/core/llm_router.py` exists and new agent uses it per stack-truth
- All new enums exported from `app.models.__init__`
- All new schemas exported from `app.schemas.__init__`
- All new repositories exported from `app.repositories.__init__`
- All new services exported from `app.services.__init__`

---

## Out of Scope (Deferred)

- Dynamic adaptation of methodology weights based on real-time feedback (Phase 2+)
- Machine learning for trait weight optimization (Phase 3+)
- Athlete-specific methodology preferences (Phase 2+)