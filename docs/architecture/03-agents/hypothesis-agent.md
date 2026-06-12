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
  trait_vector: MethodologyTraitVector   // coaching philosophy expression (0.0–1.0 per trait)
  phase_definitions: PhaseDefinition[]   // adaptation strategy — the core output
  checkpoints: {
    type: CheckpointType
    week: number
    metric: string
    session_type: string
  }[]
  rationale: string                      // why this approach suits this athlete
  risk_notes: string[]
}

// PhaseDefinition (from 00-foundations/terminology.md):
// {
//   phase: PhaseLabel
//   objective: ObjectiveCategory[]
//   weeks: number
//   distribution: {
//     low_aerobic: number
//     high_aerobic: number
//     threshold: number
//     vo2max: number
//     neuromuscular: number
//   }
//   specificity: number
//   approach: 'linear' | 'undulating' | 'block' | 'step'
//   recovery_cycle: 'frequent' | 'moderate' | 'infrequent'
// }
```

---

## Prompt Structure

### System Prompt
- **Three-layer model:** TraitVector (identity) → PhaseDefinition[] (adaptation strategy) → WeeklyDistribution[] (generated later by deterministic expansion)
- **TraitVector:** 10 fixed traits describing coaching philosophy expression. Each trait ranges from 0.0 to 1.0. Highest layer of the three-layer hierarchy: MethodologyTraitVector → PhysiologicalIntent → SessionType.
- **PhaseDefinition:** The core reasoning unit. Each phase has a label (methodology-specific), objectives (shared ObjectiveCategory enum), distribution (6 zones), specificity (independent attribute), approach (linear/undulating/block/step), and recovery_cycle (frequent/moderate/infrequent).
- **Hybrid methodology:** You are NOT limited to a single coaching methodology. You may draw from different methodologies for different phases based on the athlete's specific gaps and objectives. For example: Lydiard-style aerobic accumulation for base phases, Canova-specificity progression for race-specific phases, Norwegian threshold concentration for threshold development, Daniels-style multi-system balance for sharpening. The trait_vector represents the OVERALL coaching identity, not rigid adherence to one methodology.
- **Specificity is separate from distribution.** Specificity is a property of the stimulus, not a training zone. It overlaps with every load type (a marathon-pace threshold session has threshold distribution AND high specificity). Model it as a separate `specificity` number on each PhaseDefinition, not as part of the distribution.
- **Phase objectives share the athlete objectives enum.** Use the same ObjectiveCategory values (aerobic_base, threshold_quality, pacing_discipline, etc.) that the athlete's objectives use. This ensures the plan directly addresses athlete goals.
- **Hard invariants** (no back-to-back hard sessions, 48h recovery, etc.)
- **Distinctness rule:** Generate 3 hypotheses by varying methodology approach across phases. Each hypothesis should represent a genuinely different coaching strategy — not just different numbers, but different phase sequences, different methodology combinations, different specificity trajectories.

### Context
- Athlete twin state and context summary
- Athlete preferences (available days, long_workout_day)
- Athlete objectives (from objective management — same ObjectiveCategory enum used in phase objectives)
- Goal definition (event type, date, description)
- Race calendar (secondary events)
- Confidence gaps (which metrics need calibration)

### Instructions
1. Analyse athlete profile: strengths, weaknesses, constraints, race priorities
2. Review athlete objectives — these should directly inform phase objectives
3. For each hypothesis:
   a. Select a methodology approach (single tradition or hybrid)
   b. Design 4-5 phases using methodology-specific labels (e.g., 'aerobic_base', 'threshold_peak', 'specific_endurance')
   c. Assign objectives to each phase (from ObjectiveCategory enum, addressing athlete gaps)
   d. Define distribution, specificity, approach, and recovery_cycle per phase
   e. Ensure the overall trajectory makes physiological sense (base before specificity, etc.)
   f. Ensure hard constraints are respected
   g. Incorporate race calendar and secondary events
   h. Schedule checkpoints at optimal times
4. Return three hypotheses with rationale and risk notes

---

## Reasoning Dimensions

| Dimension | Type | Purpose |
|-----------|------|---------|
| trait_vector | MethodologyTraitVector | Coaching philosophy identity — 10 fixed traits (0.0–1.0) describing overall methodology emphasis. Static per hypothesis. |
| phase_definitions | PhaseDefinition[] | Adaptation strategy — 4-5 phases, each with distribution, specificity, approach, recovery_cycle, and objectives. The core output. |
| checkpoints | CheckpointDescriptor[] | Progress measurement points — scheduled based on confidence gaps, phase transitions, and race calendar |

**Note:** The former four dimensions (trait_vector, load_distribution, approach, recovery_cycle) are consolidated into two: trait_vector (identity) and phase_definitions (strategy). Approach and recovery_cycle are now per-phase attributes within PhaseDefinition, not independent hypothesis dimensions. Distribution is per-phase, not plan-wide.

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
