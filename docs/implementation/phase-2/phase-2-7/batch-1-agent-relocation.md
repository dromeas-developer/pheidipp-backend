# Batch BRD: Phase 2.7 — Batch 1 — Agent Relocation
## Source: docs/implementation/phase-2/phase-2-7/overview.md

## Batch Objective
Relocate `WorkoutGenerationAgent` and `FirstMessageAgent` from `app/services/` to `app/agents/` to enforce the stack-truth layer architecture (`agents/` → LangGraph DAGs; `agents → services`). This is a pure file relocation plus import rewiring — no behavioural change, no code edits inside the agent files. Closes finding G-05 from the gap analysis.

## Preconditions
No preconditions — this is the first batch of Phase 2.7.

## Scope
- Move `app/services/workout_generation_agent.py` → `app/agents/workout_generation_agent.py` (verbatim file content, no internal edits)
- Move `app/services/first_message_agent.py` → `app/agents/first_message_agent.py` (verbatim file content, no internal edits)
- Update import statements in the 3 files that import the agents by direct module path:
  - `app/api/v1/workout.py` — imports `WorkoutGenerationAgent`
  - `app/api/v1/coach.py` — imports `FirstMessageAgent`
  - `app/services/__init__.py` — re-exports both agents
- Populate `app/agents/__init__.py` (currently empty) to export both relocated agents
- Update `app/agents/README.md` to list the two new agents alongside `PostWorkoutAgent`
- Update `app/services/README.md` to remove the relocated agent entries (the "Coach Agents" section and the `workout_generation_agent.py` row in the "Workout Generation" section)

## Out Of Scope
- **No code changes inside the agent files.** The agents' internal logic, LLM client construction, event production, idempotency checks, and transaction boundaries remain identical. The files move verbatim.
- **No relocation of error modules.** `workout_generation_errors.py` stays in `app/services/` — it defines domain exceptions, not agent behaviour. `FirstMessageAlreadyExistsError` and `LLMServiceUnavailableError` (defined inside `first_message_agent.py`) move with the agent file since they are co-located, but their import paths in consumers must be updated.
- **No relocation of `workout_target_types.py`** — it is a constants module, not an agent. Stays in `app/services/`.
- **No relocation of `context_budget_service.py`, `twin_context_assembler.py`, `prompt_registry.py`** — these are platform services the agents depend on, not agents themselves. Stays in `app/services/` (and `app/core/` for the registry).
- **No LLM router creation.** G-01 was retracted — the agents' direct `AsyncOpenAI(base_url=settings.LITELLM_BASE_URL, ...)` construction is ADR-007 compliant. Do not introduce a router.
- **No test file changes.** Existing tests import the agents by direct module path; those imports must be updated, but the test logic does not change. The coder updates import paths in test files as part of making the suite pass — this is not a behavioural change.
- **Batches 2 and 3** (hypertables, outbox publisher, event-flow, plan-router) are not in this batch.

## Steps

### Step 1 — Move the agent files

1. [OWNER: Coder] Move `app/services/workout_generation_agent.py` to `app/agents/workout_generation_agent.py`. The file content is transferred verbatim — no edits to imports, class definition, methods, or internal logic. The file's own `from app.services...` and `from app.core...` imports remain unchanged because they reference modules that are not moving.

2. [OWNER: Coder] Move `app/services/first_message_agent.py` to `app/agents/first_message_agent.py`. Same verbatim transfer. The file's own internal imports remain unchanged.

### Step 2 — Update the agents package init

3. [OWNER: Coder] Populate `app/agents/__init__.py` (currently empty) to export the three agent classes:
   - `from app.agents.post_workout_agent import PostWorkoutAgent`
   - `from app.agents.workout_generation_agent import WorkoutGenerationAgent`
   - `from app.agents.first_message_agent import FirstMessageAgent`
   - Add all three to `__all__`.

### Step 3 — Update consuming import sites

4. [OWNER: Coder] In `app/api/v1/workout.py`, change the import `from app.services.workout_generation_agent import WorkoutGenerationAgent` to `from app.agents.workout_generation_agent import WorkoutGenerationAgent`. Do not change any other import in this file — `ContextBudgetService`, `workout_generation_errors`, and `workout_target_types` stay as `app.services` imports because those modules are not moving.

5. [OWNER: Coder] In `app/api/v1/coach.py`, change the import `from app.services.first_message_agent import (FirstMessageAgent, ...)` to `from app.agents.first_message_agent import (FirstMessageAgent, ...)`. If the import block also pulls `FirstMessageAlreadyExistsError` or `LLMServiceUnavailableError` from `app.services.first_message_agent`, those now come from `app.agents.first_message_agent` instead (they are co-located in the moved file). Do not change `ContextBudgetService` or any other `app.services` import.

6. [OWNER: Coder] In `app/services/__init__.py`, update the two import statements:
   - Line ~39: `from app.services.first_message_agent import (...)` → `from app.agents.first_message_agent import (...)`
   - Line ~108: `from app.services.workout_generation_agent import WorkoutGenerationAgent` → `from app.agents.workout_generation_agent import WorkoutGenerationAgent`
   Keep the re-exports in `__all__` so that `from app.services import WorkoutGenerationAgent` continues to resolve for any external consumer that relies on the re-export. The re-export is a backwards-compatibility shim — the canonical import path is now `app.agents`, but the shim prevents breakage.

### Step 4 — Update documentation

7. [OWNER: Coder] Update `app/agents/README.md` "Contents" section to list all three agents:
   - `post_workout_agent.py` — `PostWorkoutAgent` (already present)
   - `workout_generation_agent.py` — `WorkoutGenerationAgent` — idempotent day-of workout generation with LLM step synthesis and GenerationEvent audit
   - `first_message_agent.py` — `FirstMessageAgent` — idempotent onboarding coach message generation with context-budget enforcement
   The "Architecture Notes" and "Cross-References" sections already describe the agent pattern correctly and apply to all three — no change needed there.

8. [OWNER: Coder] Update `app/services/README.md`:
   - Remove the entire "Coach Agents" section (lines ~53-56) — `first_message_agent.py` has moved to `app/agents/`.
   - In the "Workout Generation" section (lines ~46-51), remove the `workout_generation_agent.py` row. Keep `workout_generation_errors.py` and `workout_target_types.py` rows — those modules stay in `app/services/`.
   - Do not fix the stale `calibration_eligibility_service.py` or `load_computation_service.py` descriptions in this batch — those are a separate cleanup (Batch 3).

## Context Needed
Step 1:
  Primary:    `app/services/workout_generation_agent.py`, `app/services/first_message_agent.py` (the files being moved)
  Secondary:  `app/agents/post_workout_agent.py` (the existing agent — reference for the pattern the moved files should match in location)
  Fallback:    —
  Forbidden:   Do not edit the internal content of the moved files. The move is verbatim.
Step 2:
  Primary:    `app/agents/__init__.py` (currently empty — the file to populate), `app/agents/post_workout_agent.py` (reference for the export pattern)
  Secondary:  —
  Fallback:   —
  Forbidden:  —
Step 3 (Steps 4-6):
  Primary:    `app/api/v1/workout.py` (line ~39), `app/api/v1/coach.py` (line ~34), `app/services/__init__.py` (lines ~39 and ~108) — the three files with import statements to update
  Secondary:  `app/agents/__init__.py` (output of Step 3 — confirms the new canonical import path)
  Fallback:   —
  Forbidden:  Do not change imports for `ContextBudgetService`, `workout_generation_errors`, `workout_target_types`, `PromptRegistry`, `TwinContextAssembler`, or any other `app.services` or `app.core` module — only the two agent imports change.
Step 4 (Steps 7-8):
  Primary:    `app/agents/README.md`, `app/services/README.md` (the two README files to update)
  Secondary:  —
  Fallback:   —
  Forbidden:  Do not fix the stale `calibration_eligibility_service.py` or `load_computation_service.py` descriptions in `app/services/README.md` — that is Batch 3's scope.

(This is everything relevant to the steps above. Primary items are fetched together in Pre-Flight Step 3; Secondary and Fallback are requested only on demand.)

## Batch Success Criteria
Batch 1 complete when:
- `app/agents/workout_generation_agent.py` exists and contains the `WorkoutGenerationAgent` class verbatim from the former `app/services/workout_generation_agent.py`
- `app/agents/first_message_agent.py` exists and contains the `FirstMessageAgent` class verbatim from the former `app/services/first_message_agent.py`
- `app/services/workout_generation_agent.py` and `app/services/first_message_agent.py` no longer exist (the files were moved, not copied)
- `app/agents/__init__.py` exports `PostWorkoutAgent`, `WorkoutGenerationAgent`, and `FirstMessageAgent` in `__all__`
- `from app.agents import WorkoutGenerationAgent, FirstMessageAgent, PostWorkoutAgent` resolves successfully
- `from app.agents.workout_generation_agent import WorkoutGenerationAgent` resolves successfully
- `from app.agents.first_message_agent import FirstMessageAgent` resolves successfully
- `app/api/v1/workout.py` imports `WorkoutGenerationAgent` from `app.agents.workout_generation_agent`
- `app/api/v1/coach.py` imports `FirstMessageAgent` (and any co-located error classes) from `app.agents.first_message_agent`
- `app/services/__init__.py` re-exports both agents from `app.agents.*` (backwards-compatibility shim) so `from app.services import WorkoutGenerationAgent` still resolves
- `app/agents/README.md` lists all three agents in its Contents section
- `app/services/README.md` no longer lists `first_message_agent.py` or `workout_generation_agent.py` (the "Coach Agents" section is removed; the `workout_generation_agent.py` row in "Workout Generation" is removed)
- The full existing test suite passes without modification to test logic (test files may have import-path updates only)
- The four LLM agent entry points behave identically: `POST /athletes/{id}/coach/first-message`, `GET /athletes/{id}/today`, `POST /athletes/{id}/sessions/{sid}/generate-workout`, `POST /athletes/{id}/activities/{aid}/analyse`

## Relevant Architecture Contracts
- `docs/adr/007-litellm-proxy.md` — DEPENDS ON: confirms the `AsyncOpenAI(base_url=settings.LITELLM_BASE_URL, api_key=settings.LITELLM_API_KEY)` pattern the relocated agents use is the compliant form. The agents' internal LLM client construction is not changed by this batch.
- Stack-truth instruction `001-stack-truth.md` → "Layers: agents/ → LangGraph DAGs" and "agents → services" — IMPLEMENTS: this batch relocates agent classes to the `agents/` layer where they belong.

## Relevant Invariants
- **Layer architecture (non-negotiable):** `api → services → repositories → models` and `agents → services`. No business logic in api. No direct repository access outside services. No layer skipping or reversal. — This batch enforces the `agents/` location for agent classes.
- **No behavioural change in Batch 1:** Agent relocation is a pure file move + import update. The agents' runtime behaviour, transaction boundaries, event production, and idempotency must be identical before and after.

## Relevant Notes
**Implementation Clarifications** — The two agent files move verbatim. The error modules (`workout_generation_errors.py`) stay in `app/services/` because they are domain exceptions, not agents. `FirstMessageAlreadyExistsError` and `LLMServiceUnavailableError` are defined inside `first_message_agent.py` and therefore move with it — their import paths in consumers update accordingly.

**Known Risks** — `app/services/__init__.py` currently re-exports both agents (lines ~39 and ~108). The grep confirmed all three consumers use the direct module path (`from app.services.workout_generation_agent import ...`, not `from app.services import ...`), so the risk of breaking a `from app.services import WorkoutGenerationAgent` consumer is low. The re-export shim in Step 6 is kept as a safety net. The coder must verify no test file uses the `from app.services import WorkoutGenerationAgent` form — if any do, update those imports to `from app.agents import WorkoutGenerationAgent` or rely on the shim.

## Files Expected To Change
- `[NEW] app/agents/workout_generation_agent.py` — moved verbatim from `app/services/`
- `[NEW] app/agents/first_message_agent.py` — moved verbatim from `app/services/`
- `[EXISTING — modified] app/agents/__init__.py` — populate with exports for all three agents
- `[EXISTING — modified] app/agents/README.md` — add the two new agents to Contents
- `[EXISTING — modified] app/api/v1/workout.py` — update `WorkoutGenerationAgent` import path
- `[EXISTING — modified] app/api/v1/coach.py` — update `FirstMessageAgent` import path
- `[EXISTING — modified] app/services/__init__.py` — update the two agent import paths to `app.agents.*` (keep re-exports as shim)
- `[EXISTING — modified] app/services/README.md` — remove the "Coach Agents" section and the `workout_generation_agent.py` row
- `[EXISTING — deleted] app/services/workout_generation_agent.py` — moved (not deleted by the coder; the `git mv` or equivalent removes the old path)
- `[EXISTING — deleted] app/services/first_message_agent.py` — moved

## Coder Notes
- **Use `git mv`** (or your editor's move-and-detect-rename equivalent) to move the two files. This preserves git history. Do not `cp` + `rm` — that breaks `git log --follow`.
- **The moved files' internal imports do not change.** Both agent files import from `app.services.*` (e.g. `ContextBudgetService`, `EventPublisher`, repositories) and `app.core.*` (`PromptRegistry`, `settings`). None of those modules are moving, so the internal import statements remain valid after the file relocates to `app/agents/`.
- **`FirstMessageAlreadyExistsError` and `LLMServiceUnavailableError`** are defined inside `first_message_agent.py`. When the file moves, any consumer importing them from `app.services.first_message_agent` must switch to `app.agents.first_message_agent`. Check `app/api/v1/coach.py`'s import block carefully — it may pull these error classes in the same `from app.services.first_message_agent import (...)` statement.
- **The re-export shim in `app/services/__init__.py` is intentional.** It lets `from app.services import WorkoutGenerationAgent` continue to resolve for any consumer or test that relies on the old path. The canonical path is now `app.agents`, but the shim prevents silent breakage. Do not remove the re-exports from `__all__`.
- **Do not fix the stale README descriptions** for `calibration_eligibility_service.py` ("Phase 1.6 hard-wired to false") or `load_computation_service.py` ("HR-only heuristic... deferred"). Those are stale but out of scope for this batch — Batch 3 will clean them up.
- **Verify the suite after the move.** Run the full test suite. If any test file imports the agents via `from app.services.workout_generation_agent import ...` or `from app.services.first_message_agent import ...`, update those import paths to `app.agents.*`. This is an import-path update only — do not modify test logic.