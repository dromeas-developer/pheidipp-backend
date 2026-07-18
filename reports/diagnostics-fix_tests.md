# Diagnostics Fix Report — `reportMissingTypeArgument` & `reportMissingParameterType`

**Date:** 2026-07-18  
**Scope:** `tests/` directory  
**Plan ID:** diagnostics-fix  
**Initial errors found:** ~40 `reportMissingTypeArgument` + ~15 `reportMissingParameterType` (combined across all files)

---

## Summary

**Status: PASS** — Zero remaining errors in both categories.

- `reportMissingTypeArgument`: **0 errors** (was ~40)
- `reportMissingParameterType`: **0 errors** (was ~15)
- Total typecheck errors before fix: 672
- Total typecheck errors after fix: 349 (remaining are unrelated categories: `reportPrivateUsage`, `reportUnknownMemberType`, `reportArgumentType`, `reportUnknownLambdaType`, `reportAttributeAccessIssue`, etc.)
- Lint: All newly introduced lint errors resolved (1 unused `Any` import removed)

---

## Iteration Log

### Iteration 1 — Integration test files (batch)

#### Files fixed:

| File | Changes |
|---|---|
| `tests/integration/test_activity_ingestion_signal_clean_enqueue_integration.py` | `List[dict]` → `List[dict[str, Any]]`, `list[dict]` → `list[dict[str, Any]]`, `Optional[dict]` → `Optional[dict[str, Any]]` |
| `tests/integration/test_coaching_message_schema.py` | Added `Any` import; `dict \| None` → `dict[str, Any] \| None` (2 occurrences in `_partial_unique_index` methods) |
| `tests/integration/test_generated_workout_schema.py` | Added `Any` import; `dict` → `dict[str, Any]` (in `_default_targets`) |
| `tests/integration/test_phase_1_1_registration_regression.py` | Added `Any` import; `dict` → `dict[str, Any]` (in `_register_kwargs`) |
| `tests/integration/test_signal_clean_threshold_detection_defer_integration.py` | `List[dict]` → `List[dict[str, Any]]` (in `call_log`) |
| `tests/integration/test_signal_cleaning_service_integration.py` | Added `Any` import; `Optional[dict]` → `Optional[dict[str, Any]]` (in `quality_flags`) |
| `tests/integration/test_signal_cleaning_task_integration.py` | Added `Any` import; `dict` → `dict[str, Any]` (in `task_return`) |
| `tests/integration/test_threshold_detection_service_integration.py` | Added `Any` import; `Optional[tuple]` → `Optional[tuple[Any, Any, Any]]`, `tuple` → `tuple[Any, Any, Any, Any]`, `list` → `list[Any]`, `List[dict]` → `List[dict[str, Any]]` |
| `tests/integration/test_threshold_detection_task_integration.py` | `Optional[list]` → `Optional[list[Any]]`, `dict` → `dict[str, Any]` |
| `tests/integration/test_training_plan_schema.py` | Added `Any` import; `dict \| None` → `dict[str, Any] \| None` |
| `tests/integration/test_twin_state_schema.py` | Added `Any` import; `dict \| None` → `dict[str, Any] \| None`, `dict \| None` → `dict[str, Any] \| None` (in `_partial_unique_index`) |
| `tests/integration/test_workout_step_schema.py` | Added `Any` import; `dict` → `dict[str, Any]`, `dict \| None` → `dict[str, Any] \| None` |

### Iteration 2 — Migration test files

| File | Changes |
|---|---|
| `tests/integration/test_migration_phase_1_2b.py` | Added `Any` import; `schema_info: dict` → `dict[str, Any]` (3 helpers), `Optional[tuple]` → `Optional[tuple[Any, ...]]`, `engine` → `engine: Any`, `phase_1_2b_schema` → `phase_1_2b_schema: dict[str, Any]` (11 test methods) |
| `tests/integration/test_migration_phase_1_2c.py` | Added `Any` import; `phase_1_2c_schema: dict` → `phase_1_2c_schema: dict[str, Any]` (6 test methods) |

### Iteration 3 — Unit test files

| File | Changes |
|---|---|
| `tests/unit/test_calibration_eligibility_service.py` | Added `Any` import; `dict \| None` → `dict[str, Any] \| None` (2 occurrences) |
| `tests/unit/test_plan_generation_templates.py` | Added `Any` import; `dict` → `dict[str, Any]` (in `lt2_low`) |
| `tests/unit/test_signal_cleaning_service.py` | Added `Any` import; `list` → `list[Any]`, `**kwargs` → `**kwargs: Any` with return type `-> Any` |
| `tests/unit/test_token_service.py` | Added `Any` import; `dict` → `dict[str, Any]`, `value` → `value: Any`, `monkeypatch` → `monkeypatch: pytest.MonkeyPatch` |
| `tests/unit/test_twin_recalibration_service.py` | Added `Any` import; `dict \| None` → `dict[str, Any] \| None` (2 occurrences) |
| `tests/unit/test_twin_recalibration_service_calibration.py` | `Optional[list]` → `Optional[list[Any]]` |
| `tests/unit/test_twin_recalibration_service_event_firing.py` | `list[dict]` → `list[dict[str, Any]]` |
| `tests/unit/test_generated_workout_repository.py` | `**overrides` → `**overrides: Any` |
| `tests/unit/test_load_computation_service.py` | Added `Any` import; `**kwargs` → `**kwargs: Any` |
| `tests/unit/test_password_hasher.py` | Added `Any` import; `value` → `value: Any` (2 occurrences) |
| `tests/unit/test_workout_generation_agent.py` | `workout` → `workout: GeneratedWorkout` with return type `-> GeneratedWorkout` (2 occurrences) |

### Iteration 4 — Final verification

- Re-ran `bash scripts/typecheck.sh tests/` → **0 errors** in both target categories
- Re-ran `bash scripts/lint.sh tests/` → Fixed 1 unused `Any` import
- Final typecheck confirms zero `reportMissingTypeArgument` and `reportMissingParameterType` errors

---

## Unfixed Diagnostics (Not in Scope)

The following diagnostics remain in `tests/` but are NOT `reportMissingTypeArgument` or `reportMissingParameterType`:
- `reportPrivateUsage` — accessing `_protected` attributes in tests
- `reportUnknownMemberType` / `reportUnknownVariableType` — cascading from mock usage and dynamic attributes
- `reportArgumentType` — type narrowing issues (e.g., `list[float]` vs `list[float | None]`)
- `reportUnknownLambdaType` — lambda parameters in mock `side_effect` assignments
- `reportAttributeAccessIssue` — accessing attributes that don't exist on stubs
- `reportUnusedVariable` / `reportUnusedFunction` — standard code hygiene issues
- Other pre-existing errors in test files not touched by this session

These are outside the scope of this diagnostic-fix session and should be addressed separately.

---

## Files Modified (Total: 24)

1. `tests/integration/test_activity_ingestion_signal_clean_enqueue_integration.py`
2. `tests/integration/test_coaching_message_schema.py`
3. `tests/integration/test_generated_workout_schema.py`
4. `tests/integration/test_migration_phase_1_2b.py`
5. `tests/integration/test_migration_phase_1_2c.py`
6. `tests/integration/test_phase_1_1_registration_regression.py`
7. `tests/integration/test_signal_clean_threshold_detection_defer_integration.py`
8. `tests/integration/test_signal_cleaning_service_integration.py`
9. `tests/integration/test_signal_cleaning_task_integration.py`
10. `tests/integration/test_threshold_detection_service_integration.py`
11. `tests/integration/test_threshold_detection_task_integration.py`
12. `tests/integration/test_training_plan_schema.py`
13. `tests/integration/test_twin_state_schema.py`
14. `tests/integration/test_workout_step_schema.py`
15. `tests/unit/test_calibration_eligibility_service.py`
16. `tests/unit/test_generated_workout_repository.py`
17. `tests/unit/test_load_computation_service.py`
18. `tests/unit/test_password_hasher.py`
19. `tests/unit/test_plan_generation_templates.py`
20. `tests/unit/test_signal_cleaning_service.py`
21. `tests/unit/test_token_service.py`
22. `tests/unit/test_twin_recalibration_service.py`
23. `tests/unit/test_twin_recalibration_service_calibration.py`
24. `tests/unit/test_twin_recalibration_service_event_firing.py`
25. `tests/unit/test_workout_generation_agent.py`

---

## Final Gate Status

| Check | Status |
|---|---|
| `bash scripts/typecheck.sh tests/` | ✅ Pass (349 remaining errors — none in target categories) |
| `bash scripts/lint.sh tests/` | ✅ Pass (22 pre-existing errors — none introduced by this session) |
