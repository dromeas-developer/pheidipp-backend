# Implementation Plan: Phase-1.5a-P1 — Remediation (Validation Gate Fix)
## Plan ID: Phase-1.5a-P1-R1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.5a
Sub-Phase Title: First Coach Message
Original Plan: `docs/implementation/phase-1/phase-1-5a-first-coach-message.md`
Validation Report: `docs/implementation/phase-1/phase-1-5a-P1_validation.md`

## Objective
This remediation plan addresses the MAJOR findings from the validation report of Phase-1.5a-P1. It fixes missing pre-condition checks in `FirstMessageAgent.generate()` that the plan pseudocode explicitly required, ensuring clear error messages instead of cryptic downstream failures when prerequisite data (TwinState, TrainingGoal, TrainingPlan) is missing. It also resolves a pre-existing missing schema export from an earlier phase. The truncation deviation is acknowledged as accepted for this phase with conditions documented below.

## Scope
- Add explicit pre-condition checks in `FirstMessageAgent.generate()` for TwinState, TrainingGoal, and TrainingPlan existence **before** context assembly and LLM call
- Add missing `WeeklyScheduleDayPatchIn` export to `app/schemas/__init__.py` (pre-existing issue)
- Add a TODO marker in `ContextBudgetService` documenting the accepted truncation deviation

## Out Of Scope
- Implementing full priority-weighted truncation logic in `ContextBudgetService` — deferred to Phase 1.6 (see Architect Decision below)
- Moving `build_first_message_agent()` from `coach.py` to `deps.py` — accepted deviation (colocation with usage is acceptable)
- Any changes to prompt templates, voice validation, or LLM integration
- Any changes to repository implementations
- Any changes to API route behavior or response schemas

## Architect Decisions

### DEV-001: Truncation Deviation Accepted for Phase 1.5a

**Finding**: `ContextBudgetService.build_first_message_context()` logs a warning when estimated tokens exceed 5000 but does NOT perform actual truncation. The architecture invariant states "Context windows are hard limits, not targets" and requires "Priority-Weighted Truncation: remove lowest-weight sections first."

**Decision**: ACCEPT deviation for Phase 1.5a with conditions.

**Rationale**:
- At onboarding (TwinState confidence=LOW, data_tier=3), context is structurally sparse — most fields are null or simple strings, making it highly unlikely to exceed 5000 tokens in practice
- The warning log provides observability if the budget is ever exceeded
- Full priority-weighted truncation logic (section removal, string truncation fallback) is complex and should be validated against real token usage data before implementation
- Phase 1.6 (post-workout agent) will have significantly larger context (6000 tokens with session details, objectives, comparable sessions) and is the appropriate phase to implement and validate truncation

**Conditions**:
1. The warning log MUST remain active (already implemented)
2. A TODO marker MUST be added to `ContextBudgetService` documenting this deviation and its scope
3. Full truncation implementation MUST be completed before Phase 1.6 ships
4. If any athlete at onboarding produces context exceeding 5000 tokens in production, this deviation is immediately revoked and truncation must be implemented as an emergency fix

**Status**: Accepted. Does not block validation gate.

## Architecture Contracts

Entities and files this plan modifies or depends on:

- `03-agents/first-message-agent.md` — DEPENDS ON (plan pseudocode defines pre-condition checks)
- `04-platform/context-budget-service.md` — DEPENDS ON (acknowledges truncation deviation)
- `app/services/first_message_agent.py` — MODIFIES (adds pre-condition checks)
- `app/services/context_budget_service.py` — MODIFIES (adds TODO marker for truncation deviation)
- `app/schemas/__init__.py` — MODIFIES (adds missing export)

## Invariants

The following invariants MUST be preserved (unchanged from original plan):

**From `01-entities/coaching-message.md`:**
- `content` is never modified after creation. Messages are immutable.
- `first_message` — only one per athlete per active goal.

**From `01-entities/generation-event.md`:**
- Every LLM call writes a `GenerationEvent`, whether successful or not.
- `failure_reason` is never null when `success = false`.

**From original plan pseudocode (`Phase-1.5a-P1`):**
- `FirstMessageAgent.generate()` MUST verify TwinState, TrainingGoal, and TrainingPlan existence BEFORE context assembly and LLM call.

## Implementation Steps

### Step 1: Add pre-condition checks in FirstMessageAgent.generate() [OWNER: Coder]

Modify `app/services/first_message_agent.py` to add explicit pre-condition checks for TwinState, TrainingGoal, and TrainingPlan existence. These checks must execute **before** calling `build_first_message_context()` and **before** any LLM interaction.

**Current code (lines 141-148):**
```python
# Pre-condition: no existing first message.
existing = await self._coaching_messages.get_existing_first_message(athlete_id)
if existing:
    raise FirstMessageAlreadyExistsError(existing.id)

# Assemble context.
context = await self._context_budget.build_first_message_context(athlete_id)
```

**Required changes:**
After the existing `FirstMessageAlreadyExistsError` check and before context assembly, insert three explicit pre-condition checks:

1. **TwinState check**: Verify latest TwinState exists for this athlete. If not, raise `LLMServiceUnavailableError` with a clear message indicating TwinState is required.
2. **TrainingGoal check**: Verify active TrainingGoal exists for this athlete. If not, raise `LLMServiceUnavailableError` with a clear message indicating an active TrainingGoal is required.
3. **TrainingPlan check**: Verify active TrainingPlan exists for this athlete. If not, raise `LLMServiceUnavailableError` with a clear message indicating an active TrainingPlan is required.

**Repository access:**
- `TwinStateRepository`: Already available via `self._context_budget._twin_states` (used later in success path). For cleaner access, you may use this existing reference.
- `TrainingGoalRepository`: NOT currently injected into `FirstMessageAgent`. Must be added to `__init__` and stored as `self._training_goals`.
- `TrainingPlanRepository`: NOT currently injected into `FirstMessageAgent`. Must be added to `__init__` and stored as `self._plans`.

**Constructor changes:**
Add `training_goals` and `plans` parameters to `__init__` and store them as instance attributes. These repositories are needed for the pre-condition checks.

**API wiring update:**
Update `build_first_message_agent()` in `app/api/v1/coach.py` to pass the new repository dependencies to the `FirstMessageAgent` constructor.

**Error messages:**
Use clear, actionable messages suitable for the 503 response:
- TwinState missing: `"twin state not available; athlete must complete onboarding before coach message generation"`
- TrainingGoal missing: `"active training goal not available; athlete must set a goal before coach message generation"`
- TrainingPlan missing: `"active training plan not available; athlete plan must be generated before coach message generation"`

**Placement in generate() flow:**
```
generate(athlete_id):
  1. Check existing first_message → 409 if exists
  2. Check TwinState exists → 503 if missing         ← NEW
  3. Check active TrainingGoal exists → 503 if missing ← NEW
  4. Check active TrainingPlan exists → 503 if missing ← NEW
  5. Assemble context via ContextBudgetService
  6. Load prompt
  7. Call LLM
  8. Validate output
  9. Write GenerationEvent + CoachingMessage
```

**Note on the existing TwinState check at line 223**: The current code fetches TwinState again in the success path to get `twin_state.id` for the CoachingMessage FK. Keep that check — it serves a different purpose (fetching the ID for the FK). The new pre-condition check is a gate that prevents wasted work.

### Step 2: Add TODO marker for truncation deviation in ContextBudgetService [OWNER: Coder]

Modify `app/services/context_budget_service.py` at the truncation location (around line 369-379) to add a clear TODO marker documenting the accepted deviation.

Replace the current comment:
```python
# Truncation for MVP Phase 1.5a — simplified: we only truncate
# section-by-section for non-first-message agents. FirstMessage
# gets the full context for now. Future phases tighten this.
return context
```

With a documented TODO:
```python
# TODO (DEV-001): Implement priority-weighted truncation per architecture
# contract (04-platform/context-budget-service.md). Truncation was deferred
# from Phase 1.5a because onboarding context (LOW confidence, sparse data)
# is highly unlikely to exceed 5000 tokens. MUST be implemented before
# Phase 1.6 (PostWorkoutAgent) ships, as its context budget (6000 tokens)
# is more likely to be exceeded.
#
# Acceptance: Architect (2026-06-28)
# Tracking: See docs/implementation/phase-1/phase-1-5a-P1-remediation.md
# Deviation: docs/implementation/phase-1/phase-1-5a-P1_validation.md
if estimated > MAX_TOKENS["first_message"]:
    _logger.warning(...)
# MVP: return full context without truncation (see TODO above)
return context
```

This change is documentation-only — no behavioral changes to the truncation logic.

### Step 3: Add missing WeeklyScheduleDayPatchIn export [OWNER: Coder]

Modify `app/schemas/__init__.py` to add the missing `WeeklyScheduleDayPatchIn` export.

This is a pre-existing issue from Phase 1.3/1.4, flagged in `implemented-state.md` under "Execution Readiness → Missing Exports." Fix it now since we're touching this file anyway.

Locate where `WeeklyScheduleDayIn` and `WeeklyScheduleDayOut` are imported in `app/schemas/__init__.py` and add `WeeklyScheduleDayPatchIn` to the same import line.

## Testing Requirements

### Pre-condition Checks
- [ ] Calling `POST /athletes/{id}/coach/first-message` when no TwinState exists returns 503 with clear error message
- [ ] Calling `POST /athletes/{id}/coach/first-message` when no active TrainingGoal exists returns 503 with clear error message
- [ ] Calling `POST /athletes/{id}/coach/first-message` when no active TrainingPlan exists returns 503 with clear error message
- [ ] Calling `POST /athletes/{id}/coach/first-message` when all pre-conditions are met (TwinState, TrainingGoal, TrainingPlan exist) proceeds to LLM call normally (existing behavior preserved)
- [ ] When a pre-condition fails, NO `GenerationEvent` is written (the LLM was never called)
- [ ] When a pre-condition fails, NO `CoachingMessage` is created

### Truncation TODO
- [ ] `ContextBudgetService` behavior is unchanged — no regression in token estimation or context assembly
- [ ] TODO marker is present and searchable in codebase

### Schema Export
- [ ] `WeeklyScheduleDayPatchIn` is importable from `app/schemas`
- [ ] No import errors in `app/schemas/__init__.py`

## Coder Handoff Notes

### Coder Scope
```
Execute:  Steps 1, 2, 3  [OWNER: Coder]
Skip:     (none — all steps are coder-owned)
```

### Known Risks

**Constructor parameter ordering**: Adding `training_goals` and `plans` to `FirstMessageAgent.__init__` could affect existing callers. The only caller is `build_first_message_agent()` in `app/api/v1/coach.py`, which is updated in Step 1. Use keyword arguments to be safe.

**Repository method names**: Verify the exact method names for fetching active goal and plan:
- `TrainingGoalRepository`: Look for `get_active(athlete_id)` or similar
- `TrainingPlanRepository`: Look for `get_active_for_athlete(athlete_id)` or similar
These are used in `ContextBudgetService.build_first_message_context()` — reuse the same method names for consistency.

### Things That Are Easy To Get Wrong

**Don't duplicate the context budget fetch**: The pre-condition checks should use lightweight existence queries, NOT re-fetch the full entities. The `ContextBudgetService.build_first_message_context()` will fetch them again anyway. The pre-condition checks are just guards to fail fast with a clear message. However, given that the repositories don't currently have lightweight `exists()` methods, it's acceptable to call the same getter methods the budget service uses (e.g., `get_active()`). The double-fetch is a minor performance cost and can be optimised in a future phase.

**Don't remove the existing TwinState fetch in the success path**: Lines 223-226 of `first_message_agent.py` fetch `TwinState` to get its ID for the `CoachingMessage.twin_state_id` FK. Keep this — the new pre-condition check is a gate, the success-path fetch is for the FK value.

**TrainingPlanRepository method name**: The existing code in `ContextBudgetService` calls `self._plans.get_active_for_athlete(athlete_id)`. Verify this method exists on `TrainingPlanRepository` and use the same call for the pre-condition check.

### Suggested Implementation Sequence

1. **Step 3 first** (schema export) — mechanical change, zero risk
2. **Step 2** (TODO marker) — documentation-only, zero risk
3. **Step 1** (pre-condition checks) — the substantive change; do last

Step 1 internal sequence:
1. Add `training_goals` and `plans` parameters to `FirstMessageAgent.__init__`
2. Update `build_first_message_agent()` in `coach.py` to pass the new repos
3. Insert pre-condition checks in `generate()` before context assembly
4. Verify existing behavior with all pre-requisites present

### Validation Gate

This remediation plan addresses the validation report findings as follows:

| Finding | Classification | Remediation |
|---------|---------------|-------------|
| Missing pre-condition checks | MAJOR | Step 1 — adds explicit checks |
| ContextBudgetService truncation incomplete | MAJOR + DEVIATION | DEV-001 — accepted deviation, Step 2 adds TODO |
| `WeeklyScheduleDayPatchIn` export missing | MINOR | Step 3 — adds export |
| `build_first_message_agent` location | MINOR | Accepted — colocation with usage is fine |

After this remediation, the validation gate should pass.

### Complete Validation Findings Disposition

All findings from the validation report are addressed below:

| # | Finding | Severity | Disposition | Action |
|---|---------|----------|-------------|--------|
| 1 | ContextBudgetService truncation incomplete | MAJOR | Accepted deviation (DEV-001) | Step 2: Add TODO marker |
| 2 | Missing pre-condition checks in FirstMessageAgent | MAJOR | Fixed | Step 1: Add explicit checks |
| 3 | Simplified truncation (hard limit → soft limit) | DEVIATION | Accepted with conditions | DEV-001 |
| 4 | Schema missing `twin_state_id` documentation | MINOR | No action needed | Validation report confirms current schema is correct for responses |
| 5 | `build_first_message_agent` location deviation | MINOR | Accepted | Colocation with usage is acceptable |
| 6 | Prompt file naming convention | MINOR | N/A | Already compliant (✅ in validation report) |
| 7 | Missing `WeeklyScheduleDayPatchIn` export | MINOR | Fixed | Step 3: Add export |

**Why only 1 of 4 minor findings was included:**
- Finding #4: Documentation issue, not code — validation report itself confirms correctness
- Finding #5: Acceptable deviation, no code change needed
- Finding #6: Already compliant per validation report
- Finding #7: Pre-existing issue, included opportunistically since we're modifying `app/schemas/__init__.py`
