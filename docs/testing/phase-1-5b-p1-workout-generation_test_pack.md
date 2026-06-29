# Test Pack — Phase-1.5b-P1 (Workout Generation)

## Overview

This test pack covers the Phase-1.5b implementation of the Workout Generation feature.
The feature enables athletes to see their workout for the day, generated on-demand from
the planned session and current twin state.

## Final Status

**All 6 features promoted** on 2026-06-28 after DevOps Run 5 reported **77/77 tests
passing** with a clean full-stack build. The 6 test files are now members of both the
`regression` and `release` selection groups in `tests/test-manifest/index.yaml`.

## Test Run History

| Run | Passed | Failed | Trigger / Fix |
|-----|--------|--------|---------------|
| 1   | 57     | 20     | Initial run — pre-`conftest.py` fix; WeeklyPlan NOT NULL violations |
| 2   | 62     | 15     | DevOps added `WeeklyPlan` `before_insert` listener to `conftest.py` |
| 3   | 74     | 3      | Coder fixed repository assertion patterns and agent mock data |
| 4   | 75     | 2      | Test Architect fixed integration 404 path, JSON parsing, and `target_gap_sec_per_km` for gap target_type |
| **5** | **77** | **0**  | **Test Architect fixed mock step structure — added `work` + `cooldown` steps so the last step satisfies the validator's `last step = cooldown` invariant** |

## What Was Generated

### Unit Tests

| File | Coverage |
|------|----------|
| `tests/unit/test_generated_workout_repository.py` | `GeneratedWorkoutRepository` — append-only insert, idempotent `get_by_session_and_date()`, ordered `get_by_planned_session()` |
| `tests/unit/test_workout_step_repository.py` | `WorkoutStepRepository` — batch `insert_many()`, ordered `get_by_workout()` |
| `tests/unit/test_planned_session_repository.py` | `PlannedSessionRepository` — `get_by_id()`, `get_today_for_athlete()` via WeeklyPlan→TrainingPlan join |
| `tests/unit/test_workout_target_types.py` | `SESSION_INTENT_MAP` completeness, `DATA_TIER_TARGET_TYPE` mapping, `get_step_physiological_intent()` helper |
| `tests/unit/test_workout_generation_agent.py` | `WorkoutGenerationAgent` — idempotency gate, pre-conditions, LLM failure handling, step validation, context assembly |

### Integration Tests

| File | Coverage |
|------|----------|
| `tests/integration/test_workout_endpoints.py` | `GET /athletes/{id}/today` and `POST /athletes/{id}/sessions/{sid}/generate-workout` — full HTTP surface with auth, 404, 409, 502, 403 |

## Test Inventory

### `test_generated_workout_repository.py`

- **`TestInsert`** — `insert()` adds workout to session and flushes, returns the workout
- **`TestGetBySessionAndDate`** — returns existing workout when found, `None` when not found, queries by both `planned_session_id` and `generation_date`
- **`TestGetByPlannedSession`** — returns workouts ordered by `generated_at DESC`, empty list when none exist

### `test_workout_step_repository.py`

- **`TestInsertMany`** — adds all steps in one batch flush, refreshes each step, returns the steps list, handles empty list
- **`TestGetByWorkout`** — returns steps ordered by `step_order ASC`, empty list when none exist, queries by `generated_workout_id`

### `test_planned_session_repository.py`

- **`TestGetById`** — returns session when found, `None` when not found, queries by id
- **`TestGetTodayForAthlete`** — returns sessions ordered by `session_slot ASC`, empty list when none, joins via WeeklyPlan→TrainingPlan, filters by athlete_id and active plan

### `test_workout_target_types.py`

- **`TestSessionIntentMap`** — all 16 `SessionType` values covered, correct mapping to `PhysiologicalIntent`
- **`TestDataTierTargetType`** — Tier 1-2→power, Tier 3-4→gap, Tier 5-6→description, all tiers covered
- **`TestGetStepPhysiologicalIntent`** — warmup/cooldown/recovery always return `RECOVERY` regardless of session type, work steps derive from `SESSION_INTENT_MAP`

### `test_workout_generation_agent.py`

- **`TestIdempotencyGate`** — existing workout returned without LLM call (`allow_existing=True`), `WorkoutAlreadyGeneratedError` raised (`allow_existing=False`), context assembly skipped on idempotency hit
- **`TestPreConditions`** — `LLMServiceUnavailableError` when no twin state, `PlannedSessionNotFoundError` when session missing
- **`TestLLMFailure`** — `GenerationEvent(success=false)` written on LLM error, no workout inserted, `LLMServiceUnavailableError` propagated
- **`TestStepValidation`** — null `physiological_intent` raises `WorkoutGenerationContractError`, valid structure passes
- **`TestContextAssembly`** — `build_workout_context()` called with correct `athlete_id` and `planned_session_id`

### `test_workout_endpoints.py`

- **`TestGetToday`** — 200 with workout when exists, 404 when no session today, 403 on cross-athlete access, 401 without auth
- **`TestPostGenerateWorkout`** — 201 on successful generation, 409 when already generated, 502 on LLM failure, 404 when session not found, 403 on cross-athlete access, 401 without auth
- **`TestIdempotency`** — second POST returns 409 with same workout ID

## Coverage Gaps

The following capabilities are **not yet covered** by generated tests and should be added
in future iterations or by DevOps if infrastructure issues arise:

| Gap | Why Missing | Priority |
|-----|-------------|----------|
| Integration: twin state linkage invariant | Requires full DB setup with TwinState + plan + session chain | Medium |
| Integration: GAP-only pace validation in targets | Requires mocking LLM output with pace targets and verifying raw pace is absent | Medium |
| Integration: `recovery_modifier_level = GREEN` default on generated workout | Requires full generation flow with real DB state | Medium |
| Integration: `twin_state_id` records generation twin version | Requires mocking twin state and verifying it on the generated workout | Medium |
| Integration: event `workout_generated` produced in same transaction | Requires DB-level assertion on SystemEvent + Outbox rows | High |
| Unit: `ContextBudgetService.build_workout_context()` token budget enforcement | Requires mocking all nested repo calls; covered in existing Phase-1.5a tests for `build_first_message_context` | Low |

## Execution Prerequisites

All tests in this phase require:

```yaml
migrations: true    # generated_workouts and workout_steps tables must exist
seed_data: false
external_services:
  - LiteLLM proxy  # required for agent tests that reach the LLM call path
```

**Note:** The unit tests (`test_workout_generation_agent.py`) mock the LLM client via `patch.object(WorkoutGenerationAgent, "_build_llm_client")` so they do not require the LiteLLM proxy to be reachable. The integration tests patch at the agent level (`patch("app.api.v1.workout.WorkoutGenerationAgent")`) so they also do not require the proxy.

## Execution Groups

### `phase_1_5b_feature` (scope: feature)

Runs all Phase-1.5b tests in a single group:

```
tests/unit/test_generated_workout_repository.py
tests/unit/test_workout_step_repository.py
tests/unit/test_planned_session_repository.py
tests/unit/test_workout_target_types.py
tests/unit/test_workout_generation_agent.py
tests/integration/test_workout_endpoints.py
```

**Depends on:** `phase_1_5a_feature` (must run after Phase-1.5a tests complete, as they share the `ContextBudgetService`)

### `smoke` — No changes

Phase-1.5b does not add new smoke tests. The existing smoke group remains unchanged.

### `regression` / `release` — Phase-1.5b promoted

After DevOps Run 5 reported 77/77 tests passing with a clean full-stack build, all six
Phase-1.5b features were promoted (status `generated → promoted`) on 2026-06-28. The
following test paths are now part of both the `regression` and `release` selection
groups in `tests/test-manifest/index.yaml`:

```
tests/unit/test_generated_workout_repository.py
tests/unit/test_workout_step_repository.py
tests/unit/test_planned_session_repository.py
tests/unit/test_workout_target_types.py
tests/unit/test_workout_generation_agent.py
tests/integration/test_workout_endpoints.py
```

Phase-1.5b is the second promoted sub-phase (after Phase-1.5a coaching) in the
regression/release gate.

### `feature` — Reset

The `feature` selection group is now empty. It will be repopulated when the next Test
Architect cycle opens a new sub-phase manifest.

## Cross-Phase Impact

Phase-1.5b introduced the following new architecture contracts that existing tests should be aware of:

1. **`workout_generated` event** — Phase-1.6's post-workout flow will consume this event. The integration test `test_workout_endpoints.py` verifies the event is not duplicated.
2. **`WorkoutGenerationContext` dataclass** — shared between `ContextBudgetService.build_workout_context()` and `WorkoutGenerationAgent`. Changes to this contract affect both Phase-1.5b and Phase-1.6.
3. **GAP-only pace enforcement** — The prompt template (`app/core/prompts/workout_gen_v1.md`) enforces GAP-only pace in the LLM output. Integration tests do not yet validate this at the response level.

## Running Tests

```bash
# Full feature suite for Phase-1.5b
bash scripts/run-tests.sh tests/unit/test_generated_workout_repository.py
bash scripts/run-tests.sh tests/unit/test_workout_step_repository.py
bash scripts/run-tests.sh tests/unit/test_planned_session_repository.py
bash scripts/run-tests.sh tests/unit/test_workout_target_types.py
bash scripts/run-tests.sh tests/unit/test_workout_generation_agent.py
bash scripts/run-tests.sh tests/integration/test_workout_endpoints.py

# Or via the manifest (DevOps reads this to resolve scope)
# Read tests/test-manifest/phase-1-5b.yaml for execution group
```