# Implementation Plan: Phase-1.5a — First Coach Message
## Plan ID: Phase-1.5a-P1

## Sub-Phase Reference
Sub-Phase ID: Phase-1.5a
Sub-Phase Title: First Coach Message

## Objective
This plan delivers the athlete's first interaction with the coach: a four-paragraph first message triggered manually via API endpoint after the athlete completes onboarding (post training plan generation). The message demonstrates that the coach has read and understood the athlete's specific data — sport background, structural risk, goal structure — and sets the tone for the coaching relationship. The plan builds the complete platform infrastructure for LLM agents (PromptRegistry, ContextBudgetService, TwinContextAssembler), implements the FirstMessageAgent itself, and exposes the API surface. This is a single plan because the components are tightly coupled to deliver one coherent capability, and the testing gate requires end-to-end message generation.

## Scope
- **Repositories** (persistence layer):
  - `CoachingMessageRepository` — append-only insert and retrieval
  - `GenerationEventRepository` — append-only insert for LLM audit trail
  - Database migration for schema (if not already in place)
- **Platform services** (shared infrastructure):
  - `PromptRegistry` — loads and versions prompt templates from filesystem
  - `ContextBudgetService` — enforces token budgets, priority-weighted truncation
  - `TwinContextAssembler` — translates `TwinState` into coaching-relevant language
- **Agent service**:
  - `FirstMessageAgent` — generates four-paragraph first message using LiteLLM proxy
- **API surface**:
  - `POST /athletes/{id}/coach/first-message` — triggers generation, returns 409 if already exists
  - `GET /athletes/{id}/coach/messages` — returns all messages for the athlete
- **Schemas** (request/response contracts):
  - `CoachingMessageResponse` — message structure returned by API
  - `FirstMessageRequest` — (empty body, authentication-driven endpoint)
  - `GenerationEventResponse` — (internal observability, not exposed publicly)
- **Dependency injection**:
  - Wire `FirstMessageAgent`, `PromptRegistry`, `ContextBudgetService`, `TwinContextAssembler` into API layer
  - Register repositories and schemas in `__init__.py` files
- **Prompt template**:
  - Create `app/core/prompts/first_message_v1.md` with four-paragraph structure

## Out Of Scope
- Event-driven triggering by `onboarding_completed` (this will be implemented in Phase 1.5b when event consumer pattern exists)
- Proactive message routing (`ProactiveMessageService` for wellness alerts, phase transitions)
- `GET /athletes/{id}/coach/messages/{message_id}` — not in Phase 1.5a scope
- `POST /athletes/{id}/activities/{activity_id}/analyse` — post-workout message (Phase 1.6)
- Workout generation agent (Phase 1.5b)
- Post-workout analysis agent (Phase 1.6)
- Objectives, comparable session references in first message (deferred to Phase 4)
- Weather or wellness modifiers in first message (deferred to Phase 3)
- Direct LLM provider integration — all LLM calls route through LiteLLM proxy (see ADR-007)

## Architecture Contracts
Entities this plan implements or depends on:

- `01-entities/coaching-message.md` — IMPLEMENTS (message storage, API surface)
- `01-entities/generation-event.md` — IMPLEMENTS (LLM audit trail)
- `01-entities/twin-state.md` — DEPENDS ON (reads TwinState via repository)
- `01-entities/athlete-profile.md` — DEPENDS ON (reads profile via repository)
- `01-entities/athlete-preferences.md` — DEPENDS ON (reads preferences via repository)
- `01-entities/training-goal.md` — DEPENDS ON (reads active goal via repository)
- `01-entities/training-plan.md` — DEPENDS ON (reads active plan via repository)

Events:
- `00-foundations/event-catalogue.md` → `coaching_message_generated` — PRODUCES (after successful generation)

Platform services:
- `03-agents/first-message-agent.md` — IMPLEMENTS (agent contract)
- `04-platform/context-budget-service.md` — IMPLEMENTS (token budget enforcement)

Infrastructure decisions:
- `docs/adr/007-litellm-proxy.md` — DECISION (all LLM calls route through LiteLLM proxy; use OpenAI-compatible client)

Vision (referenced for prompt development):
- `coach/first-message.md` — DECISION (four-paragraph structure, voice constraints)
- `coach/voice-and-format.md` — DECISION (global voice rules)
- `twin/confidence-and-uncertainty.md` — DECISION (Tier 3 language tier)

## Invariants
The following invariants MUST be preserved (copied verbatim from architecture documents):

**From `01-entities/coaching-message.md`:**
- `content` is never modified after creation. Messages are immutable.
- `first_message` — only one per athlete per active goal. A second call to the generation endpoint returns 409.
- Every message creation is preceded by a `GenerationEvent` record. A `CoachingMessage` without a corresponding `GenerationEvent` indicates a recording failure — monitored as an alert.

**From `01-entities/generation-event.md`:**
- Every LLM call writes a `GenerationEvent`, whether successful or not. A `CoachingMessage` created without a corresponding `GenerationEvent` indicates an instrumentation failure.
- `failure_reason` is never null when `success = false`.
- Records are never modified after creation.
- `input_token_count` and `output_token_count` are required even on failure — capture whatever was available before failure.
- `agent_name` matches the class name of the agent that made the call.

**From `00-foundations/principles.md`:**
- **Principle 2: Python computes, LLM narrates.** All analytical computation lives in Python services. LLM agents receive pre-computed metrics and twin state summary, then reason about plan structure. Python validates all structural invariants.

**From `00-foundations/principles.md`:**
- **Principle 4: Append-only event sourcing.** All state changes are recorded as immutable events. No updates or deletes on core entities (TwinState, CoachingMessage, GenerationEvent).

**From vision/coach/first-message.md:**
- Four paragraphs: Welcome, What Was Found, The Plan, The First Block
- No bullets, no headers, no emojis, no generic affirmations
- No acronyms without explanation (HR, LT1, GAP — all plain English)
- Paragraph 2 MUST reference the athlete's specific `sport_background` and `structural_risk_flag` where applicable
- The message could NOT have been written without reading this athlete's specific data — if it reads as a template, it has failed

**From vision/coach/voice-and-format.md:**
- Three natural paragraphs (post_workout, first_message) **Note: first_message is four paragraphs**
- No acronyms without explanation
- No raw numbers without context
- No generic encouragement
- Always name specific patterns
- Balance recognition with honest coaching

## Implementation Steps

### Step 1: Create CoachingMessage and GenerationEvent repositories [OWNER: Coder]
Implement `CoachingMessageRepository` and `GenerationEventRepository` to handle persistence of coaching messages and LLM audit events. Both repositories expose append-only semantics (insert + read methods, no update/delete). Register repositories in `app/repositories/__init__.py`.

**Requirements:**
- `CoachingMessageRepository` methods: `insert()`, `get_by_athlete_id()`, `get_by_athlete_and_type()`, `get_existing_first_message()` 
- `GenerationEventRepository` methods: `insert()`, `get_by_athlete_id()` 
- Follow existing repository pattern (see `app/repositories/twin_state_repository.py`)
- Use `AsyncSession`, `Session.flush()` but not `Session.commit()` (caller manages transaction)
- Append-only invariant: no `update()` or `delete()` methods

### Step 2: Create PromptRegistry service [OWNER: Coder]
Implement `PromptRegistry` to load and version prompt templates from the filesystem. The registry reads `.md` prompt files from `app/core/prompts/` (location TBD), returns prompt content with version metadata.

**Requirements:**
- Load prompts from `app/core/prompts/{agent_name}_v{version}.md`
- Return prompt content as string
- Track version string (e.g., "v1", "v2") — embedded in prompt filename
- Cache prompts in memory after first load (avoid filesystem reads on every call)
- Thread-safe (async-safe for concurrent requests)

### Step 3: Create TwinContextAssembler service [OWNER: Coder]
Implement `TwinContextAssembler` to translate `TwinState` inline values into coaching-relevant language and descriptors. This is a deterministic computation, not LLM-based.

**Requirements:**
- Input: `TwinState` record
- Output: `TwinContextSummary` containing:
  - `readiness_descriptor` (from `readiness_level`)
  - `confidence_descriptor` (from `confidence_level`)
  - `fitness_form_descriptor` (from fitness/fatigue/form values — narrative translation)
  - `data_tier` 
- Follow pattern from `01-entities/twin-state.md` → Context Assembly section
- Deterministic, no LLM calls
- Used by both `FirstMessageAgent` (this phase) and future agents

### Step 4: Create ContextBudgetService [OWNER: Coder]
Implement `ContextBudgetService` to enforce token limits on LLM context. Uses priority-weighted truncation to degrade context gracefully when token budget is exceeded.

**Requirements:**
- Token estimation: `JSON.stringify(obj).length / 4` (deterministic, no external dependencies)
- Define `AGENT_PRIORITY_PROFILES` per agent type (FirstMessageAgent priority weights)
- Priority weights 1–100, where 100 = highest priority (removed last)
- Truncation strategy: remove lowest-weight sections first, then truncate strings if still over budget
- No errors thrown — degraded context returned if budget exceeded (log warning)
- Method: `buildFirstMessageContext(athlete_id)` returns `FirstMessageContext` with budget enforced
- Max tokens for FirstMessageAgent: 5000 tokens (architecture spec: 3k–5k)
- Latency: p95 < 100ms (excluding data fetch)

### Step 5: Create FirstMessageAgent service [OWNER: Coder]
Implement `FirstMessageAgent` to generate the four-paragraph first message. This is an async service that:
1. Calls `ContextBudgetService.buildFirstMessageContext()` to assemble context
2. Loads prompt from `PromptRegistry`
3. Calls LiteLLM proxy via OpenAI-compatible client with prompt and context
4. Writes `GenerationEvent` (success or failure)
5. On success: writes `CoachingMessage` with `message_type='first_message'`
6. On failure: writes `GenerationEvent` with `success=false`, throws exception (503 to caller)

**Requirements:**
- Pre-condition check: no existing `CoachingMessage` with `message_type='first_message'` for this goal (raise exception if exists)
- Idempotency: return existing message if already generated (or throw specific exception → 409 at API layer)
- Every LLM call writes `GenerationEvent` (before or after message creation, in same transaction)
- Capture input/output token counts from LLM response (even on failure) — the LiteLLM proxy provides these in the usage metadata
- Capture latency (time from context assembly to LLM response)
- Use OpenAI-compatible client (`from openai import AsyncOpenAI`) configured with `settings.LITELLM_BASE_URL` and `settings.LITELLM_API_KEY` per ADR-007
- Specify model as `"cohere/command-a-plus"` (default from config) or allow override
- Output: four natural paragraphs (not three), ~300–500 words

### Step 6: Create first message prompt template [OWNER: Coder]
Create `app/core/prompts/first_message_v1.md` with the four-paragraph structure specified in `vision/coach/first-message.md`. 

**Requirements:**
- **Paragraph 1 (Welcome)**: warm, brief; signals coach has been reading the athlete's data
- **Paragraph 2 (What Was Found)**: specific observations about strengths AND gaps, MUST reference athlete's `sport_background` and `structural_risk_flag` where applicable
- **Paragraph 3 (The Plan)**: training plan structure and rationale toward the goal
- **Paragraph 4 (The First Block)**: concrete preview of weeks 1-3

**Voice constraints (embedded in prompt):**
- No bullets, headers, or emojis
- No generic affirmations ("Great!", "You're making progress!")
- No raw numbers without coaching context
- No acronyms without explanation (HR, LT1, GAP — all plain English)
- No enthusiasm about the coaching journey — the coach does not sell the product
- Message could NOT have been written without reading this athlete's specific data

**Prompt must include context placeholders:**
- `{{readiness_level}}`, `{{confidence_level}}`, `{{sport_background}}`, `{{structural_risk_flag}}`
- `{{goal_type}}`, `{{goal_description}}`, `{{weeks_to_event}}`
- `{{plan_phases}}` (list with labels and weeks)
- `{{first_block_sessions}}` (session types for weeks 1-2)

### Step 7: Create API schemas (Pydantic) [OWNER: Coder]
Define request/response schemas for the coach message endpoints.

**Requirements:**
- `CoachingMessageResponse` (Pydantic):
  - `id: UUID`
  - `message_type: str` (e.g., "first_message")
  - `content: str`
  - `generated_at: datetime`
  - `prompt_version: str`
  - `twin_state_id: UUID`
- `MessagesListResponse` (Pydantic):
  - `messages: list[CoachingMessageResponse]`
  - `total: int`
- Register schemas in `app/schemas/__init__.py`

### Step 8: Create API routes [OWNER: Coder]
Implement the endpoints `/athletes/{athlete_id}/coach/first-message` and `/athletes/{athlete_id}/coach/messages`.

**Requirements:**
- `POST /athletes/{athlete_id}/coach/first-message`:
  - Authentication required (Bearer JWT)
  - Calls `FirstMessageAgent.generate()`
  - Returns 201 with `CoachingMessageResponse` on success
  - Returns 409 if first message already exists (with existing `message_id` in response)
  - Returns 503 on LLM failure (GenerationEvent written with `success=false`)
  - Idempotent: second call returns 409, does NOT re-call LLM
  
- `GET /athletes/{athlete_id}/coach/messages`:
  - Authentication required (Bearer JWT)
  - Returns list of `CoachingMessageResponse` ordered by `generated_at DESC`
  - Query params: `message_type` (optional filter), `limit` (default 20, max 100), `offset` (default 0)
  - Returns 200 with `MessagesListResponse`

**Endpoint structure:**
- Create new router file: `app/api/v1/coach.py`
- Register router in `app/api/v1/__init__.py`

### Step 9: Wire dependency injection [OWNER: Coder]
Create dependency functions to build `FirstMessageAgent` with all required dependencies.

**Requirements:**
- Add function to `app/api/deps.py` (or new `app/services/wiring.py`):
  - `build_first_message_agent()` → constructs `FirstMessageAgent` with:
    - `ContextBudgetService`
    - `PromptRegistry`
    - `TwinContextAssembler`
    - `CoachingMessageRepository`
    - `GenerationEventRepository`
    - `TwinStateRepository`
    - `AthleteProfileRepository`
    - `AthletePreferencesRepository`
    - `TrainingGoalRepository`
    - `TrainingPlanRepository`
    - LiteLLM client (via `AsyncOpenAI` configured with proxy settings per ADR-007)

### Step 10: Register new services and routes [OWNER: Coder]
Ensure all new components are properly imported and discoverable.

**Requirements:**
- Add to `app/repositories/__init__.py`: `CoachingMessageRepository`, `GenerationEventRepository`
- Add to `app/services/__init__.py`: `FirstMessageAgent`, `ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`
- Add to `app/api/v1/__init__.py`: `coach_router`
- Add to `app/schemas/__init__.py`: `CoachingMessageResponse`, `MessagesListResponse`
- Verify `app/repositories/__init__.py` imports are complete (used for migration autogenerate)

### Step 11: Generate and review database migration [OWNER: Coder]
Generate Alembic migration for any new tables (CoachingMessage, GenerationEvent schemas may already exist from Phase 1.2c, but verify).

**Requirements:**
- Run `alembic revision --autogenerate -m "add_coaching_message_generation_event"`
- Review generated migration for correctness
- If schema already exists (from 79dc97d4e433), skip generation
- Coder generates, but does not apply

### Step 12: Review and augment migration [OWNER: DevOps]
Review the generated migration for compliance with operational requirements:
- Check for missing indexes (e.g., `(athlete_id, generated_at DESC)` on `coaching_messages`)
- Check for hypertable conversions if applicable
- Add any required seed data
- Apply migration to test database: `./db-upgrade-test.sh`
- Apply migration to production database: `./db-upgrade.sh`

### Step 13: Unit tests for services [OWNER: Test Architect]
Create unit tests for the new services.

**Requirements:**
- `tests/unit/test_first_message_agent.py`:
  - Test generation with valid context (mock LiteLLM call)
  - Test 409 on duplicate generation attempt
  - Test 503 on LLM failure (GenerationEvent written with success=false)
  - Test context assembly with sparse twin state
  - Test idempotency (second call returns existing message)
- `tests/unit/test_context_budget_service.py`:
  - Test token estimation accuracy
  - Test truncation by priority weight
  - Test budget enforcement (within budget)
  - Test budget enforcement (exceeded, degraded)
- `tests/unit/test_twin_context_assembler.py`:
  - Test readiness descriptor translation
  - Test confidence descriptor translation
  - Test fitness form descriptor generation
- `tests/unit/test_prompt_registry.py`:
  - Test prompt loading from filesystem
  - Test version tracking
  - Test caching behavior

### Step 14: Integration tests for API endpoints [OWNER: Test Architect]
Create integration tests for the new API endpoints.

**Requirements:**
- `tests/integration/test_coach_endpoints.py`:
  - `POST /athletes/{id}/coach/first-message`:
    - 201 on successful generation (mock LiteLLM or use test proxy)
    - 409 on duplicate attempt (verify existing message returned)
    - 401 on unauthenticated request
    - 403 on accessing another athlete's endpoint
    - 503 on LLM failure (verify GenerationEvent written with success=false)
  - `GET /athletes/{id}/coach/messages`:
    - 200 with message list
    - 200 with filter by message_type
    - 200 with limit/offset pagination
    - 401 on unauthenticated request

### Step 15: Update test manifest [OWNER: Test Architect]
Register new tests in the manifest for this sub-phase.

**Requirements:**
- Create `tests/test-manifest/phase-1-5a.yaml`
- List all new test files
- Update `tests/test-manifest/index.yaml` to include `phase-1-5a.yaml`

## Event Contracts
### Produced
| Event | Trigger | Version | Payload |
|-------|---------|---------|---------|
| `coaching_message_generated` | Successful message creation | v1 | `{message_id, message_type, generation_event_id, prompt_version}` |

Production flow:
1. `FirstMessageAgent.generate()` completes LLM call via LiteLLM proxy
2. `GenerationEvent` inserted (success=true, token counts from proxy response)
3. `CoachingMessage` inserted (message_type=first_message)
4. Event published via `EventPublisher` (outbox pattern, after transaction commit)

### Consumed
None in this phase. Future phase will add `onboarding_completed` consumer.

**Ordering guarantee**: `FirstMessageAgent` is called manually via API endpoint after onboarding completes. No event consumer in this phase.

## Pseudocode

### FirstMessageAgent.generate(athlete_id)

```
FirstMessageAgent.generate(athlete_id):
  
  # Pre-condition check
  existing_message = CoachingMessageRepository.get_existing_first_message(athlete_id)
  if existing_message:
    raise FirstMessageAlreadyExistsError(existing_message.id)
  
  # Pre-conditions (per architecture)
  twin_state = TwinStateRepository.get_latest(athlete_id)
  if NOT twin_state:
    raise PreconditionError("TwinState must exist")
  
  active_goal = TrainingGoalRepository.get_active(athlete_id)
  if NOT active_goal:
    raise PreconditionError("Active TrainingGoal must exist")
  
  active_plan = TrainingPlanRepository.get_active(athlete_id)
  if NOT active_plan:
    raise PreconditionError("Active TrainingPlan must exist")
  
  # Assemble context via ContextBudgetService
  context = ContextBudgetService.buildFirstMessageContext(athlete_id)
  # Returns FirstMessageContext with budget enforced (max 5000 tokens)
  
  # Load prompt
  prompt_version = "v1"
  prompt = PromptRegistry.get_prompt("first_message", prompt_version)
  
  # Prepare messages for LLM (OpenAI-compatible format per ADR-007)
  messages = [
    {"role": "system", "content": prompt},
    {"role": "user", "content": render_context(context)}
  ]
  
  # Call LiteLLM proxy via OpenAI-compatible client
  llm_client = AsyncOpenAI(
    base_url=settings.LITELLM_BASE_URL,  # http://litellm:4000/v1
    api_key=settings.LITELLM_API_KEY,
  )
  
  input_token_count = ContextBudgetService.estimate_tokens({"messages": messages})
  
  start_time = now()
  try:
    # Make LLM call via proxy (proxy routes "cohere/command-a-plus" to Cohere Cloud)
    llm_response = await llm_client.chat.completions.create(
      model="cohere/command-a-plus",
      messages=messages,
      max_tokens=1000,
    )
    latency_ms = (now() - start_time).milliseconds()
    
    # Extract token counts from proxy response (ADR-007: proxy provides authoritative usage metrics)
    output_token_count = llm_response.usage.total_tokens
    generated_content = llm_response.choices[0].message.content
    
    # Validate four paragraphs
    if NOT validate_paragraph_count(generated_content) == 4:
      raise VoiceViolationError("First message must be four paragraphs")
    
    # Success path
    generation_event = GenerationEvent(
      athlete_id=athlete_id,
      agent_name="FirstMessageAgent",
      prompt_version=prompt_version,
      trigger_context="manual_api_call",
      input_token_count=input_token_count,
      output_token_count=output_token_count,
      latency_ms=latency_ms,
      success=true,
      failure_reason=null,
      created_at=now()
    )
    GenerationEventRepository.insert(generation_event)
    
    # Create CoachingMessage
    coaching_message = CoachingMessage(
      athlete_id=athlete_id,
      twin_state_id=twin_state.id,
      activity_id=null,
      message_type="first_message",
      content=generated_content,
      prompt_version=prompt_version,
      generated_at=now()
    )
    CoachingMessageRepository.insert(coaching_message)
    
    # Publish event (after transaction commit via outbox)
    EventPublisher.enqueue(
      event_name="coaching_message_generated",
      payload={
        "message_id": coaching_message.id,
        "message_type": "first_message",
        "generation_event_id": generation_event.id,
        "prompt_version": prompt_version
      }
    )
    
    return coaching_message
  
  except OpenAIError as e:  # Catches proxy errors (APITimeoutError, APIConnectionError, etc.)
    # Failure path
    latency_ms = (now() - start_time).milliseconds()
    output_token_count = 0  # or whatever was available before failure
    
    # Write GenerationEvent for failure (Invariant: every LLM call writes GenerationEvent)
    generation_event = GenerationEvent(
      athlete_id=athlete_id,
      agent_name="FirstMessageAgent",
      prompt_version=prompt_version,
      trigger_context="manual_api_call",
      input_token_count=input_token_count,
      output_token_count=output_token_count,
      latency_ms=latency_ms,
      success=false,
      failure_reason=e.error_type,  # e.g., "proxy_unavailable", "rate_limit", "timeout"
      created_at=now()
    )
    GenerationEventRepository.insert(generation_event)
    
    # No CoachingMessage created on failure
    # Raise exception → 503 at API layer
    raise LLMServiceUnavailableError(f"LLM call failed: {e}")
```

## Testing Requirements
Each testing requirement maps to a capability from the sub-phase document.

### Generation Endpoint
- [ ] `POST /athletes/{athlete_id}/coach/first-message` with valid onboarding returns 201 and `CoachingMessageResponse`
- [ ] Response `content` contains exactly four natural paragraphs (split by double newline)
- [ ] Response `message_type` is "first_message"
- [ ] Calling `POST /athletes/{athlete_id}/coach/first-message` twice returns 409 on second call
- [ ] Second call response includes existing `message_id` (from first call)
- [ ] Second call does NOT create a second `CoachingMessage` (verify database count)
- [ ] Second call does NOT call the LLM (mock LiteLLM client, verify call count = 1)

### Voice Compliance
- [ ] Generated message contains no bullet points (no lines starting with `-` or `*`)
- [ ] Generated message contains no headers (no lines starting with `#`)
- [ ] Generated message contains no emojis (no unicode emoji characters)
- [ ] Generated message contains no generic affirmations ("Great!", "Awesome!", "You're making progress!")
- [ ] Generated message does NOT contain unexplained acronyms (no "HR" alone, must be "heart rate (HR)")
- [ ] For crossover athletes (`structural_risk_flag=true`): message mentions sport background AND structural risk

### Data Specificity
- [ ] Two different athletes with different `sport_background` values receive different paragraphs
- [ ] Paragraph 2 references athlete's specific `sport_background` (verify with test data)
- [ ] Paragraph 2 references `structural_risk_flag` where applicable (true for crossover athletes)
- [ ] Message could not be identical across athletes with different contexts (verify non-template)

### LLM Failure Handling
- [ ] Simulating LiteLLM timeout returns 503 to caller
- [ ] On LiteLLM failure, `GenerationEvent` is written with `success=false`
- [ ] On LiteLLM failure, `CoachingMessage` is NOT created (verify database)
- [ ] `GenerationEvent.failure_reason` is populated with specific error type (e.g., "timeout", "rate_limit", "proxy_unavailable")
- [ ] `GenerationEvent.input_token_count` and `output_token_count` are recorded (even on failure)

### Messages List Endpoint
- [ ] `GET /athletes/{athlete_id}/coach/messages` returns 200 with `MessagesListResponse`
- [ ] Response `messages` list is ordered by `generated_at DESC` (newest first)
- [ ] Response `total` matches the number of messages in database
- [ ] Query param `message_type=first_message` filters correctly
- [ ] Query param `limit=5` returns at most 5 messages
- [ ] Query param `offset=10` skips first 10 messages

### Generation Event Integrity
- [ ] Every `CoachingMessage` has a corresponding `GenerationEvent` (verify via query)
- [ ] Every `GenerationEvent` has `agent_name="FirstMessageAgent"`
- [ ] Every `GenerationEvent` has `prompt_version` matching the prompt used
- [ ] No `CoachingMessage` exists without a `GenerationEvent` (query audit)

### Context Budget Enforcement
- [ ] Context with >5000 estimated tokens is truncated to <=5000 tokens
- [ ] Truncation removes lowest-priority sections first (verify by section names)
- [ ] Warning is logged when context exceeds budget
- [ ] Degraded context (some sections removed) is returned, not an error

### Repository Contracts
- [ ] `CoachingMessageRepository.insert()` creates append-only record (no update, no delete methods exist)
- [ ] `GenerationEventRepository.insert()` creates append-only record
- [ ] `CoachingMessageRepository.get_existing_first_message()` returns message or null
- [ ] `CoachingMessageRepository.get_by_athlete_id()` returns messages ordered by `generated_at DESC`

### Authentication & Authorization
- [ ] `POST /athletes/{athlete_id}/coach/first-message` without JWT returns 401
- [ ] `POST /athletes/{athlete_id}/coach/first-message` with JWT for different athlete returns 403
- [ ] `GET /athletes/{athlete_id}/coach/messages` without JWT returns 401

### LiteLLM Proxy Integration (per ADR-007)
- [ ] FirstMessageAgent uses `AsyncOpenAI` client (NOT direct Cohere/OpenAI SDKs)
- [ ] Client is configured with `settings.LITELLM_BASE_URL` and `settings.LITELLM_API_KEY`
- [ ] Model name passed to proxy: `"cohere/command-a-plus"` (matches config in `pheidipp_litellm_config.yaml`)
- [ ] When LiteLLM proxy is unreachable: 503 returned, GenerationEvent written with `failure_reason="proxy_unavailable"`

## Coder Handoff Notes

### Coder Scope
Execute:  Steps 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11  [OWNER: Coder] — includes migration generation
Skip:     Step 12 (DevOps — migration review and application),
          Step 13, 14, 15 (Test Architect — tests, manifest)

### Known Risks

**Prompt quality gate**: The first message is the most important coaching artifact in the product. The prompt (`app/core/prompts/first_message_v1.md`) must be developed and tested in isolation (script or notebook) before the endpoint is wired. Voice quality review is a go/no-go gate. **Do not ship a prompt that generates templated messages.**

**Context budget overflow at LOW confidence**: At onboarding, `TwinState.confidence_level = 'low'` and many fields are null. The `ContextBudgetService` must handle sparse data gracefully — do not throw errors when assembling context from null threshold values. The `TwinContextAssembler` should translate null thresholds to appropriate coaching language (e.g., "we're still learning your thresholds").

**LiteLLM proxy dependency (ADR-007)**: This plan assumes the LiteLLM proxy is deployed and configured. The proxy is accessed via `http://litellm:4000/v1` (Docker service name). If the proxy is unavailable, the agent must gracefully handle the failure and write a `GenerationEvent` with `success=false` and `failure_reason="proxy_unavailable"`.

### Things That Are Easy To Get Wrong

**LiteLLM client configuration (ADR-007)**: Do NOT use direct Cohere/OpenAI/Anthropic SDKs. Use ONLY the OpenAI-compatible client:
```python
from openai import AsyncOpenAI
from app.config import settings

llm_client = AsyncOpenAI(
    base_url=settings.LITELLM_BASE_URL,  # http://litellm:4000/v1
    api_key=settings.LITELLM_API_KEY,
)

response = await llm_client.chat.completions.create(
    model="cohere/command-a-plus",  # proxy routes to Cohere Cloud
    messages=[...],
)
```
The proxy handles provider-specific quirks (message cleaning, reasoning stripping, tool calls). The model name `"cohere/command-a-plus"` is defined in `litellm_proxy/pheidipp_litellm_config.yaml`.

**GenerationEvent MUST be written even on failure**: Wrap the entire LLM call + message creation in a try-except. In the except block, write the `GenerationEvent` with `success=false` before raising. Do not silently swallow LLM failures.

**Idempotency is at the API layer, not the service layer**: The `FirstMessageAgent` throws `FirstMessageAlreadyExistsError` when a message already exists. The API layer catches this and returns 409. Do NOT make the agent silently return the existing message.

**Four paragraphs vs three**: The vision specifies three paragraphs for some message types, but the first message is four paragraphs (Welcome, What Was Found, The Plan, The First Block). Enforce this in both the prompt and validation logic.

**Sport background and structural risk MUST be referenced in paragraph 2**: This is a hard requirement, not optional. The prompt template must include context placeholders that make this reference possible. Validation should ensure these fields are actually mentioned in the output.

**Append-only repositories**: Do not implement `update()` or `delete()` methods. If a message needs to be "updated," it must be regenerated (which is not yet specified — defer to future phase). For now, messages are immutable.

**Transaction boundaries**: The `FirstMessageAgent` manages its own transaction. Do not call `session.commit()` in the service layer. Do not pass the session around between services — each repository receives the session in its constructor.

### Suggested Implementation Sequence

While steps are numbered for dependency clarity, the coder may batch related work:

1. **Persistence layer first** (Step 1) — repositories and migration (if needed)
2. **Platform services together** (Steps 2, 3, 4) — `PromptRegistry`, `TwinContextAssembler`, `ContextBudgetService` are tightly coupled and can be developed in parallel
3. **Agent and prompt together** (Steps 5, 6) — the prompt template is part of the agent's "code"; develop them together
4. **API layer** (Steps 7, 8) — schemas and routes; these depend on the agent being complete
5. **Wiring** (Steps 9, 10) — dependency injection and registrations
6. **Migration** (Step 11) — generate, review, commit

### Voice Quality Validation

Before merging, the prompt must be validated with real athlete data. Recommended approach:
1. Create a test script that generates messages for 3-5 different athlete profiles (varying sport_background, structural_risk_flag, fitness levels)
2. Manually review each generated message against the voice constraints
3. If any message reads as templated or violates voice rules, iterate on the prompt
4. Get product/team sign-off on prompt quality before deployment

The prompt is the most important deliverable in this phase. Budget time for iterative refinement.

### Database Migration Status

From `implemented-state.md`:
- Current DB revision: `d1579f4430e7`
- Migration pending: yes

The `CoachingMessage` and `GenerationEvent` models likely exist from Phase 1.2c (migration `79dc97d4e433_phase_1_2c_twin_fitness_coaching_.py`). Verify this before generating a new migration. If the tables already exist with the correct schema, no new migration is needed.

If schema changes are required (e.g., missing indexes), create a new migration. If the schema is complete, skip Step 11 migration generation.

### LiteLLM Proxy Configuration (ADR-007)

The LiteLLM proxy is configured in three places:

1. **Environment variables** (`app/config.py`):
   - `LITELLM_API_KEY`: Authentication key for proxy access
   - `LITELLM_BASE_URL`: Default `http://litellm:4000/v1` (proxied via Docker service name)

2. **Model routing** (`litellm_proxy/pheidipp_litellm_config.yaml`):
   - Maps `"cohere/command-a-plus"` → Cohere Cloud via OpenAI compatibility layer
   - Defines per-model timeouts and retry settings
   - Default model: `cohere/command-a-plus`

3. **Custom callbacks** (`litellm_proxy/callbacks.py`):
   - `MessageHistoryCleaner`: Strips reasoning tokens, normalises tool calls, fixes empty messages
   - Logs token usage per call with cached-token breakdown
   - Registered in the proxy config file under `success_callback` and `failure_callback`

**Testing with the proxy**: For unit tests, mock the `AsyncOpenAI` client. For integration tests, either:
- Deploy the LiteLLM proxy container locally and hit the real endpoint
- Use a mock server that simulates the OpenAI-compatible API responses

**Proxy error types**: The OpenAI client raises these exceptions for proxy failures:
- `APITimeoutError`: Proxy did not respond within timeout (configured in proxy config)
- `APIConnectionError`: Cannot reach the proxy (network issue)
- `APIError`: Proxy returned an error status (4xx, 5xx)
- `AuthenticationError`: Invalid `LITELLM_API_KEY`

Capture these in the `GenerationEvent.failure_reason` field.

### Context Budget Thresholds

Per architecture (`04-platform/context-budget-service.md`):
- `first_message`: 5000 tokens max
- Token estimation: `JSON.stringify(obj).length / 4`

The `ContextBudgetService` in this phase implements only the FirstMessageAgent context builder. Future phases will add other agent context builders (workout, post_workout).

### Event Publication

The `coaching_message_generated` event is published via the outbox pattern (`SystemEvent` / `SystemEventOutbox`) after the transaction commits. Use the existing `EventPublisher` from `app/services/event_publisher.py`. Do not bypass the outbox pattern.

### Architecture Decision Record

**ADR-007 (LiteLLM proxy)**: All LLM calls must route through the LiteLLM proxy. This is a hard constraint — do not use direct provider SDKs. See `docs/adr/007-litellm-proxy.md` for the full decision rationale and compliance examples.
