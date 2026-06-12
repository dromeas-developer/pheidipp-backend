# Plan Generation — Race Event Mode
*LLM-driven hypothesis generation with constraint-first validation for race/event goals.*

---

## Purpose

- Defines the full pipeline for race_event mode: training length gate → hypothesis generation → validation → synthesis → persistence
- The LLM generates three strategic hypotheses; Python validates and scores; the coach selects; persistence is atomic
- See `plan-generation.md` for shared types, inputs, and regeneration triggers

---

## Phase 0: Training Length Gate

Before any hypothesis generation, the system evaluates whether the goal timeline is appropriate.

```typescript
type ExperienceLevel = 'novice' | 'intermediate' | 'experienced'

type TrainingLengthGateInput = {
  weeks_until_goal: number
  fitness_level: number
  goal_event_type: GoalEventType
  experience_level: ExperienceLevel
}

type TrainingLengthGateResult = {
  action: 'proceed' | 'propose_intermediate' | 'propose_shorter_goal'
  message: string
  intermediate_objectives?: string[]
  gate_reason?: string              // e.g. "goal_too_far", "fitness_insufficient_for_distance"
}

// Configurable default threshold
const TRAINING_LENGTH_GATE_DEFAULT_WEEKS = 24

// Threshold adjustments by goal type and experience
const GATE_THRESHOLDS: Record<GoalEventType, Record<ExperienceLevel, number>> = {
  marathon:      { novice: 20, intermediate: 24, experienced: 30 },
  half_marathon: { novice: 16, intermediate: 20, experienced: 24 },
  '10k':         { novice: 12, intermediate: 16, experienced: 20 },
  '5k':          { novice: 8,  intermediate: 12, experienced: 16 },
  ultra:         { novice: 24, intermediate: 30, experienced: 36 },
  trail_race:    { novice: 20, intermediate: 24, experienced: 30 },
  custom:        { novice: 20, intermediate: 24, experienced: 30 },
}

function evaluateTrainingLength(input: TrainingLengthGateInput): TrainingLengthGateResult {
  const threshold = GATE_THRESHOLDS[input.goal_event_type]?.[input.experience_level] 
    ?? TRAINING_LENGTH_GATE_DEFAULT_WEEKS
  
  if (input.weeks_until_goal > threshold) {
    return {
      action: 'propose_intermediate',
      message: `Your ${input.goal_event_type} is ${input.weeks_until_goal} weeks away. That's too far ` +
               `to plan in detail — too much will change in your fitness and life. ` +
               `Let's focus on a 12-week block targeting the physiological foundations ` +
               `you'll need most: aerobic base, threshold development, and structural ` +
               `resilience. We'll reassess and plan the next phase after that.`,
      intermediate_objectives: [
        'aerobic_fitness',
        'threshold_power',
        'structural_resilience'
      ],
      gate_reason: 'goal_too_far'
    }
  }
  
  if (input.weeks_until_goal < 8 && input.fitness_level <= 2) {
    return {
      action: 'propose_shorter_goal',
      message: `With ${input.weeks_until_goal} weeks to your ${input.goal_event_type} and your current ` +
               `fitness level, a 10K or half-marathon would be a more realistic target. ` +
               `This builds race experience and confidence for the full distance later.`,
      gate_reason: 'fitness_insufficient_for_distance'
    }
  }
  
  return {
    action: 'proceed',
    message: ''
  }
}
```

**Behaviour:**
- `proceed`: Continue to Phase 1 (hypothesis generation) with full plan duration
- `propose_intermediate`: System proposes 8–12 week intermediate block; plan covers intermediate duration only
- `propose_shorter_goal`: System proposes alternative goal; athlete must accept or abandon

---

## Phase 1: Generate Strategic Hypotheses

The LLM generates three distinct hypotheses using the three-layer model: trait_vector (identity) + phase_definitions (adaptation strategy).

```typescript
type StrategicHypothesis = {
  name: string
  trait_vector: MethodologyTraitVector   // coaching philosophy identity
  phase_definitions: PhaseDefinition[]   // adaptation strategy — 4-5 phases
  checkpoints: CheckpointDescriptor[]
  rationale: string
  risk_notes: string[]
}

// PhaseDefinition (from 00-foundations/terminology.md):
// {
//   phase: PhaseLabel                    // methodology-specific label
//   objective: ObjectiveCategory[]       // shared with athlete objectives
//   weeks: number
//   distribution: { low_aerobic, high_aerobic, threshold, vo2max, neuromuscular }
//   specificity: number                  // independent attribute (0.0-1.0)
//   approach: 'linear' | 'undulating' | 'block' | 'step'
//   recovery_cycle: 'frequent' | 'moderate' | 'infrequent'
// }

type HypothesisGenerationInput = {
  twin_state: TwinState
  twin_context: TwinContextSummary
  athlete_preferences: AthletePreferences
  athlete_objectives: Objective[]       // from objective management — informs phase objectives
  goal: {
    description: string
    event_type: GoalEventType
    event_date: string
  }
  secondary_events: SecondaryEvent[]
  confidence_gaps: ConfidenceGap[]
}

type ConfidenceGap = {
  metric: string           // e.g. "LT2", "aerobic_fitness"
  confidence: 'low' | 'medium' | 'high'
  priority: 'high' | 'medium' | 'low'
}
```

**Distinctness Rule:**
Each hypothesis must differ in methodology approach and phase structure, not just numeric values. At minimum:
- Different phase labels (e.g., one uses 'threshold_build', another uses 'special_endurance')
- Different methodology combinations (e.g., one is pure Norwegian, another is Lydiard + Canova hybrid)
- Different specificity trajectories (e.g., one builds specificity gradually, another concentrates it in late phases)
- Different approach patterns within phases (e.g., one uses linear progression, another uses undulating)

**Generation Process:**
1. Analyse athlete profile: strengths, weaknesses, constraints, race priorities, confidence gaps
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
4. Validate logical coherence: trait_vector should reflect the overall emphasis across all phases

**Example Hypotheses for Marathon Athlete:**

*Athlete Context:* Weak aerobic base (aerobic_base: improve), moderate threshold (threshold_quality: maintain), good structural tolerance (structural_tolerance: maintain), goal: marathon in 16 weeks.

```typescript
// Hypothesis 1: "Norwegian Threshold"
{
  trait_vector: {
    threshold_density: 0.8,
    high_frequency: 0.9,
    high_aerobic_volume: 0.7,
    low_intensity_dominant: 0.6,
    high_intensity_sparse: 0.1,
    structural_durability: 0.5,
    race_specificity: 0.5,
    variety_emphasis: 0.3,
    neuromuscular_support: 0.2,
    conservative_progression: 0.7
  },
  phase_definitions: [
    { phase: 'aerobic_foundation', objective: ['aerobic_base'], weeks: 4,
      distribution: { low_aerobic: 0.70, high_aerobic: 0.15, threshold: 0.10, vo2max: 0.03, neuromuscular: 0.02 },
      specificity: 0.1, approach: 'linear', recovery_cycle: 'infrequent' },
    { phase: 'threshold_build', objective: ['threshold_quality', 'aerobic_base'], weeks: 6,
      distribution: { low_aerobic: 0.55, high_aerobic: 0.10, threshold: 0.25, vo2max: 0.05, neuromuscular: 0.05 },
      specificity: 0.3, approach: 'undulating', recovery_cycle: 'moderate' },
    { phase: 'threshold_peak', objective: ['threshold_quality', 'pacing_discipline'], weeks: 4,
      distribution: { low_aerobic: 0.50, high_aerobic: 0.10, threshold: 0.30, vo2max: 0.05, neuromuscular: 0.05 },
      specificity: 0.6, approach: 'block', recovery_cycle: 'frequent' },
    { phase: 'taper', objective: ['pacing_discipline'], weeks: 2,
      distribution: { low_aerobic: 0.65, high_aerobic: 0.10, threshold: 0.10, vo2max: 0.05, neuromuscular: 0.10 },
      specificity: 0.5, approach: 'linear', recovery_cycle: 'frequent' },
  ]
}

// Hypothesis 2: "Lydiard + Canova Hybrid"
{
  trait_vector: {
    high_aerobic_volume: 0.9,
    race_specificity: 0.8,
    structural_durability: 0.8,
    low_intensity_dominant: 0.7,
    threshold_density: 0.4,
    high_intensity_sparse: 0.2,
    high_frequency: 0.6,
    variety_emphasis: 0.5,
    neuromuscular_support: 0.4,
    conservative_progression: 0.6
  },
  phase_definitions: [
    { phase: 'aerobic_base', objective: ['aerobic_base', 'structural_tolerance'], weeks: 5,
      distribution: { low_aerobic: 0.80, high_aerobic: 0.10, threshold: 0.05, vo2max: 0.03, neuromuscular: 0.02 },
      specificity: 0.1, approach: 'linear', recovery_cycle: 'infrequent' },
    { phase: 'hill_phase', objective: ['structural_tolerance', 'aerobic_base'], weeks: 3,
      distribution: { low_aerobic: 0.65, high_aerobic: 0.15, threshold: 0.10, vo2max: 0.05, neuromuscular: 0.05 },
      specificity: 0.2, approach: 'block', recovery_cycle: 'moderate' },
    { phase: 'special_endurance', objective: ['threshold_quality', 'durability'], weeks: 4,
      distribution: { low_aerobic: 0.50, high_aerobic: 0.15, threshold: 0.20, vo2max: 0.05, neuromuscular: 0.10 },
      specificity: 0.6, approach: 'undulating', recovery_cycle: 'moderate' },
    { phase: 'specific_endurance', objective: ['pacing_discipline', 'durability'], weeks: 3,
      distribution: { low_aerobic: 0.40, high_aerobic: 0.15, threshold: 0.15, vo2max: 0.05, neuromuscular: 0.25 },
      specificity: 0.9, approach: 'block', recovery_cycle: 'frequent' },
    { phase: 'taper', objective: ['pacing_discipline'], weeks: 1,
      distribution: { low_aerobic: 0.60, high_aerobic: 0.10, threshold: 0.10, vo2max: 0.10, neuromuscular: 0.10 },
      specificity: 0.7, approach: 'linear', recovery_cycle: 'frequent' },
  ]
}

// Hypothesis 3: "Daniels Multi-System"
{
  trait_vector: {
    threshold_density: 0.6,
    high_aerobic_volume: 0.7,
    variety_emphasis: 0.7,
    low_intensity_dominant: 0.5,
    high_intensity_sparse: 0.4,
    high_frequency: 0.5,
    structural_durability: 0.5,
    race_specificity: 0.5,
    neuromuscular_support: 0.3,
    conservative_progression: 0.5
  },
  phase_definitions: [
    { phase: 'aerobic_base', objective: ['aerobic_base'], weeks: 4,
      distribution: { low_aerobic: 0.70, high_aerobic: 0.15, threshold: 0.10, vo2max: 0.03, neuromuscular: 0.02 },
      specificity: 0.1, approach: 'linear', recovery_cycle: 'moderate' },
    { phase: 'threshold_build', objective: ['threshold_quality', 'aerobic_base'], weeks: 4,
      distribution: { low_aerobic: 0.55, high_aerobic: 0.15, threshold: 0.20, vo2max: 0.05, neuromuscular: 0.05 },
      specificity: 0.3, approach: 'undulating', recovery_cycle: 'moderate' },
    { phase: 'vo2max_development', objective: ['threshold_quality', 'neuromuscular_sharpness'], weeks: 4,
      distribution: { low_aerobic: 0.50, high_aerobic: 0.10, threshold: 0.15, vo2max: 0.15, neuromuscular: 0.10 },
      specificity: 0.5, approach: 'undulating', recovery_cycle: 'moderate' },
    { phase: 'sharpening', objective: ['pacing_discipline', 'neuromuscular_sharpness'], weeks: 3,
      distribution: { low_aerobic: 0.45, high_aerobic: 0.10, threshold: 0.15, vo2max: 0.15, neuromuscular: 0.15 },
      specificity: 0.7, approach: 'block', recovery_cycle: 'frequent' },
    { phase: 'taper', objective: ['pacing_discipline'], weeks: 1,
      distribution: { low_aerobic: 0.60, high_aerobic: 0.10, threshold: 0.10, vo2max: 0.10, neuromuscular: 0.10 },
      specificity: 0.7, approach: 'linear', recovery_cycle: 'frequent' },
  ]
}
```

---

## Phase 2: Validate and Synthesize Strategic Framework

### Step 1: Constraint-First Validation

Hard invariants are checked first. Hypotheses violating any invariant are discarded immediately.

```typescript
type ValidationInvariant = {
  name: string
  check: (hypothesis: StrategicHypothesis, inputs: PlanGenerationInputs) => boolean
}

const HARD_INVARIANTS: ValidationInvariant[] = [
  {
    name: 'no_unsafe_load_spikes',
    check: (h, inputs) => /* acute load increase ≤ 10% week-over-week */
  },
  {
    name: 'no_incompatible_intensity_stacking',
    check: (h, inputs) => /* no back-to-back threshold/vo2max sessions */
  },
  {
    name: 'minimum_recovery_spacing',
    check: (h, inputs) => /* ≥ 48 hours between hard sessions */
  },
  {
    name: 'no_schedule_violating_constraints',
    check: (h, inputs) => /* workouts only on available days/times */
  },
  {
    name: 'running_only',
    check: (h, inputs) => /* no non-running activities in twin calibration */
  },
  {
    name: 'honesty_invariant',
    check: (h, inputs) => /* plans never pretend to know more than twin */
  },
  {
    name: 'no_overlapping_tapers',
    check: (h, inputs) => /* cannot taper for multiple races simultaneously */
  },
  {
    name: 'a_race_priority',
    check: (h, inputs) => /* A-race always takes precedence */
  },
  {
    name: 'secondary_events_outside_a_race_taper',
    check: (h, inputs) => /* B/C-races not in A-race taper or race week */
  }
]

function validateHypothesis(
  hypothesis: StrategicHypothesis,
  inputs: PlanGenerationInputs
): { valid: boolean; violated_invariants: string[] } {
  const violated = HARD_INVARIANTS
    .filter(inv => !inv.check(hypothesis, inputs))
    .map(inv => inv.name)
  
  return { valid: violated.length === 0, violated_invariants: violated }
}
```

**Result:** Invalid hypotheses are discarded. No scoring, no partial credit.

### Step 2: Score Valid Hypotheses

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Twin Alignment | 35% | Addresses strengths/weaknesses from twin analysis |
| Goal Fit | 25% | Aligns with goal type, distance, and race calendar |
| Objective Alignment | 25% | Addresses the athlete's active objectives (e.g., aerobic_base improve, threshold_quality maintain) |
| Injury Safety | 15% | Mitigates twin-identified structural and recovery risks |

```typescript
type HypothesisScore = {
  hypothesis_name: string
  twin_alignment: number      // 0–100
  goal_fit: number            // 0–100
  objective_alignment: number // 0–100
  injury_safety: number       // 0–100
  weighted_total: number      // computed
}

function scoreHypothesis(
  hypothesis: StrategicHypothesis,
  inputs: PlanGenerationInputs
): HypothesisScore {
  const twin_alignment = computeTwinAlignment(hypothesis, inputs.twin_context)
  const goal_fit = computeGoalFit(hypothesis, inputs.goal, inputs.secondary_events)
  const objective_alignment = computeObjectiveAlignment(hypothesis, inputs.active_objectives)
  const injury_safety = computeInjurySafety(hypothesis, inputs.twin_context)
  
  return {
    hypothesis_name: hypothesis.name,
    twin_alignment,
    goal_fit,
    objective_alignment,
    injury_safety,
    weighted_total: (twin_alignment * 0.35) + (goal_fit * 0.25) + (objective_alignment * 0.25) + (injury_safety * 0.15)
  }
}
```

### Step 3: Coach Selection

The coach (LLM) selects the best hypothesis based on scores and contextual judgement. The athlete does not choose.

### Step 4: Synthesize Strategic Framework

```typescript
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
  
  // Note: intensity_distribution removed — replaced by per-phase distributions on phase_definitions
  
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

type PhaseAdjustment = {
  phase: string
  adjustment: string
  detail: string
}
```

---

## Phase 3: Validate and Persist (Python)

Python validates the LLM's phase definitions against hard invariants. If valid, persists TrainingPlan and the first WeeklyPlan atomically. If invalid, returns errors for regeneration.

The LLM owns strategic decisions — methodology, phase emphasis, distribution. Python only enforces non-negotiable safety rules.

```typescript
type ValidationResult = {
  valid: boolean
  errors: ValidationError[]
}

type ValidationError = {
  rule: string           // e.g. "phase_definitions_gap"
  description: string    // human-readable explanation
}

function validatePhaseDefinitions(
  framework: StrategicFramework,
  inputs: PlanGenerationInputs
): ValidationResult {
  const errors: ValidationError[] = []
  
  // 1. Validate phase definitions cover full duration without gaps or excess
  const totalWeeks = weeksUntilGoal(inputs.training_goal.goal_event_date, inputs.today)
  const definitionWeeks = framework.phase_definitions.reduce((sum, p) => sum + p.weeks, 0)
  if (definitionWeeks < totalWeeks) {
    errors.push({
      rule: 'phase_definitions_incomplete',
      description: `Phase definitions cover ${definitionWeeks} weeks but plan needs ${totalWeeks}`
    })
  }
  if (definitionWeeks > totalWeeks) {
    errors.push({
      rule: 'phase_definitions_too_long',
      description: `Phase definitions cover ${definitionWeeks} weeks but plan needs ${totalWeeks}`
    })
  }
  
  // 2. Validate distribution sums ≤ 1.0 per phase
  for (const phase of framework.phase_definitions) {
    const distSum = Object.values(phase.distribution).reduce((a, b) => a + b, 0)
    if (distSum > 1.0) {
      errors.push({
        rule: 'distribution_sum_exceeded',
        description: `Phase '${phase.phase}' distribution sums to ${distSum.toFixed(2)} (max 1.0)`
      })
    }
  }
  
  // 3. Validate specificity range per phase
  for (const phase of framework.phase_definitions) {
    if (phase.specificity < 0.0 || phase.specificity > 1.0) {
      errors.push({
        rule: 'specificity_out_of_range',
        description: `Phase '${phase.phase}' specificity is ${phase.specificity} (must be 0.0-1.0)`
      })
    }
  }
  
  // 4. Validate phase ordering is physiologically coherent
  // Base phases should come before race-specific phases
  const phaseOrder = framework.phase_definitions.map(p => p.phase)
  const lastBasePhase = phaseOrder.findLastIndex(p => 
    p.includes('base') || p.includes('foundation') || p.includes('hill')
  )
  const firstSpecificPhase = phaseOrder.findIndex(p => 
    p.includes('specific') || p.includes('sharpening')
  )
  if (lastBasePhase > firstSpecificPhase && firstSpecificPhase !== -1) {
    errors.push({
      rule: 'phase_ordering_incoherent',
      description: 'Base/foundation phases appear after race-specific phases'
    })
  }
  
  // 5. Validate hard training constraints
  // (no back-to-back quality, 48h recovery — enforced at weekly synthesis level)
  
  // 6. Validate secondary events don't conflict with A-race taper
  // (handled by race schedule integration)
  
  return { valid: errors.length === 0, errors }
}
```

**Failure Handling:**

| Scenario | Behaviour |
|---|---|
| Validation fails | Return errors to LLM; LLM regenerates with error feedback |
| LLM produces invalid arc after retries | Fall back to simpler hypothesis or template |
| Persist fails after validation | Log error; retry; alert after 3 failures |

---

## Cross-References

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseDefinition, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_definitions, strategic_rationale, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **WeeklyPlan entity:** `01-entities/weekly-plan.md` — first WeeklyPlan created atomically with TrainingPlan
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
- **Vision hypothesis selection:** `docs/vision/product/hypothesis-selection.md` — why three hypotheses, four reasoning dimensions, scoring criteria
- **Vision checkpoints:** `docs/vision/product/training-plan-checkpoints.md` — checkpoint hierarchy and scheduling
