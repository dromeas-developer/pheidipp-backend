# Test Pack — Phase-1.5a-P1 (First Coach Message)

Sub-phase: **Phase-1.5a — First Coach Message**
Plan ID: **Phase-1.5a-P1**
Plan: `docs/implementation/phase-1/phase-1-5a-first-coach-message.md`
Manifest: `tests/test-manifest/phase-1-5a.yaml`

Operating mode: **Bootstrap** — no prior manifest exists. This is the
initial test generation for Phase-1.5a. All tests are newly generated.
`tests/test-manifest/index.yaml` is created from scratch.

## What This Sub-Phase Delivers

The athlete's first interaction with the coach: a four-paragraph first
message triggered manually via `POST /athletes/{id}/coach/first-message`.
The message demonstrates that the coach has read and understood the
athlete's specific data (sport background, structural risk, goal
structure) and sets the tone for the coaching relationship.

Key components:
- `FirstMessageAgent` — generates four-paragraph message via LiteLLM proxy
- `ContextBudgetService` — enforces 5000-token budget, priority-weighted truncation
- `TwinContextAssembler` — translates `TwinState` into coaching language
- `PromptRegistry` — loads and caches prompt templates from filesystem
- `CoachingMessageRepository` / `GenerationEventRepository` — append-only persistence
- `POST /athletes/{id}/coach/first-message` — 201 success, 409 duplicate, 503 LLM failure
- `GET /athletes/{id}/coach/messages` — paginated message list

## Test Files Generated

| Path | Layer | Purpose |
|------|-------|---------|
| `tests/unit/test_first_message_agent.py` | unit | FirstMessageAgent: pre-condition check, idempotency, paragraph validation, success/failure paths, token capture |
| `tests/unit/test_context_budget_service.py` | unit | ContextBudgetService: token estimation, budget enforcement, context assembly |
| `tests/unit/test_twin_context_assembler.py` | unit | TwinContextAssembler: readiness/confidence/fitness descriptors, structural risk flag |
| `tests/unit/test_prompt_registry.py` | unit | PromptRegistry: filesystem loading, caching, thread-safety, PromptNotFoundError |
| `tests/unit/test_coaching_repositories.py` | unit | Append-only invariants: no update/delete on repositories |
| `tests/integration/test_coach_endpoints.py` | integration | Full HTTP surface: 201/409/503/401/403, pagination, filtering |

## Coverage Map (sub-phase only)

### Routes
- **Covered:** `POST /athletes/{id}/coach/first-message`, `GET /athletes/{id}/coach/messages`

### Events
- **Covered:** `coaching_message_generated` (published via outbox after transaction commit)

### Invariants
- **Covered:**
  - `first_message` — only one per athlete. Second call returns 409.
  - Every `CoachingMessage` has a corresponding `GenerationEvent`
  - `GenerationEvent.failure_reason` is non-null when `success=false`
  - Messages are immutable (`content` never modified)
  - Append-only repositories (no update/delete)

## What Was Created

### New test files
- `tests/unit/test_first_message_agent.py` — 13 test methods covering agent logic
- `tests/unit/test_context_budget_service.py` — 16 test methods covering token budget
- `tests/unit/test_twin_context_assembler.py` — 14 test methods covering context assembly
- `tests/unit/test_prompt_registry.py` — 11 test methods covering prompt loading
- `tests/unit/test_coaching_repositories.py` — 9 test methods covering repository invariants
- `tests/integration/test_coach_endpoints.py` — 12 test methods covering HTTP surface

### New manifest files
- `tests/test-manifest/phase-1-5a.yaml` — sub-phase manifest with all features and execution groups
- `tests/test-manifest/index.yaml` — cross-phase selection groups (smoke/feature/regression/release)

## Operating Mode Decisions

1. **Bootstrap — no prior manifest.** This is the first test generation
   for Phase-1.5a. `tests/test-manifest/index.yaml` is created from scratch
   with empty `selection.regression` and `selection.release` (no promoted tests yet).

2. **Smoke group: unit tests only.** The smoke group includes three unit
   test files that cover the core business logic without requiring database
   or HTTP infrastructure. These are the fastest tests and serve as the
   primary tripwire.

3. **Feature group: all Phase-1.5a tests.** Per the manifest specification,
   `selection.feature` holds the current sub-phase only. All six test files
   (5 unit + 1 integration) are included.

4. **Status: generated.** All features in `phase-1-5a.yaml` carry
   `validation.implemented: true`, `validation.executable: false`,
   `validation.passed: false`. DevOps will execute and update.

5. **No mock LLM in unit tests.** The `FirstMessageAgent` tests mock the
   `AsyncOpenAI` client via `patch.object(FirstMessageAgent, "_build_llm_client")`.
   Integration tests use `patch("app.api.v1.coach.FirstMessageAgent")` to
   mock the entire agent.

6. **Append-only repository tests use real DB.** The repository tests in
   `test_coaching_repositories.py` use the actual database via `db_session`
   fixture to verify the append-only invariant (no update/delete methods exist).

## Open Items / Coverage Gaps

### Voice Compliance
The plan requires generated messages to be:
- Four paragraphs (verified in `TestParagraphValidation`)
- No bullets, headers, or emojis (helper methods in `TestVoiceComplianceHelpers`)
- No generic affirmations (helper methods in `TestVoiceComplianceHelpers`)
- No unexplained acronyms (not yet assertable without LLM mock)

These are verified through helper methods in the integration test file.
Full enforcement requires LLM integration testing with real prompts.

### Data Specificity
The plan requires:
- Paragraph 2 references `sport_background` and `structural_risk_flag`
- Message could not be identical across athletes

These require end-to-end testing with the real LLM, which is deferred
to integration testing with the LiteLLM proxy deployed.

### LiteLLM Proxy Integration
Per ADR-007, all LLM calls route through the LiteLLM proxy. Unit tests
mock the `AsyncOpenAI` client. Integration tests mock the `FirstMessageAgent`
entirely. Full proxy integration testing requires the proxy to be deployed.

## DevOps Hand-off Checklist

When DevOps picks up Phase-1.5a-P1 for execution:

1. Read `tests/test-manifest/index.yaml` -> `selection.feature` to
   resolve execution scope (the 6 Phase-1.5a test files).
2. Read `tests/test-manifest/phase-1-5a.yaml` for prerequisites — see
   `features.*.execution_prerequisites` (migrations=true, seed_data=false,
   external_services=[]).
3. Ensure `CoachingMessage` and `GenerationEvent` tables exist (likely
   from Phase-1.2c migration `79dc97d4e433`).
4. Run the suite; on PASS, set `validation.executable: true` and
   `validation.passed: true` per feature in `tests/test-manifest/phase-1-5a.yaml`.
5. Hand the report back to the Test Architect for promotion.

## Inherited Test Infrastructure Notes

The `tests/README.md` guide captures hard-won lessons from prior test
failures. Phase-1.5a tests honor those:

- Every integration test uses the `db_session` fixture; no manual
  session construction.
- Schema introspection goes through `tests/utils/schema_helpers.py` —
  not direct `sync_session.connection()` calls.
- HTTP tests use `httpx.AsyncClient` against the real FastAPI app via
  the `client` fixture.
- JWT tokens are created fresh per test via `token_service.create_access_token()`.
- Tests use unique emails via `f"{uuid.uuid4()}@example.com"` to avoid collisions.

## Reference

- Plan: `docs/implementation/phase-1/phase-1-5a-first-coach-message.md`
- Manifest: `tests/test-manifest/phase-1-5a.yaml`
- Index: `tests/test-manifest/index.yaml`
- Architecture: `docs/architecture/03-agents/first-message-agent.md`,
  `docs/architecture/04-platform/context-budget-service.md`,
  `docs/architecture/02-computations/twin-context-assembler.md`
- Vision: `docs/vision/coach/first-message.md`,
  `docs/vision/coach/voice-and-format.md`