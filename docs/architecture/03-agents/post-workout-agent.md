# PostWorkoutAgent — Post-Workout Analysis Message

## Purpose
- Generates the post-workout coach message narrating pre-computed execution findings
- Receives structured findings from Python services; never derives analytical conclusions
- The most frequent message type; quality must be consistently high

## Context Budget: ~3k–6k tokens

```typescript
type PostWorkoutContext = {
  // Prescribed session
  prescribed: {
    session_type: SessionType
    phase_label: PhaseLabel
    week_number: number
    intent_description: string
    approximate_duration_minutes: number
  }

  // Pre-computed compliance (Python-derived)
  compliance: {
    duration_delta_pct: number    // actual vs prescribed
    session_type_match: boolean
    effort_delta: string | null   // if RPE captured
    athlete_notes: string | null
  }

  // Pre-computed execution findings (Python-derived, never LLM-derived)
  // null for manual entries without FIT file
  execution: ExecutionObservation['coaching_observations'] | null

  // Comparable session (Python-identified; null if no match above 0.50 threshold)
  comparable_session: ComparableSessionContext | null

  // Pre-computed objective updates (evaluated BEFORE this agent runs)
  objective_updates: {
    objective_title: string
    category: ObjectiveCategory
    direction_of_change: ObjectiveDirectionOfChange
    evidence: string        // Python-written
    is_milestone: boolean   // first 'achieved'
  }[]

  // TwinState context
  readiness_summary: {
    phase_position: string  // e.g. "week 3 of 4 in threshold development"
    confidence_level: TwinConfidenceLevel
  }
}
```

## Output Contract

```typescript
type PostWorkoutOutput = {
  content: string
  // Three natural paragraphs:
  // Para 1: Overall session summary — what happened vs what was planned
  // Para 2: Execution story — specific patterns from execution findings;
  //         if comparable_session present: explicit historical comparison
  // Para 3: Objective progress — specific movement on relevant objectives;
  //         if milestone: acknowledge explicitly before moving on
}
```

## Null Handling Rules

**`execution = null`** (manual entry, no FIT file):
- Para 1: compliance-based summary only
- Para 2: based on athlete notes if present; otherwise general session acknowledgement
- Para 3: objective updates if available; otherwise plan context

**`comparable_session = null`** (no match above 0.50):
- Para 2 omits historical comparison entirely
- Prompt instruction: "Do not reference previous sessions. Do not write 'this was your first session of this type.'"

**`objective_updates = []`** (no relevant objectives for this session type):
- Para 3 focuses on plan position and what the next session is building toward

## Voice Constraints

- Three natural paragraphs; no headers, bullets, emojis
- Para 2 names specific execution patterns — never generic ("your pacing was good")
- Para 2 names the comparable session with a specific observation ("three weeks ago you faded in rep 4; today you held it")
- Para 3 addresses objective movement with specific signal evidence from `objective_updates[n].evidence`
- Never fabricates a historical comparison if `comparable_session = null`

### Voice Rules Cross-Reference

Maps `vision/coach/voice-and-format.md` rules to agent-specific constraints. The vision defines the universal voice standard; this agent enforces it for post-workout messages.

| Vision Rule (voice-and-format.md) | Agent Constraint | Enforcement Mechanism | Applies Here? |
|---|---|---|---|
| Three natural paragraphs, no bullets/headers/emojis | "Three natural paragraphs; no headers, bullets, emojis" | Prompt constraint | ✅ Yes |
| No acronyms without explanation | Not explicitly in agent constraints | Prompt (implicit in post_workout_v1.md) | ⚠️ Verify prompt coverage |
| No raw numbers without context | Not explicitly in agent constraints | Prompt (implicit in post_workout_v1.md) | ⚠️ Verify prompt coverage |
| No generic encouragement | "never generic ('your pacing was good')" | Prompt constraint | ✅ Yes |
| Always name specific patterns | "Para 2 names specific execution patterns" | Prompt constraint + context block structure | ✅ Yes |
| Connect today to the past | "Para 2 names the comparable session with a specific observation" | Prompt constraint + `comparable_session` context | ✅ Yes |
| Balance recognition with honest coaching | Not explicitly in agent constraints | Emergent from prompt tone calibration | ⚠️ Verify prompt coverage |
| Address session in training context | `readiness_summary.phase_position` in context block | Context block provides training position | ✅ Yes (structural) |
| Tone: warm but not effusive, direct but not blunt | Not explicitly in agent constraints | Emergent from prompt tone calibration | ⚠️ Verify prompt coverage |

## Pre-conditions (must all be true before agent runs)
1. `Activity` exists and is ingested
2. `ExecutionObservation` created (or null; never pending)
3. `ObjectiveUpdateService.evaluate_post_session()` has completed
4. `ComparableSessionService.find()` has completed
5. No existing `CoachingMessage` with `message_type = 'post_workout'` for this activity

## Idempotency
`POST /athletes/{id}/activities/{id}/analyse` when analysis already exists → returns existing `CoachingMessage` (200). LLM not called.
## Prompt Location

`app/core/prompts/post_workout_v1.md` (lap-based analysis)
`app/core/prompts/post_workout_v2_segments.md` (segment-based analysis)

## Performance Constraints
- p95 < 8s (LLM latency)
- Full pipeline (ingestion → analysis → message): p95 < 60s

## Cross-References
- ExecutionObservation schema: `01-entities/execution-observation.md`
- Comparable session algorithm: `02-computations/comparable-sessions.md`
- Objective update evaluation: `02-computations/objective-management.md`
- CoachingMessage schema: `01-entities/coaching-message.md`
- Voice rules: `vision/coach/voice-and-format.md`
- Post-workout content rules: `vision/coach/post-workout.md`
