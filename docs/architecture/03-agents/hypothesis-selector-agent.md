# Hypothesis Selector Agent

## Purpose

- Scores and selects the best strategic approach from three hypotheses
- Synthesises the selected approach into a strategic framework
- Produces the complete framework including phase arc, race schedule, checkpoint schedule, and intensity balance

---

## Context Budget: ~4k–6k tokens

---

## Context Type

```typescript
type HypothesisSelectorContext = {
  // Three hypotheses from HypothesisAgent
  hypotheses: StrategicHypothesis[]
  
  // Athlete context for scoring
  twin_context: TwinContextSummary
  athlete_preferences: AthletePreferences
  
  // Goal definition
  goal: {
    event_type: GoalEventType
    event_date: string
  }
  
  // Race calendar
  secondary_events: SecondaryEvent[]
}
```

---

## Output Contract

```typescript
type HypothesisSelectorOutput = {
  selected_hypothesis_name: string
  strategic_framework: StrategicFramework
}

type StrategicFramework = {
  strategic_rationale: {
    primary_driver: string           // plain English; why this approach suits the athlete
    methodology_summary: string      // high-level approach description
    risk_notes: string[]
  }
  
  macrocycle_structure: string       // plain English description
  
  // Phase arc — strategic intent per week, no session-level detail
  phase_arc: PhaseArcEntry[]
  
  race_schedule: RaceScheduleEntry[]
  checkpoint_schedule: CheckpointDescriptor[]
  phase_adjustments: PhaseAdjustment[]
  
  intensity_distribution: {
    low_aerobic: number            // percentage of session time (0-1)
    high_aerobic: number
    threshold: number
    vo2max: number
    neuromuscular: number
    recovery: number
  }
  
  progression_model: {
    volume: string
    intensity: string
  }
  
  recovery_model: {
    type: string
    structure: string
    race_recovery: Record<string, string>
  }
  
  risk_mitigations: string[]
}

type PhaseArcEntry = {
  week_number: number
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  race_considerations?: string
  checkpoint_intent?: string
  target_session_count: number
}

type RaceScheduleEntry = {
  race: string                       // "A-race", "B-race", "C-race"
  type: GoalEventType
  week: number
  role: 'peak' | 'tune_up' | 'training'
  taper: string
  recovery: string
}

type CheckpointDescriptor = {
  type: CheckpointType
  week_number: number
  target_date: string
  target_metric: string
  session_type: string
  planner_message: string
}

type PhaseAdjustment = {
  phase: string
  adjustment: string
  detail: string
}
```

---

## Prompt Structure

### System Prompt
- Scoring criteria: twin alignment (50%), goal fit (30%), injury safety (10%)
- Constraint-first validation rules
- Strategic framework structure
- Race schedule formatting
- Checkpoint scheduling logic

### Context
- Three hypotheses with rationale and risk notes
- Athlete twin context summary
- Athlete preferences
- Goal definition
- Race calendar

### Instructions
1. **Validate each hypothesis** against hard invariants
   - Discard invalid hypotheses immediately
   - No scoring, no partial credit

2. **Score valid hypotheses** on three criteria:
   - Twin Alignment (50%): addresses strengths/weaknesses
   - Goal Fit (30%): aligns with goal type and race calendar
   - Injury Safety (10%): mitigates identified risks

3. **Select the best hypothesis** based on scores

4. **Synthesise strategic framework** from selected hypothesis:
   - Derive macrocycle structure
   - Integrate race schedule with taper/recovery windows
   - Schedule checkpoints based on confidence gaps and phase transitions
   - Define intensity balance
   - Specify progression model
   - Define recovery model
   - Identify risk mitigations

5. **Return** selected hypothesis name and strategic framework

---

## Scoring Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Twin Alignment | 50% | Addresses strengths and weaknesses identified in twin analysis |
| Goal Fit | 30% | Aligns with goal type, distance, and race calendar |
| Injury Safety | 10% | Mitigates twin-identified structural and recovery risks |

---

## Constraint-First Validation

Before scoring, each hypothesis is checked against hard invariants:

- No unsafe load spikes (≤10% weekly increase)
- No back-to-back hard sessions
- Minimum 48h between intense efforts
- Sessions only on available days
- Running-only
- Honesty invariant
- No overlapping tapers
- A-race priority
- Secondary events outside A-race taper

**Invalid hypotheses are discarded. No scoring, no partial credit.**

---

## Checkpoint Scheduling Logic

Checkpoints are scheduled based on:

| Factor | Trigger | Example |
|--------|---------|---------|
| Confidence gaps | Low/medium confidence in a metric | LT2 confidence = MEDIUM → calibration at week 10 |
| Race calendar | B/C-races exist | Half-marathon B-race → secondary race checkpoint |
| Phase transitions | Moving from base to build | Week 8 transition → benchmark checkpoint |
| Regular intervals | Every 3–4 weeks | Progress review checkpoints |

---

## Idempotency

- **Not idempotent.** Different hypotheses may produce different frameworks.
- Same hypotheses + same context → same framework (deterministic scoring)

---

## Failure Semantics

| Scenario | Behaviour |
|---|---|
| LLM failure | Return 503; retry once |
| Invalid output | Return error; retry with validation feedback |
| All hypotheses invalid | Return error; suggest simpler approach or template |
| Framework fails validation | Return errors for regeneration |

---

## Cross-References

- Hypothesis generation: `03-agents/hypothesis-agent.md`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- Plan generation pipeline: `02-computations/plan-generation.md`
- Validation logic: `02-computations/plan-generation.md` → validatePhaseArc
- Checkpoint types: `01-entities/checkpoint.md`
