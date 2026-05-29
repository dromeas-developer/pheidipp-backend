# 1e — Coaching Agents Foundation
*First coach message + day-of workout generation*

## Objective

The two most important user-facing moments in the product: the first coach message
that makes an athlete feel genuinely seen, and the day-of workout that makes training
feel purposeful. Both are LLM agents that narrate pre-computed Python findings.
Prompt engineering is the primary engineering challenge here — test extensively
before wiring to endpoints.

## Scope

Prompt registry (`app/core/prompts.py`). `ContextBudgetService`. First coach message
agent. Day-of workout generation agent. `CoachingMessage` creation. `GeneratedWorkout`
creation (JSON structure — `WorkoutStep` model with `PhysiologicalIntentState` is 2c).
`GenerationEvent` logging for every LLM call.

## Non-Goals

- Post-workout analysis — deferred to 1f
- Wellness or weather modifiers on workout targets — deferred to 3b and 3d
  (adjusted_targets = theoretical_targets until then)
- `WorkoutStep` model — deferred to 2c
- Objectives in the first message — deferred to 4c
  (objectives system requires calibration data before it is meaningful)
- Comparable session references — deferred to 4b (no sessions exist yet)

## Architecture References

- LLM architecture, context window targets, agent structure:
  `architecture/llm-and-agents.md`
- `ContextBudget` abstraction: `architecture/llm-and-agents.md` → ContextBudget
- `GenerationEvent` field list: `architecture/llm-and-agents.md` → GenerationEvent Logging
- How TwinState feeds agents (context assembly): `architecture/twin-state.md`
  → How the Twin Feeds LLM Agents
- First coach message four-paragraph structure: `vision/coach/first-message.md`
- Voice and format rules: `vision/coach/voice-and-format.md`
- Day-of workout generation targets: `vision/coach/daily-view.md`
  → Two-Column Target Display

## Dependencies

Requires 1a (CoachingMessage, GeneratedWorkout, GenerationEvent models),
1b (auth), 1c (TwinState must exist), 1d (PlannedSession must exist for workout generation).

## Models Modified

No new models. CoachingMessage, GeneratedWorkout, GenerationEvent defined in 1a
are first populated here.

## Services & Tasks Introduced

**`PromptRegistry`** — loads and versions prompt templates from `app/core/prompts/`.
- `get(name, version=None) → str` — returns the versioned prompt string.
- Prompt files are markdown files in `app/core/prompts/`. One file per agent.
- Version is embedded in the file name: `first_message_v1.md`, `workout_gen_v1.md`.

**`ContextBudgetService`** (sync) — assembles and enforces context window limits.
- `build_first_message_context(athlete_id) → dict` — assembles TwinState summary,
  goal event summary, athlete profile summary, and computed observations. Enforces
  3k–5k token budget. Truncates lower-priority sections if over budget.
- `build_workout_context(athlete_id, planned_session_id) → dict` — assembles
  readiness summary, today's session intent, data tier, recovery modifier (green
  by default in Phase 1). Enforces 2k–3k token budget.

**`FirstMessageAgent`** (async) — generates the first coach message.
- `generate(athlete_id) → CoachingMessage`
- Calls `ContextBudgetService.build_first_message_context()`
- Calls Anthropic API with the first_message prompt and assembled context
- Writes `GenerationEvent` (success or failure)
- On success: writes `CoachingMessage` with `message_type = first_message`
- On failure: writes `GenerationEvent` with `success = False`; raises so caller
  can surface the error

**`WorkoutGenerationAgent`** (async) — generates the day-of workout.
- `generate(athlete_id, planned_session_id) → GeneratedWorkout`
- Calls `ContextBudgetService.build_workout_context()`
- Calls Anthropic API with the workout_gen prompt and assembled context
- Output stored as JSON in `GeneratedWorkout.workout_structure`
- `theoretical_targets` and `adjusted_targets` are identical in Phase 1
  (no wellness or weather modifiers yet)
- `recovery_modifier_level = green`, `recovery_modifier_reason = null`
- Writes `GenerationEvent` on completion

**`TwinContextAssembler`** (sync) — translates raw TwinState into coaching-relevant
language for LLM context. See `architecture/twin-state.md`.
- At LOW confidence: expresses targets as effort descriptions and ranges
- Flags structural risk for crossover athletes
- Converts data tier to plain-language capability description

## Endpoints Introduced

- `POST /athletes/{athlete_id}/coach/first-message` — triggers `FirstMessageAgent`.
  Returns the generated `CoachingMessage`. Protected by `require_self`.
  Returns 409 if a first message already exists for this athlete.
- `GET /athletes/{athlete_id}/coach/messages` — returns all CoachingMessage records
  for the athlete, ordered `generated_at` desc. Protected by `require_self`.
- `GET /athletes/{athlete_id}/today` — returns today's PlannedSession and its
  GeneratedWorkout if it exists. If no GeneratedWorkout exists yet, triggers
  `WorkoutGenerationAgent` synchronously and returns the result.
  Protected by `require_self`.
- `POST /athletes/{athlete_id}/sessions/{session_id}/generate-workout` — explicit
  workout generation trigger. Returns `GeneratedWorkout`. Protected by `require_self`.

## Key Constraints

- Every LLM call — success or failure — writes a `GenerationEvent`. No silent failures.
- Context windows are hard limits, not targets. The `ContextBudgetService` must
  enforce them before the API call, not discover they were exceeded from the response.
- The first coach message must not be regenerated once it exists. The endpoint
  returns 409 on a second call. If quality is poor, the prompt must be improved
  and re-tested before re-enabling generation.
- Workout generation is idempotent for the same `(planned_session_id, date)` pair —
  calling the endpoint twice returns the existing GeneratedWorkout rather than
  generating a second one.
- The LLM prompt for the first message is the most important engineering asset in
  Phase 1. It must be developed and tested in isolation (script or notebook) before
  the endpoint is wired. Voice quality review is a go/no-go gate.

## Done Criteria

- `POST /athletes/{athlete_id}/coach/first-message` returns a four-paragraph
  message with no bullets, no headers, no emojis, and no generic affirmations.
  The message references the athlete's specific sport background and structural
  risk flag where applicable.
- `GET /athletes/{athlete_id}/today` returns a GeneratedWorkout with a workout
  structure appropriate for the session type, data tier, and plan phase.
- A failed LLM call (e.g. API timeout) writes a `GenerationEvent` with `success = False`
  and returns a 503 to the caller — no silent data corruption.
- Calling `POST /athletes/{athlete_id}/coach/first-message` twice returns 409 on
  the second call without calling the LLM.
