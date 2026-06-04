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

The LLM generates three distinct hypotheses using four primary dimensions.

```typescript
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

// trait_vector uses the 10 fixed traits from MethodologyTraitVector (00-foundations/terminology.md)
// Highest layer of the three-layer hierarchy: MethodologyTraitVector → PhysiologicalIntent → SessionType
// Phase-level evolution, not weekly

type StrategicHypothesis = {
  name: string
  dimensions: HypothesisDimensions
  phase_emphasis: PhaseDescriptor[]
  race_considerations: RaceConsiderations
  checkpoints: CheckpointDescriptor[]
  rationale: string
  risk_notes: string[]
}

type HypothesisGenerationInput = {
  twin_state: TwinState
  twin_context: TwinContextSummary
  athlete_preferences: AthletePreferences
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
Each hypothesis must differ in at least 2 of the 4 dimensions (trait_vector, load_distribution, approach, recovery_cycle).

```typescript
// How to measure difference in trait_vector:
function traitVectorDistance(a: MethodologyTraitVector, b: MethodologyTraitVector): number {
  const keys: (keyof MethodologyTraitVector)[] = [
    'high_aerobic_volume', 'low_intensity_dominant', 'threshold_density',
    'high_intensity_sparse', 'high_frequency', 'structural_durability',
    'race_specificity', 'variety_emphasis', 'neuromuscular_support',
    'conservative_progression'
  ]
  
  return Math.sqrt(
    keys.reduce((sum, key) => sum + Math.pow(a[key] - b[key], 2), 0)
  )
}

function areHypothesesDistinct(
  h1: HypothesisDimensions,
  h2: HypothesisDimensions,
  threshold: number = 0.5
): boolean {
  const trait_diff = traitVectorDistance(h1.trait_vector, h2.trait_vector)
  const load_diff = loadDistributionDistance(h1.load_distribution, h2.load_distribution)
  const approach_diff = h1.approach !== h2.approach ? 1 : 0
  const recovery_diff = h1.recovery_cycle !== h2.recovery_cycle ? 1 : 0
  
  // At least 2 dimensions must differ significantly
  const significant_diffs = [
    trait_diff > threshold,
    load_diff > threshold,
    approach_diff > 0,
    recovery_diff > 0
  ].filter(Boolean).length
  
  return significant_diffs >= 2
}
```

**Generation Process:**
1. Analyse athlete profile: strengths, weaknesses, constraints, race priorities, confidence gaps
2. Select three distinct combinations by varying at least 2 of the 4 dimensions. Each hypothesis should represent a genuinely different coaching approach for this athlete's specific objectives and race type.
3. For each hypothesis: justify trait_vector choices, address weaknesses, respect constraints, incorporate race calendar, schedule checkpoints
4. Validate logical coherence: trait_vector + approach + recovery_cycle must be compatible

**Example Hypotheses for Marathon Athlete:**

*Athlete Context:* Weak aerobic base (aerobic_base: improve), moderate threshold (threshold_quality: maintain), good structural tolerance (structural_tolerance: maintain), goal: marathon in 16 weeks.

```typescript
// Hypothesis 1: "Aerobic Emphasis"
{
  trait_vector: {
    high_aerobic_volume: 0.8,
    low_intensity_dominant: 0.7,
    threshold_density: 0.3,
    high_intensity_sparse: 0.1,
    high_frequency: 0.5,
    structural_durability: 0.4,
    race_specificity: 0.6,
    variety_emphasis: 0.2,
    neuromuscular_support: 0.1,
    conservative_progression: 0.6
  },
  load_distribution: {
    low_aerobic: 0.45,
    high_aerobic: 0.30,
    threshold: 0.15,
    vo2max: 0.05,
    neuromuscular: 0.05,
    recovery: 0.00
  },
  approach: 'linear',
  recovery_cycle: 'frequent'
}

// Hypothesis 2: "Balanced Development"
{
  trait_vector: {
    high_aerobic_volume: 0.6,
    low_intensity_dominant: 0.5,
    threshold_density: 0.5,
    high_intensity_sparse: 0.2,
    high_frequency: 0.6,
    structural_durability: 0.5,
    race_specificity: 0.5,
    variety_emphasis: 0.3,
    neuromuscular_support: 0.2,
    conservative_progression: 0.5
  },
  load_distribution: {
    low_aerobic: 0.40,
    high_aerobic: 0.25,
    threshold: 0.20,
    vo2max: 0.10,
    neuromuscular: 0.05,
    recovery: 0.00
  },
  approach: 'undulating',
  recovery_cycle: 'frequent'
}

// Hypothesis 3: "Threshold-Forward"
{
  trait_vector: {
    high_aerobic_volume: 0.5,
    low_intensity_dominant: 0.4,
    threshold_density: 0.7,
    high_intensity_sparse: 0.3,
    high_frequency: 0.5,
    structural_durability: 0.5,
    race_specificity: 0.7,
    variety_emphasis: 0.4,
    neuromuscular_support: 0.3,
    conservative_progression: 0.4
  },
  load_distribution: {
    low_aerobic: 0.35,
    high_aerobic: 0.20,
    threshold: 0.25,
    vo2max: 0.15,
    neuromuscular: 0.05,
    recovery: 0.00
  },
  approach: 'block',
  recovery_cycle: 'micro_cycles'
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
  
  macrocycle_structure: string    // plain English description
  
  // Phase arc from LLM — strategic intent per week, no session-level detail
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
    volume: string    // plain English progression rules
    intensity: string
  }
  
  recovery_model: {
    type: string      // recovery cycle type
    structure: string // standard structure
    race_recovery: Record<string, string>  // per-race-type recovery
  }
  
  risk_mitigations: string[]
}

type RaceScheduleEntry = {
  race: string                    // "A-race", "B-race", "C-race"
  type: GoalEventType
  week: number
  role: 'peak' | 'tune_up' | 'training'
  taper: string                   // "2 weeks", "3 days", "none"
  recovery: string                // "2 weeks", "5 days", "3 days"
}

type PhaseAdjustment = {
  phase: string
  adjustment: string
  detail: string
}
```

---

## Phase 3: Validate and Persist (Python)

Python validates the LLM's phase arc against hard invariants. If valid, persists TrainingPlan and the first WeeklyPlan atomically. If invalid, returns errors for regeneration.

The LLM owns strategic decisions — methodology, phase emphasis, intensity bias. Python only enforces non-negotiable safety rules.

```typescript
type ValidationResult = {
  valid: boolean
  errors: ValidationError[]
}

type ValidationError = {
  rule: string           // e.g. "phase_arc_gap"
  description: string    // human-readable explanation
}

function validatePhaseArc(
  framework: StrategicFramework,
  inputs: PlanGenerationInputs
): ValidationResult {
  const errors: ValidationError[] = []
  
  // 1. Validate phase arc covers full duration without gaps or excess
  const totalWeeks = weeksUntilGoal(inputs.training_block.goal_event_date, inputs.today)
  const arcWeeks = framework.phase_arc.length
  if (arcWeeks < totalWeeks) {
    errors.push({
      rule: 'phase_arc_incomplete',
      description: `Phase arc covers ${arcWeeks} weeks but plan needs ${totalWeeks}`
    })
  }
  if (arcWeeks > totalWeeks) {
    errors.push({
      rule: 'phase_arc_too_long',
      description: `Phase arc covers ${arcWeeks} weeks but plan only needs ${totalWeeks}`
    })
  }
  
  // 2. Validate phase labels are non-overlapping and ordered
  for (let i = 1; i < framework.phase_arc.length; i++) {
    if (framework.phase_arc[i].week_number <= framework.phase_arc[i-1].week_number) {
      errors.push({
        rule: 'phase_arc_ordering',
        description: `Week ${framework.phase_arc[i].week_number} follows week ${framework.phase_arc[i-1].week_number}`
      })
    }
  }
  
  // 3. Validate race schedule fits within phase arc
  for (const race of framework.race_schedule) {
    if (race.week > arcWeeks) {
      errors.push({
        rule: 'race_outside_arc',
        description: `${race.race} scheduled week ${race.week} but arc only covers ${arcWeeks} weeks`
      })
    }
  }
  
  // 4. Validate checkpoint schedule fits within phase arc
  for (const cp of framework.checkpoint_schedule) {
    if (cp.week_number > arcWeeks) {
      errors.push({
        rule: 'checkpoint_outside_arc',
        description: `Checkpoint at week ${cp.week_number} but arc only covers ${arcWeeks} weeks`
      })
    }
  }
  
  // 5. Validate intensity bias is consistent with phase label
  for (const entry of framework.phase_arc) {
    if (entry.phase_label === 'taper' && entry.intensity_bias === 'quality') {
      errors.push({
        rule: 'taper_intensity_conflict',
        description: `Taper week ${entry.week_number} cannot have quality intensity bias`
      })
    }
  }
  
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

- **Shared types and inputs:** `plan-generation.md` — PlanGenerationInputs, PhaseArcEntry, CheckpointDescriptor, persistPlan(), createFirstWeeklyPlan()
- **TrainingPlan entity:** `01-entities/training-plan.md` — produces TrainingPlan with phase_arc, strategic_rationale, checkpoint_schedule
- **Checkpoint entity:** `01-entities/checkpoint.md` — produces Checkpoint records from checkpoint_schedule
- **WeeklyPlan entity:** `01-entities/weekly-plan.md` — first WeeklyPlan created atomically with TrainingPlan
- **Vision plan generation:** `docs/vision/product/plan-generation.md` — strategic roadmap concept
- **Vision hypothesis selection:** `docs/vision/product/hypothesis-selection.md` — why three hypotheses, four reasoning dimensions, scoring criteria
- **Vision checkpoints:** `docs/vision/product/training-plan-checkpoints.md` — checkpoint hierarchy and scheduling
