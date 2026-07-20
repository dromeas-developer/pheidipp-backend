> **Baseline — migrated from** `docs/implementation/phase-1/phase-1-5a-first-coach-message.md` + `phase-1-5a-P1-remediation.md` **on** 2026-07-19.
> This plan documents what was built in Phase 1-5a, including post-validation remediation, verified against the current codebase on 2026-07-19.

## Batch Objective

Deliver the athlete's first interaction with the coach: a four-paragraph first message triggered manually via API endpoint after the athlete completes onboarding (post training plan generation). The message demonstrates that the coach has read and understood the athlete's specific data. The plan builds the complete platform infrastructure for LLM agents (PromptRegistry, ContextBudgetService, TwinContextAssembler), implements the FirstMessageAgent itself, and exposes the API surface.

## Preconditions

- TwinState exists (from phase-1-3 onboarding/twin bootstrap)
- TrainingGoal exists with active goal (from phase-1-4 plan generation)
- TrainingPlan exists with active plan (from phase-1-4 plan generation)
- LiteLLM proxy is deployed and configured (ADR-007)
- `coaching_messages` and `generation_events` tables exist (from phase-1-2c migration)

## Scope

- **Repositories**: `CoachingMessageRepository` (append-only insert and retrieval), `GenerationEventRepository` (append-only insert for LLM audit trail)
- **Platform services**: `PromptRegistry` (loads/versions prompt templates), `ContextBudgetService` (enforces token budgets), `TwinContextAssembler` (translates TwinState into coaching-relevant language)
- **Agent**: `FirstMessageAgent` (generates four-paragraph first message using LiteLLM proxy)
- **API surface**: `POST /athletes/{id}/coach/first-message`, `GET /athletes/{id}/coach/messages`
- **Schemas**: `CoachingMessageResponse`, `MessagesListResponse`
- **Prompt template**: `app/core/prompts/first_message_v1.md` with four-paragraph structure
- **Remediation**: Pre-condition checks for TwinState, TrainingGoal, TrainingPlan in `FirstMessageAgent.generate()`
- **Remediation**: TODO marker in `ContextBudgetService` for deferred priority-weighted truncation
- **Remediation**: Missing `WeeklyScheduleDayPatchIn` export in `app/schemas/__init__.py`

## Out Of Scope

- Event-driven triggering by `onboarding_completed`
- Proactive message routing
- Post-workout messages (Phase 1-6)
- Workout generation agent (Phase 1-5b)
- Objectives, comparable session references in first message
- Weather or wellness modifiers
- Full priority-weighted truncation in ContextBudgetService (deferred, see Coder Notes)
- Direct LLM provider SDKs — all calls route through LiteLLM proxy

## Steps

1. [OWNER: Coder] Create `CoachingMessageRepository` and `GenerationEventRepository`. Implement append-only insert and read methods (no update/delete). Register in `app/repositories/__init__.py`.

2. [OWNER: Coder] Create `PromptRegistry` service. Load prompts from `app/core/prompts/{agent_name}_v{version}.md`. Return prompt content with version metadata. Cache in memory after first load. Thread-safe.

3. [OWNER: Coder] Create `TwinContextAssembler` service. Translate `TwinState` inline values into coaching-relevant language: `readiness_descriptor`, `confidence_descriptor`, `fitness_form_descriptor`, `data_tier`. Deterministic, no LLM calls.

4. [OWNER: Coder] Create `ContextBudgetService`. Implement token estimation (`JSON.stringify(obj).length / 4`). Define priority profiles per agent type. Implement `build_first_message_context(athlete_id)` with 5000 token budget. NOTE: Phase 1-5a implements logging on overflow but defers actual truncation — see Step R2 for the TODO marker.

5. [OWNER: Coder] Create `FirstMessageAgent` service. Async agent that: checks idempotency (409 if existing), assembles context via `ContextBudgetService`, loads prompt via `PromptRegistry`, calls LiteLLM proxy, validates four paragraphs, writes `GenerationEvent` (success or failure), writes `CoachingMessage` on success. Agent does NOT commit — route handler owns commit.

6. [OWNER: Coder] Create prompt template `app/core/prompts/first_message_v1.md` with four-paragraph structure: Welcome, What Was Found, The Plan, The First Block. Voice constraints: no bullets/headers/emojis, no generic affirmations, no unexplained acronyms, must reference athlete's `sport_background` and `structural_risk_flag`.

7. [OWNER: Coder] Create API schemas `CoachingMessageResponse` and `MessagesListResponse` in `app/schemas/coach.py`. Register in `app/schemas/__init__.py`.

8. [OWNER: Coder] Create API routes in `app/api/v1/coach.py`. `POST /athletes/{id}/coach/first-message` (201 on success, 409 on duplicate, 503 on LLM failure). `GET /athletes/{id}/coach/messages` with `message_type`, `limit`, `offset` query params.

9. [OWNER: Coder] Create `build_first_message_agent()` dependency factory constructing `FirstMessageAgent` with all repos, services, and LiteLLM client.

10. [OWNER: Coder] Register all new components: `coach_router` in `app/api/v1/__init__.py`, services in `app/services/__init__.py`, repositories in `app/repositories/__init__.py`.

11. [OWNER: Coder] Verify database migration status. `CoachingMessage` and `GenerationEvent` tables exist from phase-1-2c migration. Generate migration only if schema changes are needed.

### Remediation Steps

R1. [OWNER: Coder] Add pre-condition checks in `FirstMessageAgent.generate()`. Before context assembly and LLM call, verify: TwinState exists (503 if missing: "twin state not available"), active TrainingGoal exists (503 if missing), active TrainingPlan exists (503 if missing). Add `TrainingGoalRepository` and `TrainingPlanRepository` parameters to `FirstMessageAgent.__init__`. Update `build_first_message_agent()` to pass them. Placement: after existing first_message check, before `build_first_message_context()`.

R2. [OWNER: Coder] Add TODO marker in `ContextBudgetService` at the truncation location documenting that priority-weighted truncation is deferred. Full truncation must be implemented before Phase 1-6 ships. The warning log on budget overflow remains active. No behavioral change.

R3. [OWNER: Coder] Add missing `WeeklyScheduleDayPatchIn` export to `app/schemas/__init__.py` (pre-existing issue from phase-1-3/1-4).

## Context Needed

- `01-entities/coaching-message.md` — message storage contract
- `01-entities/generation-event.md` — LLM audit trail contract
- `01-entities/twin-state.md` — TwinState read contract
- `01-entities/athlete-profile.md` — profile read
- `01-entities/athlete-preferences.md` — preferences read
- `01-entities/training-goal.md` — active goal read
- `01-entities/training-plan.md` — active plan read
- `03-agents/first-message-agent.md` — agent contract
- `04-platform/context-budget-service.md` — token budget enforcement
- `docs/adr/007-litellm-proxy.md` — LLM routing decision
- `docs/vision/coach/first-message.md` — four-paragraph structure
- `docs/vision/coach/voice-and-format.md` — global voice rules
- `docs/vision/twin/confidence-and-uncertainty.md` — confidence tier language

## Batch Success Criteria

- `POST /athletes/{id}/coach/first-message` with valid onboarding returns 201 and four-paragraph `CoachingMessageResponse`
- Calling the endpoint twice returns 409 on second call with existing `message_id`
- Second call does NOT create a second `CoachingMessage` and does NOT call the LLM
- `GET /athletes/{id}/coach/messages` returns paginated message list ordered by `generated_at DESC`
- Every `CoachingMessage` has a corresponding `GenerationEvent` with `agent_name="FirstMessageAgent"`
- Every LLM call writes `GenerationEvent` (success=true) or on failure writes `GenerationEvent` with `success=false` and `failure_reason` populated
- No `CoachingMessage` created when LLM fails
- Generated message contains no bullets, headers, emojis, or generic affirmations
- Paragraph 2 references athlete's specific `sport_background` and `structural_risk_flag`
- Message could not be identical across athletes with different contexts
- LiteLLM proxy unreachable: returns 503, writes `GenerationEvent` with `failure_reason="proxy_unavailable"`
- Missing TwinState returns 503 with clear message (remediation R1)
- Missing TrainingGoal returns 503 with clear message (remediation R1)
- Missing TrainingPlan returns 503 with clear message (remediation R1)
- `WeeklyScheduleDayPatchIn` is importable from `app.schemas` (remediation R3)
- Context budget overflow logs warning but does not error (truncation deferred per remediation R2)

## Files Expected To Change

- `app/repositories/coaching_message_repository.py` — new repository
- `app/repositories/generation_event_repository.py` — new repository
- `app/services/first_message_agent.py` — new agent service (pre-condition checks from remediation)
- `app/services/context_budget_service.py` — new service (TODO marker from remediation)
- `app/services/twin_context_assembler.py` — new service
- `app/core/prompt_registry.py` — new prompt registry
- `app/core/prompts/first_message_v1.md` — new prompt template
- `app/schemas/coach.py` — new response schemas
- `app/schemas/__init__.py` — register schemas, add `WeeklyScheduleDayPatchIn` export
- `app/api/v1/coach.py` — new coach routes
- `app/api/v1/__init__.py` — register `coach_router`
- `app/repositories/__init__.py` — register new repositories
- `app/services/__init__.py` — register new services

## Coder Notes

- **Append-only commitment**: `CoachingMessage` and `GenerationEvent` repositories expose only `insert()` and read methods. No `update()`, no `delete()`. Content is never modified after creation.
- **Idempotency at service layer**: `FirstMessageAgent` checks for existing `first_message` per athlete and throws `FirstMessageAlreadyExistsError`. The API layer catches this → 409.
- **Four paragraphs vs three**: The first message is four paragraphs (Welcome, What Was Found, The Plan, The First Block) — distinct from post-workout (three paragraphs).
- **Transaction ownership**: `FirstMessageAgent` does NOT commit. All writes are flushed inside the same transaction. The route handler calls `session.commit()` after the agent returns.
- **LLM client per ADR-007**: Use `AsyncOpenAI` client configured with `settings.LITELLM_BASE_URL` and `settings.LITELLM_API_KEY`. Model name: `"cohere/command-a-plus"`. Do NOT use direct provider SDKs.
- **GenerationEvent on every call**: Even when LLM fails, write `GenerationEvent` with `success=false` and `failure_reason` populated. `input_token_count` and `output_token_count` recorded even on failure.
- **Truncation deferred**: `ContextBudgetService.build_first_message_context()` logs a warning when estimated tokens exceed 5000 but returns full context without truncation. Full priority-weighted truncation must be implemented before Phase 1-6 ships. At onboarding (LOW confidence, sparse data), context is highly unlikely to exceed 5000 tokens.
- **Pre-condition checks (remediation)**: TwinState, TrainingGoal, and TrainingPlan existence is verified BEFORE context assembly and LLM call. These fail fast with clear 503 messages rather than cryptic downstream failures.
- **Schema export (remediation)**: `WeeklyScheduleDayPatchIn` was missing from `app/schemas/__init__.py` — a pre-existing issue from phase-1-3/1-4, fixed here opportunistically.
- **Voice quality gate**: The prompt is the most important deliverable. Messages that read as templates fail the exit criterion. Sport background and structural risk MUST be referenced in paragraph 2.
