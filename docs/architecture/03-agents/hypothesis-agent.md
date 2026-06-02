# Hypothesis Agent

## Purpose
- Generates three distinct strategic approaches for race_event mode plan generation
- Explores different coaching philosophies using four reasoning dimensions
- Produces hypotheses with rationale, intensity balance, and risk notes

---

## Context Budget: ~3k–5k tokens

---

## Context Type

```typescript
type HypothesisAgentContext = {
  // Athlete state
  twin_state: TwinState
  twin_context: TwinContextSummary
  
  // Athlete preferences
  athlete_preferences: AthletePreferences
  
  // Goal definition
  goal: {
    description: string
    event_type: GoalEventType
    event_date: string
  }
  
  // Race calendar
  secondary_events: SecondaryEvent[]
  
  // Confidence gaps from twin analysis
  confidence_gaps: ConfidenceGap[]
}

type ConfidenceGap = {
  metric: string           // e.g. "LT2", "aerobic_fitness"
  confidence: 'low' | 'medium' | 'high'
  priority: 'high' | 'medium' | 'low'
}
```

---

## Output Contract

```typescript
type HypothesisAgentOutput = {
  hypotheses: StrategicHypothesis[]
}

type StrategicHypothesis = {
  name: string                           // internal label; not surfaced to athlete
  training_philosophy: string            // e.g. "mostly easy running with occasional hard sessions"
  progression_pattern: string            // e.g. "steady gradual increases"
  recovery_structure: string             // e.g. "recovery weeks every 3-4 training phases"
  intensity_balance: {
    easy_percentage: number              // 0-100
    moderate_percentage: number
    hard_percentage: number
  }
  phase_emphasis: {
    name: string
    weeks: number
    focus: string[]
  }[]
  checkpoints: {
    type: CheckpointType
    week: number
    metric: string
    session_type: string
  }[]
  rationale: string                      // why this approach suits this athlete
  risk_notes: string[]
}
```

---

## Prompt Structure

### System Prompt
- Coaching methodology principles
- Four reasoning dimensions (training philosophy, progression pattern, recovery structure, intensity balance)
- Hard invariants (no back-to-back hard sessions, 48h recovery, etc.)
- Distinctness rule: each hypothesis must differ in ≥2 dimensions

### Context
- Athlete twin state and context summary
- Athlete preferences (available days, long_workout_day)
- Goal definition (event type, date, description)
- Race calendar (secondary events)
- Confidence gaps (which metrics need calibration)

### Instructions
1. Analyse athlete profile: strengths, weaknesses, constraints, race priorities
2. Select three distinct combinations of reasoning dimensions
3. For each hypothesis:
   - Justify the approach choice
   - Address how it targets athlete weaknesses
   - Ensure all hard constraints are respected
   - Incorporate race calendar
   - Schedule checkpoints at optimal times
4. Return three hypotheses with rationale and risk notes

---

## Reasoning Dimensions

| Dimension | Options | Purpose |
|-----------|---------|---------|
| Training Philosophy | Mostly easy, threshold-focused, balanced, high-frequency | Overall approach |
| Progression Pattern | Linear, undulating, block, step | How load advances |
| Recovery Structure | Frequent, periodic, extended | Recovery cadence |
| Intensity Balance | Easy-heavy, balanced, moderate-heavy | Intent distribution |

---

## Core Rule for Distinctness

Each hypothesis must differ meaningfully across at least two of the four dimensions, while respecting all twin constraints and the race calendar.

---

## Idempotency

- **Not idempotent.** Different calls may produce different hypotheses.
- Regeneration triggers: new_block, goal_date_change, confidence_upgrade, checkpoint_completed

---

## Failure Semantics

| Scenario | Behaviour |
|---|---|
| LLM failure | Return 503; retry once |
| Invalid output (missing fields) | Return error; retry with validation feedback |
| No valid hypotheses after retries | Fall back to template-based plan |
| All hypotheses violate invariants | Return error with explanation |

---

## Cross-References

- Plan generation pipeline: `02-computations/plan-generation.md`
- Hypothesis selection: `03-agents/hypothesis-selector-agent.md`
- Session planning: `03-agents/session-planner-agent.md`
- Confidence gaps: `01-entities/twin-state.md`
- Twin context assembly: `01-entities/twin-state.md` → Context Assembly
