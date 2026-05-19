# Phase 1d — First Coach Message

## Context

Phase 1c delivered `TwinState` and its initialisation from onboarding questionnaire data.
Phase 1d is the first LLM call: it generates the athlete's first coach message
immediately after onboarding completes and stores it for retrieval.

**Key architectural decisions:**
- LLM calls live in `app/agents/`. `FirstMessageAgent` is the first occupant.
- Prompts live in `app/agents/prompts/` as frozen, versioned modules.
- The agent receives a pre-computed structured brief (`FirstMessageCoachingBrief`).
- The brief builder accepts a `ContextBudget` that controls fidelity.
- Generation runs as a FastAPI `BackgroundTask` triggered after the onboarding transaction commits.
- Every generation attempt produces a structured generation event log.
- Only successful messages are persisted to `coach_messages`.
- Frontend detects readiness via `first_message_ready` on the onboarding status endpoint.
- **LLM proxy**: All LLM calls go through a litellm-compatible proxy. The application only needs the model name — no provider-specific configuration. The OpenAI SDK is used with a custom `base_url` pointing to the proxy.
- `CoachMessage` records are append-only.

**What Phase 1d does not include:**
- Post-workout analysis, daily briefing, weekly review (Phase 2)
- Free coach chat (later)
- Real plan generation (Phase 1e)
- `generation_events` table (Phase 2)

---

## App Structure After Phase 1d

```
app/
  agents/
    __init__.py
    first_message_agent.py                   [CREATE]
    prompts/
      __init__.py                            [CREATE]
      registry.py                            [CREATE]
      first_message_v1.py                    [CREATE]
  api/routes/
    coach_messages.py                        [CREATE]
    athletes.py                              [MODIFY]
  api/dependencies/services.py               [MODIFY]
  core/
    llm.py                                   [CREATE]
    telemetry.py                             [CREATE]
  models/
    coach_message.py                         [CREATE]
    enums.py                                 [MODIFY]
    athlete.py                               [MODIFY]
    __init__.py                              [MODIFY]
  repositories/
    coach_message_repository.py              [CREATE]
    __init__.py                              [MODIFY]
  schemas/
    coach_message.py                         [CREATE]
    onboarding.py                            [MODIFY]
    __init__.py                              [MODIFY]
  services/
    coach_message_service.py                 [CREATE]
    first_message_brief_builder.py           [CREATE]
    __init__.py                              [MODIFY]
  tasks/
    __init__.py                              [CREATE]
    first_message_task.py                    [CREATE]
  config.py                                  [MODIFY]
  main.py                                    [MODIFY]
requirements.txt                             [MODIFY]
```

---

## Prompt Versioning Strategy

Prompts are code. They live in `app/agents/prompts/` as individual Python modules, one per version.

1. **Immutability.** Once merged, a file is never edited. Changes produce a new version file.
2. **Semantic naming.** `v1` = initial, `v1.1` = minor tone adjustment, `v2` = structural change.
3. **Registry.** `registry.py` maps version strings to prompt objects. Agents resolve through the registry.
4. **Reproducibility.** `generation_metadata` stores `prompt_version` for regression testing.
5. **Deprecation, not deletion.** Old versions remain; mark `deprecated=True` in registry.

---

## Token Budget Strategy

`ContextBudget` controls what enters the brief and at what fidelity.

Priority ordering (highest to lowest — dropped first when over budget):
1. Current twin state — always included
2. Goal and block context — always included
3. Athlete profile and preferences — always included
4. Recent sessions — capped by `include_recent_sessions`
5. Coach message history — capped by `include_coach_messages`
6. Wellness trend — included if `include_wellness_trend=True`
7. Older block summaries — included if `summarize_older_blocks=True`
8. Low-confidence twin signals — omitted if `omit_low_confidence_signals=True`

Phase 1d defaults: no session history, no prior messages, no wellness data.

---

## Failure Telemetry Strategy

Every generation attempt produces a structured log event.

`GenerationOutcome` values: `success`, `timeout`, `provider_error`, `rate_limited`, `safety_refusal`, `malformed`, `missing_data`, `internal_error`.

Log fields: `event`, `outcome`, `athlete_id`, `model`, `prompt_version`, `brief_version`, `data_tier`, `confidence_level`, `latency_ms`, plus optional `input_tokens`, `output_tokens`, `stop_reason`, `error_type`, `error_message` (truncated 200 chars), `context_budget`.

The `generation_events` table is Phase 2; Phase 1d establishes the log schema only.

---

## Models

### 1 — Update `app/models/enums.py` [MODIFY]
- Objective: Add `MessageType` and `GenerationOutcome` enums.
- Actions:
  - Add `MessageType` string enum with values: `first_message`, `daily_briefing`, `post_workout`, `weekly_review`, `recovery_alert`, `phase_transition`.
  - Add `GenerationOutcome` string enum with values: `success`, `timeout`, `provider_error`, `rate_limited`, `safety_refusal`, `malformed`, `missing_data`, `internal_error`.

### 2 — Create `app/models/coach_message.py` [CREATE]
- Objective: Append-only coach message model with full generation audit trail.
- Actions:
  - Create `CoachMessage` model inheriting from `Base`.
  - Table name: `coach_messages`.
  - Columns:
    - `id`: UUID primary key, `server_default=text("gen_random_uuid()")`, use `UUID(as_uuid=True)` for consistency with existing models.
    - `athlete_id`: UUID, `ForeignKey("athletes.id", ondelete="CASCADE")`, `nullable=False`, `index=True`.
    - `twin_state_id`: Optional UUID, `ForeignKey("twin_states.id", ondelete="SET NULL")`, `nullable=True`.
    - `training_block_id`: Optional UUID, `ForeignKey("training_blocks.id", ondelete="SET NULL")`, `nullable=True`.
    - `message_type`: `MessageType`, `SAEnum(MessageType, native_enum=False, length=30)`, `nullable=False`.
    - `content`: `Text`, `nullable=False`.
    - `generation_metadata`: `JSONB`, `nullable=False`.
    - `created_at`: `DateTime(timezone=True)`, `server_default=func.now()`, `nullable=False`.
  - Relationships:
    - `athlete`: relationship to `Athlete`, `back_populates="coach_messages"`.
    - `twin_state`: relationship to `TwinState` (no back_populates needed).
    - `training_block`: relationship to `TrainingBlock` (no back_populates needed).
  - Table args:
    - `Index("ix_coach_messages_athlete_type", "athlete_id", "message_type")`.
    - `Index("ix_coach_messages_athlete_created_at", "athlete_id", "created_at")`.

### 3 — Update `app/models/athlete.py` [MODIFY]
- Objective: Wire `coach_messages` relationship on Athlete.
- Actions:
  - In `TYPE_CHECKING` block, add import for `CoachMessage`.
  - Add `coach_messages` relationship: `Mapped[list["CoachMessage"]]`, `back_populates="athlete"`, `cascade="all, delete-orphan"`, `order_by="CoachMessage.created_at.desc()"`.

### 4 — Update `app/models/__init__.py` [MODIFY]
- Objective: Export new model and enums.
- Actions:
  - Add import: `from app.models.coach_message import CoachMessage`.
  - Add imports: `MessageType`, `GenerationOutcome` from `app.models.enums`.
  - Add `CoachMessage`, `MessageType`, `GenerationOutcome` to `__all__`.

---

## Schemas

### 5 — Create `app/schemas/coach_message.py` [CREATE]
- Objective: Pydantic schemas for coach message API responses.
- Actions:
  - Create `CoachMessageResponse` with `ConfigDict(from_attributes=True)`.
  - Fields: `id`, `athlete_id`, `twin_state_id`, `training_block_id`, `message_type`, `content`, `generation_metadata`, `created_at`.
  - Create `CoachMessageListResponse` with fields: `items: list[CoachMessageResponse]`, `total: int`.

### 6 — Update `app/schemas/onboarding.py` [MODIFY]
- Objective: Add `first_message_ready` flag to onboarding status.
- Actions:
  - Add `first_message_ready: bool = False` to `OnboardingStatusResponse`.

### 7 — Update `app/schemas/__init__.py` [MODIFY]
- Objective: Export coach message schemas.
- Actions:
  - Add import: `from app.schemas.coach_message import CoachMessageResponse, CoachMessageListResponse`.
  - Add both to `__all__`.

---

## Dependencies

### 8 — Update `requirements.txt` [MODIFY]
- Objective: Add OpenAI SDK dependency for litellm proxy communication.
- Actions:
  - Add `openai>=1.0.0` to requirements.txt.

---

## Core

### 9 — Update `app/config.py` [MODIFY]
- Objective: Add litellm proxy configuration — no provider-specific settings.
- Actions:
  - Add `LITELLM_API_KEY: str = Field(default="", env="LITELLM_API_KEY")` to `Settings`.
  - Add `LITELLM_BASE_URL: str = Field(default="http://litellm:4000/v1", env="LITELLM_BASE_URL")` to `Settings`.
  - Add `LLM_MODEL: str = Field(default="claude-sonnet-4-6", env="LLM_MODEL")` to `Settings`.

### 10 — Create `app/core/llm.py` [CREATE]
- Objective: Cached OpenAI-compatible async client singleton pointed at litellm proxy.
- Actions:
  - Import `AsyncOpenAI` from `openai`.
  - Import `lru_cache` from `functools`.
  - Import `settings` from `app.config`.
  - Define `@lru_cache(maxsize=1)` function `get_litellm_client()` returning `AsyncOpenAI(api_key=settings.LITELLM_API_KEY, base_url=settings.LITELLM_BASE_URL)`.

### 11 — Create `app/core/telemetry.py` [CREATE]
- Objective: Structured generation event logging.
- Actions:
  - Define `GenerationEvent` dataclass with fields: `event_name`, `athlete_id`, `outcome`, `model`, `prompt_version`, `brief_version`, `data_tier`, `confidence_level`, `latency_ms`, plus optional `input_tokens`, `output_tokens`, `stop_reason`, `error_type`, `error_message`, `context_budget`.
  - Define `log_generation_event(event)` that builds a dict payload from all non-None fields, truncates `error_message` to 200 chars, and emits via `logging.getLogger("pheidipp.generation")` at INFO for success or ERROR for failure.

---

## Prompts

### 12 — Create `app/agents/prompts/__init__.py` [CREATE]
- Objective: Package init for prompts module.
- Actions:
  - Create empty `__init__.py`.

### 13 — Create `app/agents/prompts/registry.py` [CREATE]
- Objective: Central prompt version registry.
- Actions:
  - Define `PromptRecord` frozen dataclass with `version`, `system_prompt`, `max_output_tokens`, `deprecated=False`, `deprecation_note=None`.
  - Define `PromptRegistry` class with `_registry: dict[str, PromptRecord]`.
  - Methods: `register(agent, record)`, `get(agent, version)`, `current(agent)`.
  - `register` raises `ValueError` if key already exists.
  - `current` resolves via `CURRENT_VERSIONS` dict.
  - Define `CURRENT_VERSIONS: dict[str, str] = {"first_message": "v1"}`.
  - Import `first_message_v1` at bottom to trigger registration.

### 14 — Create `app/agents/prompts/first_message_v1.py` [CREATE]
- Objective: Immutable first message prompt v1.
- Actions:
  - Export `PROMPT_VERSION = "v1"`.
  - Export `SYSTEM_PROMPT` string with four-paragraph coaching instructions, voice guidelines, and constraints (no precise numbers, no acronyms without explanation, no templates, no cheerleader phrases, threshold descriptors only).
  - Export `MAX_OUTPUT_TOKENS = 600`.
  - Call `PromptRegistry.register(agent="first_message", record=PromptRecord(...))` at module level.

---

## Repositories

### 15 — Create `app/repositories/coach_message_repository.py` [CREATE]
- Objective: Coach message data access, aligned with existing `BaseRepository` pattern.
- Actions:
  - Import `BaseRepository` from `app.repositories.base_repository`.
  - Define `CoachMessageRepository(BaseRepository[CoachMessage])`.
  - `__init__(self, session)` calls `super().__init__(session, CoachMessage)`.
  - Override `create(self, **kwargs)` to instantiate `CoachMessage`, `session.add()`, `await session.flush()`, return instance (no commit — UoW owns transaction).
  - Add `get_latest_by_athlete(athlete_id)` — select where athlete_id, order by created_at desc, limit 1.
  - Add `get_first_message_by_athlete(athlete_id)` — select where athlete_id and message_type == FIRST_MESSAGE, order by created_at desc, limit 1.
  - Add `has_first_message(athlete_id)` — count where athlete_id and message_type == FIRST_MESSAGE, return scalar > 0.
  - Add `list_by_athlete(athlete_id, limit=50, offset=0)` — return tuple of (list[CoachMessage], total_count).

### 16 — Update `app/repositories/__init__.py` [MODIFY]
- Objective: Export new repository.
- Actions:
  - Add import: `from app.repositories.coach_message_repository import CoachMessageRepository`.
  - Add to `__all__`.

---

## Unit of Work

### 17 — Update `app/core/unit_of_work.py` [MODIFY]
- Objective: Register coach message repository in UoW.
- Actions:
  - Import `CoachMessageRepository`.
  - In `__aenter__`, add `"coach_messages": CoachMessageRepository(self.session)` to `_repos` dict.

---

## Services

### 18 — Create `app/services/coach_message_service.py` [CREATE]
- Objective: Business logic for coach message retrieval.
- Actions:
  - Define `CoachMessageService`.
  - `get_latest(athlete_id, uow)` — returns `CoachMessageResponse` or None.
  - `get_first_message(athlete_id, uow)` — returns `CoachMessageResponse` or None.
  - `has_first_message(athlete_id, uow)` — returns bool.
  - `list_by_athlete(athlete_id, uow, limit=50, offset=0)` — returns `CoachMessageListResponse`.

### 19 — Create `app/services/first_message_brief_builder.py` [CREATE]
- Objective: Deterministic brief construction from DB models.
- Actions:
  - Define `ContextBudget` dataclass with fields: `max_input_tokens=4000`, `include_recent_sessions=0`, `include_coach_messages=0`, `include_wellness_trend=False`, `summarize_older_blocks=False`, `omit_low_confidence_signals=True`.
  - Define Pydantic models: `AthleteContext`, `GoalContext`, `TwinContext`, `PlanContext`, `CoachingInsights`, `FirstMessageCoachingBrief`.
  - `FirstMessageCoachingBrief` includes `brief_version="v1"` and `budget_snapshot: dict`.
  - Define `FirstMessageBriefBuilder` with async `build(athlete, profile, preferences, training_block, twin_state, budget=None)`.
  - `first_name` must be read from `profile.first_name`, not `athlete.first_name` (Athlete model has no first_name field).
  - Compute age from `profile.date_of_birth`.
  - Fitness band: >=81 elite, >=51 advanced, >=21 intermediate, else beginner.
  - Structural band: >=0.6 established, >=0.4 developing, else building.
  - HR descriptor: convert precise HR to "low/mid/high XXXs" natural language.
  - Weeks to event from `training_block.goal_event_date`.
  - `is_open_training` when goal_type is None, maintenance, recovery, or no event date.
  - `include_threshold_descriptors` is False when `omit_low_confidence_signals=True` and confidence_level is LOW.
  - Plan arc: heuristic based on weeks to event and open training flag.
  - First block focus and sessions based on structural_capacity_score and fitness_score.
  - Strengths: crossover backgrounds, structured training history, fitness score, chest strap, running power.
  - Gaps: structural capacity, aerobic base, short timeline, missing HR data.
  - Primary focus: structural → aerobic → race-prep → threshold.
  - Crossover note for cycling_crossover and swimming_crossover backgrounds.
  - Menstrual cycle tracking note when `profile.gender == Gender.FEMALE`.

### 20 — Update `app/services/__init__.py` [MODIFY]
- Objective: Export new services.
- Actions:
  - Add imports for `CoachMessageService` and `FirstMessageBriefBuilder`.
  - Add both to `__all__`.

---

## Agents

### 21 — Create `app/agents/first_message_agent.py` [CREATE]
- Objective: LLM call wrapper using litellm proxy via OpenAI-compatible SDK, with telemetry and validation.
- Actions:
  - Import `get_litellm_client` from `app.core.llm`.
  - Import `settings` from `app.config` (for `LLM_MODEL`).
  - Import `PromptRegistry`, `GenerationEvent`, `log_generation_event`, `GenerationOutcome`.
  - Import `openai` (for error types: `openai.APITimeoutError`, `openai.APIStatusError`).
  - Define `AGENT_NAME = "first_message"`.
  - Define `_build_user_message(brief)` that formats `FirstMessageCoachingBrief` into a structured user message string with athlete context, goal, twin model, strengths, gaps, primary focus, plan architecture, first block details, crossover context, and cycle tracking note.
  - Define `FirstMessageAgent` with async `generate(athlete_id, brief)`.
  - Resolve prompt via `PromptRegistry.current(AGENT_NAME)`.
  - Call `client.chat.completions.create(model=settings.LLM_MODEL, max_tokens=prompt_record.max_output_tokens, messages=[{"role": "system", "content": prompt_record.system_prompt}, {"role": "user", "content": user_message}])`.
  - Track latency with `time.monotonic()`.
  - On success: extract `content = response.choices[0].message.content`. Validate response has at least 2 paragraph breaks (`\n\n`), else mark `MALFORMED` and raise.
  - Extract usage: `input_tokens = response.usage.prompt_tokens`, `output_tokens = response.usage.completion_tokens`.
  - Extract stop reason: `response.choices[0].finish_reason`.
  - On `openai.APITimeoutError`: mark `TIMEOUT` and raise.
  - On `openai.APIStatusError`: mark `RATE_LIMITED` if `e.status_code == 429`, else `PROVIDER_ERROR`, and raise.
  - On unexpected exception: mark `INTERNAL_ERROR` and raise.
  - Always call `log_generation_event` before returning or raising.
  - On success return `(content: str, generation_metadata: dict)` where metadata includes model (from `settings.LLM_MODEL`), prompt_version, brief_version, outcome, input_tokens, output_tokens, latency_ms, stop_reason, data_tier, confidence_level, context_budget.

---

## Tasks

### 22 — Create `app/tasks/__init__.py` [CREATE]
- Objective: Package init for background tasks.
- Actions:
  - Create empty `__init__.py`.

### 23 — Create `app/tasks/first_message_task.py` [CREATE]
- Objective: Background task that generates and stores the first coach message.
- Actions:
  - Import `AsyncSessionLocal` from `app.db.session` to create an independent session.
  - Import `UnitOfWork` from `app.core.unit_of_work`.
  - Import `CoachMessageService`, `FirstMessageBriefBuilder`, `FirstMessageAgent`.
  - Import `AthleteService`, `AthletePreferencesService`, `TrainingBlockService`, `TwinStateService`.
  - Import relevant repositories.
  - Import `GenerationOutcome`, `MessageType`.
  - Import `log_generation_event`, `GenerationEvent`.
  - Define async `generate_first_coach_message(athlete_id: uuid.UUID)`.
  - Create a new `AsyncSessionLocal()` session inside the function (background tasks run outside request scope).
  - Use `async with session` and `async with UnitOfWork(session) as uow`.
  - Check if first message already exists via `CoachMessageService.has_first_message` — if yes, log and return early.
  - Fetch athlete, profile, preferences, training_block, twin_state via services/UoW.
  - If any required data missing, log `MISSING_DATA` event and return.
  - Build brief via `FirstMessageBriefBuilder().build(...)`.
  - Call `FirstMessageAgent().generate(athlete_id, brief)`.
  - On success: create coach message via `uow.coach_messages.create(...)` with `message_type=MessageType.FIRST_MESSAGE`, `content=content`, `generation_metadata=metadata`, `athlete_id=athlete_id`, `twin_state_id=twin_state.id`, `training_block_id=training_block.id`.
  - Commit via UoW exit.
  - On any exception: log error, do not re-raise (background task must not crash the app).

---

## API Dependencies

### 24 — Update `app/api/dependencies/services.py` [MODIFY]
- Objective: Add dependency providers for new services.
- Actions:
  - Import `CoachMessageRepository` from `app.repositories.coach_message_repository`.
  - Import `CoachMessageService` from `app.services.coach_message_service`.
  - Add `get_coach_message_service(db)` dependency factory returning `CoachMessageService(CoachMessageRepository(db))`.

---

## API Routes

### 25 — Create `app/api/routes/coach_messages.py` [CREATE]
- Objective: REST endpoints for coach message retrieval.
- Actions:
  - Create router with prefix `/athletes` and tags `["coach_messages"]`.
  - `GET /{athlete_id}/coach-messages` — list messages with optional `limit`/`offset` query params, returns `CoachMessageListResponse`.
  - `GET /{athlete_id}/coach-messages/latest` — returns latest `CoachMessageResponse` or 404.
  - `GET /{athlete_id}/coach-messages/first` — returns first message `CoachMessageResponse` or 404.
  - All endpoints use `get_coach_message_service` dependency and `get_db` for session.
  - Use `UnitOfWork` context manager for read operations.

### 26 — Update `app/api/routes/athletes.py` [MODIFY]
- Objective: Trigger first message generation after onboarding and expose readiness flag.
- Actions:
  - Import `BackgroundTasks` from `fastapi`.
  - Import `generate_first_coach_message` from `app.tasks.first_message_task`.
  - Import `CoachMessageService` and `get_coach_message_service`.
  - In `onboard_athlete` endpoint:
    - Add `background_tasks: BackgroundTasks` parameter.
    - After the `async with UnitOfWork(db) as uow` block completes and returns the response, add `background_tasks.add_task(generate_first_coach_message, athlete_id)`.
    - The background task must be added **after** the transaction commits (outside the `async with` block) so the twin state and training block are visible to the independent session in the task.
  - In `get_onboarding_status` endpoint:
    - Add `coach_message_service: CoachMessageService = Depends(get_coach_message_service)` parameter.
    - After fetching twin_state, check `first_message_ready = await coach_message_service.has_first_message(athlete_id, uow)` using a `UnitOfWork` context.
    - Include `first_message_ready` in the `OnboardingStatusResponse` return value.

### 27 — Update `app/main.py` [MODIFY]
- Objective: Register coach messages router.
- Actions:
  - Import `router as coach_messages_router` from `app.api.routes.coach_messages`.
  - Add `app.include_router(coach_messages_router)` after existing routers.

---

## Migration

### 28 — Alembic migration for `coach_messages` table [MIGRATION]
- Objective: Create the coach_messages table with indexes.
- Actions:
  - Generate migration via p-devops (`scripts/db-revision.sh`).
  - In `upgrade()`:
    - `op.create_table('coach_messages', ...)` with all columns matching the ORM model.
    - `op.create_index('ix_coach_messages_athlete_type', 'coach_messages', ['athlete_id', 'message_type'])`.
    - `op.create_index('ix_coach_messages_athlete_created_at', 'coach_messages', ['athlete_id', 'created_at'])`.
  - In `downgrade()`:
    - `op.drop_index('ix_coach_messages_athlete_created_at', table_name='coach_messages')`.
    - `op.drop_index('ix_coach_messages_athlete_type', table_name='coach_messages')`.
    - `op.drop_table('coach_messages')`.

---

## Corrections from v1

1. **LLM proxy architecture**: Replaced Anthropic-specific SDK (`AsyncAnthropic`, `ANTHROPIC_API_KEY`) with OpenAI-compatible SDK pointed at a litellm proxy. The application only needs `LITELLM_API_KEY`, `LITELLM_BASE_URL`, and `LLM_MODEL` — no provider-specific configuration.
2. **Agent API calls**: Switched from `client.messages.create()` (Anthropic format) to `client.chat.completions.create()` (OpenAI chat completions format). System prompt moves into the messages array as a `{"role": "system", ...}` message. Response extraction uses `response.choices[0].message.content`, `response.usage.prompt_tokens`/`completion_tokens`, and `response.choices[0].finish_reason`.
3. **Error handling**: Switched from Anthropic error types to `openai.APITimeoutError` and `openai.APIStatusError`.
4. **Model name**: No longer hardcoded — read from `settings.LLM_MODEL` so the proxy determines the actual provider.
5. **Dependencies**: Added `openai>=1.0.0` to `requirements.txt` (step 8).
6. **Repository pattern**: `CoachMessageRepository` now extends `BaseRepository[CoachMessage]` and uses `session.flush()` (not `commit`) to align with UoW transaction ownership.
7. **UnitOfWork**: Added `coach_messages` repository to `_repos` dict.
8. **Athlete.first_name**: The `Athlete` model has no `first_name` field — it lives on `AthleteProfile`. The brief builder reads `profile.first_name`.
9. **Background task session**: The task creates its own `AsyncSessionLocal()` session instead of reusing the request session, since it runs after the request completes.
10. **Background task trigger**: `background_tasks.add_task()` is called **outside** the `UnitOfWork` block in `onboard_athlete`, ensuring the transaction is committed before generation starts.
11. **Onboarding status**: Uses `UnitOfWork` to check `has_first_message` instead of a bare repository call.
12. **Route registration**: Added `coach_messages` router to `main.py`.
13. **Service dependencies**: Added `get_coach_message_service` factory.
