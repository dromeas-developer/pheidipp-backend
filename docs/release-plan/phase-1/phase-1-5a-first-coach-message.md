# Phase 1 — First Coach Message
## Sub-Phase ID: Phase-1.5a

## Objective
Deliver the athlete's first meaningful interaction with the coach: a four-paragraph first message triggered after onboarding completes. This message must demonstrate that the coach has read and understood the athlete's specific data. At LOW confidence, the language tier is Tier 3: "Based on what you've described..." The trigger is the `onboarding_completed` event, and the message is created exactly once per active goal.

## Challenge Notes
The first coach message sets the tone for the entire coaching relationship. If it feels generic or templated, the athlete will never fully trust the coach. If it feels genuinely personal — referencing specific background, goal, and structural risk — the athlete will engage. Vision reference: `coach/first-message.md` emphaseses that this is not about data dumping but about forming a coaching relationship.

The architect must be aware that `FirstMessageAgent` is an LLM agent, not a template. It requires `ContextBudgetService` (to stay within token limits), `PromptRegistry` (for prompt versioning), and `TwinContextAssembler` (to translate twin state into coaching language). Every LLM call writes a `GenerationEvent`. The `AthleteProfile` and `AthletePreferences` created during onboarding provide the specific data that makes the message personal.

## Capabilities Delivered
- `POST /athletes/{id}/coach/first-message` — triggers `FirstMessageAgent`. Returns 409 if message already exists.
- `GET /athletes/{id}/coach/messages` — returns all `CoachingMessage` records for the athlete, ordered by `generated_at` desc
- `FirstMessageAgent` service (async, LLM)
- `ContextBudgetService` (token budget enforcement, 3k-5k tokens)
- `PromptRegistry` (loads and versions prompt templates)
- `TwinContextAssembler` (translates `TwinState` into coaching-relevant language)
- Every LLM call writes a `GenerationEvent` (success or failure)

## Architectural Contracts Required
- `01-entities/coaching-message.md`
- `01-entities/generation-event.md`
- `01-entities/twin-state.md`
- `01-entities/athlete-profile.md`
- `01-entities/athlete-preferences.md`
- `03-agents/first-message-agent.md`
- `04-platform/context-budget-service.md`

## Vision References Required
- `coach/first-message.md` — four-paragraph structure, voice constraints
- `coach/voice-and-format.md` — global voice rules
- `twin/confidence-and-uncertainty.md` — Tier 3 language tier

## Upstream Dependencies
- Phase-1.3 (Onboarding) — `AthleteProfile`, `AthletePreferences`, `TrainingGoal`, `TwinState` must exist.
- Phase-1.2c (Twin & Fitness) — `CoachingMessage`, `GenerationEvent` schema must exist.
- Phase-1.1 (Auth) — Transactional outbox (`04-platform/system-event.md`) must exist to receive and publish the `onboarding_completed` event that triggers this phase.

## Downstream Enablement
- Phase-1.5b (Workout Generation) — shares `ContextBudgetService`, `PromptRegistry`, `TwinContextAssembler`
- Phase-1.6 (FIT Import) — `PostWorkoutAgent` extends the agent foundation built here

## Invariants To Preserve
- The first coach message must not be regenerated once it exists. The endpoint returns 409 on a second call. If quality is poor, the prompt must be improved and re-tested before re-enabling generation.
- Four paragraphs: Welcome, What Was Found, The Plan, Closing.
- No bullets, no headers, no emojis, no generic affirmations.
- No acronyms without explanation (HR, LT1, GAP — all plain English).
- Paragraph 2 MUST reference the athlete's specific `sport_background` and `structural_risk_flag` where applicable.
- The message could NOT have been written without reading this athlete's specific data — if it reads as a template, it has failed.
- Every LLM call — success or failure — writes a `GenerationEvent`. No silent failures.
- Context windows are hard limits, not targets. `ContextBudgetService` enforces them before the API call.
- `first_message` — only one per athlete per active goal. 409 on second call.

## Non-Goals
- Objectives in the first message — deferred to Phase 4 (requires data)
- Comparable session references — no sessions exist yet
- Wellness or weather modifiers — deferred to Phase 3

## Exit Gate
- `POST /athletes/{id}/coach/first-message` returns a four-paragraph message with no bullets, no headers, no emojis, and no generic affirmations.
- The message references the athlete's specific sport background and structural risk flag where applicable.
- A failed LLM call (e.g. API timeout) writes a `GenerationEvent` with `success = false` and returns a 503 to the caller — no silent data corruption.
- Calling `POST /athletes/{id}/coach/first-message` twice returns 409 on the second call without calling the LLM.

## Risks
- **Prompt quality gate**: The first message is the most important engineering asset in Phase 1. It must be developed and tested in isolation (script or notebook) before the endpoint is wired. Voice quality review is a go/no-go gate.
- **Context budget overflow**: At LOW confidence, the twin state has many null fields. The `ContextBudgetService` must handle sparse data gracefully without exceeding token limits.

