> **Baseline — test companion for** `batch-1-first-coach-message.md`, migrated from `docs/implementation/phase-1/phase-1-5a-first-coach-message.md` + `phase-1-5a-P1-remediation.md` **on** 2026-07-19.

## Test Scenarios

Derived from the plan's Testing Requirements and verified against existing test files.

### Generation Endpoint — Happy Path
- Given `POST /athletes/{id}/coach/first-message` with valid onboarding (TwinState + TrainingGoal + TrainingPlan exist), returns 201 with `CoachingMessageResponse`
- Given response `content` contains exactly four natural paragraphs (split by double newline)
- Given response `message_type` is `"first_message"`
- Given `PromptRegistry` loads prompt from `app/core/prompts/first_message_v1.md`

### Generation Endpoint — Idempotency
- Given `POST /athletes/{id}/coach/first-message` called twice, second call returns 409
- Given second call response includes existing `message_id` from first call
- Given second call does NOT create a second `CoachingMessage` (verify database count)
- Given second call does NOT call the LLM (mock LiteLLM client, verify call count = 1)

### Voice Compliance
- Given generated message contains no bullet points (no lines starting with `-` or `*`)
- Given generated message contains no headers (no lines starting with `#`)
- Given generated message contains no emojis (no unicode emoji characters)
- Given generated message contains no generic affirmations ("Great!", "Awesome!", "You're making progress!")
- Given generated message does NOT contain unexplained acronyms ("HR" alone; must be "heart rate (HR)")
- Given for crossover athletes (`structural_risk_flag=true`): message mentions sport background AND structural risk

### Data Specificity
- Given two different athletes with different `sport_background` values receive different paragraph 2 content
- Given paragraph 2 references athlete's specific `sport_background`
- Given paragraph 2 references `structural_risk_flag` where applicable
- Given message could not be identical across athletes with different contexts (verify non-template)

### LLM Failure Handling
- Given LiteLLM proxy timeout, returns 503 to caller
- Given LLM failure, `GenerationEvent` is written with `success=false`
- Given LLM failure, `CoachingMessage` is NOT created (verify database)
- Given `GenerationEvent.failure_reason` is populated with specific error type ("timeout", "rate_limit", "proxy_unavailable")
- Given `GenerationEvent.input_token_count` and `output_token_count` are recorded even on failure

### Messages List Endpoint
- Given `GET /athletes/{id}/coach/messages` returns 200 with `MessagesListResponse`
- Given response `messages` list is ordered by `generated_at DESC` (newest first)
- Given response `total` matches the number of messages in database
- Given query param `message_type=first_message` filters correctly
- Given query param `limit=5` returns at most 5 messages
- Given query param `offset=10` skips first 10 messages

### Generation Event Integrity
- Given every `CoachingMessage` has a corresponding `GenerationEvent`
- Given every `GenerationEvent` has `agent_name="FirstMessageAgent"`
- Given every `GenerationEvent` has `prompt_version` matching the prompt used
- Given no `CoachingMessage` exists without a `GenerationEvent`

### Context Budget Enforcement
- Given context with >5000 estimated tokens, warning is logged (no error, no crash)
- Given budget overflow, full context is returned (truncation deferred)

### Repository Contracts
- Given `CoachingMessageRepository` has no `update()` or `delete()` methods
- Given `GenerationEventRepository` has no `update()` or `delete()` methods
- Given `CoachingMessageRepository.get_existing_first_message()` returns message or null
- Given `CoachingMessageRepository.get_by_athlete_id()` returns messages ordered by `generated_at DESC`

### Authentication & Authorization
- Given `POST /athletes/{id}/coach/first-message` without JWT returns 401
- Given `POST /athletes/{id}/coach/first-message` with JWT for different athlete returns 403
- Given `GET /athletes/{id}/coach/messages` without JWT returns 401

### LiteLLM Proxy Integration (ADR-007)
- Given `FirstMessageAgent` uses `AsyncOpenAI` client (NOT direct Cohere/OpenAI SDKs)
- Given client configured with `settings.LITELLM_BASE_URL` and `settings.LITELLM_API_KEY`
- Given model name: `"cohere/command-a-plus"`

### Remediation: Pre-condition Checks
- Given `POST /athletes/{id}/coach/first-message` when no TwinState exists, returns 503 with message "twin state not available"
- Given no active TrainingGoal exists, returns 503 with message "active training goal not available"
- Given no active TrainingPlan exists, returns 503 with message "active training plan not available"
- Given when a pre-condition fails, NO `GenerationEvent` is written (LLM was never called)
- Given when a pre-condition fails, NO `CoachingMessage` is created
- Given when all pre-conditions are met, generation proceeds normally

### Remediation: Truncation TODO
- Given `ContextBudgetService` behavior is unchanged — no regression in token estimation
- Given TODO marker is present and searchable in codebase
- Given TODO references deferred truncation and Phase 1-6

### Remediation: Schema Export
- Given `WeeklyScheduleDayPatchIn` is importable from `app.schemas`
- Given no import errors in `app/schemas/__init__.py`
