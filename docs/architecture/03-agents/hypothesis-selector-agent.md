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
  
  // Phase definitions — the adaptation strategy (from selected hypothesis)
  phase_definitions: PhaseDefinition[]
  
  // Derived: per-week distributions (computed by deterministic expansion)
  weekly_distributions: WeeklyDistribution[]
  
  race_schedule: RaceScheduleEntry[]
  checkpoint_schedule: CheckpointDescriptor[]
  phase_adjustments: PhaseAdjustment[]
  
  // Note: intensity_distribution removed — replaced by per-phase distributions
  
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

// PhaseDefinition: see 00-foundations/terminology.md
// WeeklyDistribution: see 00-foundations/terminology.md

type RaceScheduleEntry = {
  race: string                       // "A-race", "B-event", "C-event"
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
- Scoring criteria: twin alignment (35%), goal fit (25%), objective alignment (25%), injury safety (15%)
- Constraint-first validation rules (phase ordering, distribution sums, hard invariants)
- Strategic framework structure (phase_definitions, weekly_distributions, race_schedule, checkpoints)
- PhaseDefinition validation: distribution sums ≤ 1.0, specificity 0.0-1.0, valid PhaseLabel values
- Race schedule formatting
- Checkpoint scheduling logic
- Deterministic expansion: phase_definitions → weekly_distributions (pure function, applied after selection)

### Context
- Three hypotheses with trait_vector, phase_definitions, rationale and risk notes
- Athlete twin context summary
- Athlete preferences
- Athlete objectives (shared ObjectiveCategory enum with phase objectives)
- Goal definition
- Race calendar

### Instructions
1. **Validate each hypothesis** against hard invariants:
   - Phase ordering is physiologically coherent (base before specificity, etc.)
   - Distribution values sum to ≤ 1.0 per phase
   - Specificity values are 0.0-1.0
   - Phase objectives use valid ObjectiveCategory values
   - Hard training constraints respected (no back-to-back quality, 48h recovery)
   - Discard invalid hypotheses immediately — no scoring, no partial credit

2. **Score valid hypotheses** on four criteria:
   - Twin Alignment (35%): addresses strengths/weaknesses identified in twin analysis
   - Goal Fit (25%): aligns with goal type, distance, and race calendar
   - Objective Alignment (25%): phase objectives address the athlete's active objectives
   - Injury Safety (15%): mitigates twin-identified structural and recovery risks

3. **Select the best hypothesis** based on scores

4. **Synthesise strategic framework** from selected hypothesis:
   - Copy phase_definitions from selected hypothesis
   - Apply deterministic expansion: phase_definitions → weekly_distributions
   - Derive macrocycle structure (plain English description)
   - Integrate race schedule with taper/recovery windows
   - Schedule checkpoints based on confidence gaps and phase transitions
   - Specify progression model (volume and intensity trajectory)
   - Define recovery model
   - Identify risk mitigations

5. **Return** selected hypothesis name and strategic framework

---

## Scoring Criteria

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Twin Alignment | 35% | Addresses strengths and weaknesses identified in twin analysis |
| Goal Fit | 25% | Aligns with goal type, distance, and race calendar |
| Objective Alignment | 25% | Phase objectives address the athlete's active objectives (from athlete_objectives input) |
| Injury Safety | 15% | Mitigates twin-identified structural and recovery risks |

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

## Decision Authority

Implements two authority boundaries from `docs/vision/coach/decision-authority.md`:

**Hypothesis Selection.** The coach selects the best hypothesis. The athlete does not choose between plans. The agent scores hypotheses against twin alignment, goal fit, and injury safety, then selects the highest-scoring valid candidate and synthesises a strategic framework. The athlete receives one plan with a clear rationale. There is no multiple-choice screen, no A/B testing, no negotiation over which hypothesis to use. The athlete's agency is limited to accepting or abandoning the resulting plan.

**Checkpoint Recommendation.** Checkpoints are strongly recommended, not mandatory. The agent schedules checkpoints based on confidence gaps, phase transitions, and race calendar. The athlete can decline a checkpoint. If declined, the plan continues with conservative assumptions and the cost of declining (wider zones, less precision) is communicated transparently. The agent does not enforce checkpoint completion — it surfaces the recommendation and the consequence of declining.

---

## Cross-References

- Decision authority: `docs/vision/coach/decision-authority.md` → "Hypothesis Selection" and "Checkpoint Recommendation"
- Selection criteria philosophy: `docs/vision/product/hypothesis-selection.md`
- Hypothesis generation: `03-agents/hypothesis-agent.md`
- Weekly synthesis: `03-agents/weekly-synthesis-agent.md`
- Plan generation pipeline: `02-computations/plan-generation-race.md` (race mode hypothesis validation and synthesis, includes target_performance preprocessing)
- Shared types and persistence: `02-computations/plan-generation.md`
- Deterministic expansion: `00-foundations/terminology.md` → PhaseDefinition → WeeklyDistribution
- Validation logic: `02-computations/plan-generation-race.md` → validatePhaseArc
- Checkpoint types: `01-entities/checkpoint.md`
