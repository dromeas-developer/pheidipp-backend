# Validation Report — phase_1e_training_plan_generation
Date: 2026-05-20
Plan: plans/phase_1e_training_plan_generation.md

## Result: FAIL

## Plan Conformance

| Step | File | Status | Notes |
|------|------|--------|-------|
| 1 | app/models/enums.py | ✅ | All 5 enums added: TrainingPlanStatus, TrainingPhase, SessionType, PhysiologicalIntent, MethodologyTrait |
| 2 | app/models/training_plan.py | ✅ | CREATE — all columns, relationships, and table args match plan |
| 3 | app/models/planned_session.py | ✅ | CREATE — all columns, relationships, and table args match plan |
| 4 | app/models/athlete.py | ✅ | TYPE_CHECKING import + training_plans relationship added |
| 5 | app/models/training_block.py | ✅ | TYPE_CHECKING import + training_plans relationship added |
| 6 | app/models/__init__.py | ✅ | All new enums and models exported |
| 7 | app/schemas/plan_generation.py | ✅ | CREATE — all schemas defined: MethodologyProfile, SessionAssignment, WeekPlan, PlanBlueprint, PhaseArc, PhaseArcPhase, ConstraintViolation, ValidationResult |
| 8 | app/schemas/training_plan.py | ✅ | CREATE — TrainingPlanBase, PlannedSessionBase, TrainingPlanResponse, TrainingPlanListResponse (plus TrainingPlanListItem) |
| 9 | app/schemas/__init__.py | ✅ | All new schemas imported and exported |
| 10 | app/repositories/training_plan_repository.py | ✅ | CREATE — create, get_active_by_athlete, archive_plan implemented; get_by_id inherited from BaseRepository |
| 11 | app/repositories/planned_session_repository.py | ✅ | CREATE — create, list_by_plan, bulk_create implemented |
| 12 | app/repositories/__init__.py | ✅ | Both repositories exported |
| 13 | app/services/phase_arc_computer.py | ✅ | CREATE — compute method with deterministic heuristics matches plan |
| 14 | app/services/plan_generation_brief_builder.py | ⚠️ MINOR | `build` method is sync (plan says async); `profile` param omitted but accessed via `athlete.profile` internally — acceptable improvement |
| 15 | app/services/methodology_profile_builder.py | ✅ | CREATE — build method with event-type-specific profiles matches plan |
| 16 | app/services/plan_constraint_validator.py | ✅ | CREATE — all hard constraints enforced including cross-week adjacency |
| 17 | app/services/plan_repair_engine.py | ✅ | CREATE — MAX_REPAIR_ATTEMPTS=1, allowed/forbidden repairs match plan |
| 18 | app/services/training_plan_service.py | ⚠️ MINOR | `_instantiate_plan` has extra `methodology_profile` param (plan didn't specify); `generation_metadata` missing `phase_arc_version` and `validator_version` keys specified in plan |
| 19 | app/services/__init__.py | ✅ | All new services exported |
| 20 | app/core/llm_router.py | ✅ | CREATE — `get_llm()` wraps `get_litellm_client()` |
| 21 | app/agents/prompts/plan_generation_v1.py | ✅ | CREATE — SYSTEM_PROMPT, PromptRecord v1, registration all present |
| 22 | app/agents/prompts/registry.py | ✅ | `"plan_generation": "v1"` added to CURRENT_VERSIONS; import triggers registration |
| 23 | app/agents/plan_generation_agent.py | ✅ | CREATE — all imports, AGENT_NAME, generate method with telemetry match plan |
| 24 | app/agents/__init__.py | ✅ | PlanGenerationAgent exported |
| 25 | app/tasks/plan_generation_task.py | ✅ | CREATE — idempotent background task with MISSING_DATA logging matches plan |
| 26 | app/tasks/__init__.py | ✅ | generate_training_plan exported |
| 27 | app/api/routes/training_plans.py | ✅ | CREATE — GET active and GET by-id routes with 404/403 handling |
| 28 | app/main.py | ✅ | training_plans_router imported and included |
| 29 | app/api/dependencies/services.py | ✅ | get_training_plan_service factory with all dependencies |
| 30 | app/api/routes/athletes.py | ✅ | generate_training_plan wired after generate_first_coach_message |
| 31 | app/core/unit_of_work.py | ✅ | training_plans and planned_sessions repos added to _repos dict |
| 32 | alembic/versions/*_create_training_plan_tables.py | ❌ CRITICAL | **File does not exist** — migration for training_plans and planned_sessions tables is missing |

## Stack-Truth Violations

### CRITICAL
- **Missing migration**: `alembic/versions/<hash>_create_training_plan_tables.py` — The plan (step 32) requires a migration creating `training_plans` and `planned_sessions` tables with all columns and indexes. No migration file exists in `alembic/versions/` for these tables. Without this migration, the ORM models cannot be applied to the database.

### MINOR
- **Sync vs async brief builder** (`app/services/plan_generation_brief_builder.py`): Plan specifies `build(...)` as `async` method; implementation is synchronous. Since the method performs no I/O, sync is functionally correct but deviates from the plan specification.
- **Missing metadata keys** (`app/services/training_plan_service.py`): Plan specifies `generation_metadata` should contain `phase_arc_version` and `validator_version`. Implementation only includes agent metadata (`model`, `prompt_version`, `brief_version`, `outcome`, tokens, latency) plus `methodology_profile`. The version tracking fields are absent.

## Stack-Truth Conformance (Independent Checks)

| Rule | Status | Notes |
|------|--------|-------|
| No business logic in api layer | ✅ | Routes only call service methods |
| No direct repository access from api | ✅ | Repositories accessed only via services |
| No sync SQLAlchemy | ✅ | All DB access uses AsyncSession |
| No `parse_obj()` or `.dict()` | ✅ | None found in new files |
| PATCH handlers use `exclude_unset=True` | N/A | No PATCH handlers in this feature |
| TYPE_CHECKING guards on cross-model imports | ✅ | All model cross-references guarded |
| All Enum columns use `native_enum=False` | ✅ | TrainingPlanStatus, SessionType, PhysiologicalIntent, TrainingPhase all use `native_enum=False` |
| Route files in `app/api/routes/` only | ✅ | `training_plans.py` is in correct location |
| New models exported in `app/models/__init__.py` | ✅ | TrainingPlan, PlannedSession, all enums exported |
| New schemas exported in `app/schemas/__init__.py` | ✅ | All plan_generation and training_plan schemas exported |

## Routing

| Finding Type | Route To |
|---|---|
| CRITICAL (missing migration) | p-devops + this report |
| MINOR (sync vs async, missing metadata keys) | p-coder + this report |
