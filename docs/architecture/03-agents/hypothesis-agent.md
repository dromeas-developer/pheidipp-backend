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
  dimensions: HypothesisDimensions       // the four reasoning dimensions
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

type HypothesisDimensions = {
  trait_vector: MethodologyTraitVector    // coaching philosophy expression (0.0–1.0 per trait)
  load_distribution: {
    low_aerobic: number                   // percentage of session time (0-1)
    high_aerobic: number
    threshold: number
    vo2max: number
    neuromuscular: number
    recovery: number
  }
  approach: 'linear' | 'non_linear' | 'block' | 'undulating' | 'step' | 'exponential'
  recovery_cycle: 'frequent' | 'infrequent' | 'micro_cycles' | 'macro_cycles'
}
```

---

## Prompt Structure

### System Prompt
- Coaching methodology principles
- Four reasoning dimensions: trait_vector (MethodologyTraitVector), load_distribution (PhysiologicalIntent allocation), approach (progression pattern), recovery_cycle
- The trait_vector uses 10 fixed traits describing coaching philosophy expression. Each trait ranges from 0.0 to 1.0. Highest layer of the three-layer hierarchy: MethodologyTraitVector → PhysiologicalIntent → SessionType.
- Hard invariants (no back-to-back hard sessions, 48h recovery, etc.)
- Distinctness rule: generate 3 hypotheses by varying at least 2 of the 4 dimensions. Each hypothesis should represent a genuinely different coaching approach for this athlete's specific objectives and race type.

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

| Dimension | Type | Purpose |
|-----------|------|---------|
| trait_vector | MethodologyTraitVector | Coaching philosophy expression — 10 fixed traits (0.0–1.0) describing training methodology emphasis |
| load_distribution | PhysiologicalIntent allocation | How session time is distributed across intensity zones |
| approach | progression pattern | How load advances over time (linear, undulating, block, etc.) |
| recovery_cycle | recovery cadence | Frequency and structure of recovery periods |

---

## Core Rule for Distinctness

Each hypothesis must differ in at least 2 of the 4 dimensions (trait_vector, load_distribution, approach, recovery_cycle), while respecting all twin constraints and the race calendar.

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

## Decision Authority

Implements the **Hypothesis Selection** authority boundary from `docs/vision/coach/decision-authority.md`.

This agent generates three distinct strategic hypotheses. It does not select — selection is performed by `hypothesis-selector-agent`. The authority boundary it serves: the coach produces genuinely different strategic perspectives, ensuring the hypothesis space is well-defined before the selection step. The athlete never sees these three hypotheses directly. They are an internal coaching exploration, not a menu of options.

---

## Cross-References

- Decision authority: `docs/vision/coach/decision-authority.md` → "Hypothesis Selection"
- Strategic hypothesis philosophy: `docs/vision/product/hypothesis-selection.md`
- Plan generation pipeline: `02-computations/plan-generation-race.md` (race mode hypothesis generation)
- Hypothesis selection: `03-agents/hypothesis-selector-agent.md`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- Confidence gaps: `01-entities/twin-state.md`
- Twin context assembly: `01-entities/twin-state.md` → Context Assembly
