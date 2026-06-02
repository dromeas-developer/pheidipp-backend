# Plan Generation — Computation
*Converts TrainingBlock + TwinState into TrainingPlan + PlannedSessions via training length gate, hypothesis generation, validation, synthesis, and instantiation.*

---

## Purpose

- Defines the multi-phase algorithm that produces a training plan from athlete context
- For `race_event` mode: LLM-driven hypothesis generation with constraint-first validation
- For `fitness_improvement`, `maintenance`, `recovery` modes: deterministic phase arc formulas
- Plan generation produces a **phase arc** (strategic intent per week) and the **first WeeklyPlan** atomically. Session-level detail for subsequent weeks is deferred to weekly synthesis.

---

## Inputs

```typescript
type PlanGenerationInputs = {
  training_block: TrainingBlock
  athlete_preferences: AthletePreferences
  twin_state: TwinState
  cycle_phase_log: CyclePhaseLog | null  // used to avoid key sessions in late luteal
  today: string  // YYYY-MM-DD
  secondary_events: SecondaryEvent[]     // B-races and C-races for disruption window calculation
}

// GoalType determines plan generation approach:
// - race_event: agent-driven hypothesis generation → validation → synthesis (Phase 1-2);
//              then validation and persistence (Phase 3)
// - fitness_improvement: deterministic progressive development arc
// - maintenance: deterministic consistency-focused rolling blocks
// - recovery: deterministic conservative progression

// Secondary events create disruption windows within the phase arc:
// - B-races: 4 days pre-race, 3 days post-race (reduced load/recovery focus)
// - C-races: 2 days pre-race, 1 day post-race (minimal adjustment)
```

---

## Race Event Mode: Full Pipeline

### Phase 0: Training Length Gate

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

### Phase 1: Generate Strategic Hypotheses

The LLM generates three distinct hypotheses using four primary dimensions.

```typescript
type HypothesisDimensions = {
  methodology: 'polarized' | 'pyramid' | 'threshold_focused' | 'block_periodization' | 'reverse_periodization' | 'hilf' | 'lihf'
  approach: 'linear' | 'non_linear' | 'block' | 'undulating' | 'step' | 'exponential'
  recovery_cycle: 'frequent' | 'infrequent' | 'micro_cycles' | 'macro_cycles'
  load_distribution: {
    low_aerobic: number            // percentage of session time (0-1)
    high_aerobic: number
    threshold: number
    vo2max: number
    neuromuscular: number
    recovery: number
  }
}

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

**Core Rule for Distinctness:**
Each hypothesis must differ in at least two of the four primary dimensions, while respecting all twin constraints and the race calendar.

**Generation Process:**
1. Analyse athlete profile: strengths, weaknesses, constraints, race priorities, confidence gaps
2. Select three orthogonal combinations of the four dimensions
3. For each hypothesis: justify methodology, address weaknesses, respect constraints, incorporate race calendar, schedule checkpoints
4. Validate logical coherence: methodology + approach + recovery cycle must be compatible

---

### Phase 2: Validate and Synthesize Strategic Framework

#### Step 1: Constraint-First Validation

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

#### Step 2: Score Valid Hypotheses

| Criterion | Weight | Description |
|-----------|--------|-------------|
| Twin Alignment | 50% | Addresses strengths/weaknesses from twin analysis |
| Goal Fit | 30% | Aligns with goal type, distance, and race calendar |
| Injury Safety | 10% | Mitigates twin-identified structural and recovery risks |

```typescript
type HypothesisScore = {
  hypothesis_name: string
  twin_alignment: number      // 0–100
  goal_fit: number            // 0–100
  injury_safety: number       // 0–100
  weighted_total: number      // computed
}

function scoreHypothesis(
  hypothesis: StrategicHypothesis,
  inputs: PlanGenerationInputs
): HypothesisScore {
  const twin_alignment = computeTwinAlignment(hypothesis, inputs.twin_context)
  const goal_fit = computeGoalFit(hypothesis, inputs.goal, inputs.secondary_events)
  const injury_safety = computeInjurySafety(hypothesis, inputs.twin_context)
  
  return {
    hypothesis_name: hypothesis.name,
    twin_alignment,
    goal_fit,
    injury_safety,
    weighted_total: (twin_alignment * 0.5) + (goal_fit * 0.3) + (injury_safety * 0.1)
  }
}
```

#### Step 3: Coach Selection

The coach (LLM) selects the best hypothesis based on scores and contextual judgement. The athlete does not choose.

#### Step 4: Synthesize Strategic Framework

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

type PhaseArcEntry = {
  week_number: number
  phase_label: PhaseLabel
  methodology: MethodologyTraitVector
  physiological_emphasis: string      // plain English; what this week is about
  intensity_bias: 'easy' | 'balanced' | 'moderate' | 'quality'
  race_considerations?: string        // "B-race this week, reduce pre-race"
  checkpoint_intent?: string          // "benchmark aerobic fitness"
  target_session_count: number        // hint, not constraint — weekly planner decides
}

type RaceScheduleEntry = {
  race: string                    // "A-race", "B-race", "C-race"
  type: GoalEventType
  week: number
  role: 'peak' | 'tune_up' | 'training'
  taper: string                   // "2 weeks", "3 days", "none"
  recovery: string                // "2 weeks", "5 days", "3 days"
}

type CheckpointDescriptor = {
  type: CheckpointType
  week_number: number
  target_date: string
  target_metric: string
  session_type: SessionType
  planner_message: string
}

type PhaseAdjustment = {
  phase: string
  adjustment: string
  detail: string
}
```

---

### Phase 3: Validate and Persist (Python)

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

**Persist Function:**

```typescript
function persistPlan(
  framework: StrategicFramework,
  validation: ValidationResult,
  inputs: PlanGenerationInputs
): { plan: TrainingPlan; first_weekly_plan: WeeklyPlan; checkpoints: Checkpoint[] } {
  // Creates atomically:
  // 1. TrainingPlan (with phase_arc, strategic_rationale, checkpoint_schedule)
  // 2. First WeeklyPlan (synthesised from phase_arc[0] + current twin state)
  // 3. Checkpoint records (from checkpoint_schedule)
  // 4. Fires training_plan_generated event
  
  // The first WeeklyPlan is created by the weekly-synthesis-agent
  // reading phase_arc[0] as the adjusted intent (no pre-week review needed for week 1)
}
```

**First Weekly Plan Creation:**

The first weekly plan is always created atomically with the training plan by PlanGenerationService — not by WeeklySynthesisAgent. This ensures the first message can reference specific sessions.

**Why atomic creation for week 1:** Week 1 has no prior execution data, so the pre-week review would be a no-op pass-through. Creating the first WeeklyPlan atomically avoids an unnecessary async hop through PreWeekReviewService and ensures the plan is immediately actionable.

**Producer distinction:** PlanGenerationService creates week 1. PreWeekReviewService + WeeklySynthesisAgent handle week 2 onward. WeeklySynthesisAgent's contract starts from week 2 — it never receives week 1 as input.

```typescript
async function createFirstWeeklyPlan(
  plan: TrainingPlan,
  inputs: PlanGenerationInputs
): Promise<WeeklyPlan> {
  // Week 1 uses the phase arc entry directly as the adjusted intent
  // (no pre-week review — this is the initial synthesis)
  const week1_intent: AdjustedWeeklyIntent = {
    ...plan.phase_arc[0],
    adjustment_made: false,
    adjustment_reason: null,
    adjustment_source: 'plan_unchanged'
  }
  
  // Weekly synthesis agent produces sessions for week 1
  const weekly_output = await weeklySynthesisAgent.generate({
    adjusted_intent: week1_intent,
    twin_state: inputs.twin_state,
    athlete_preferences: inputs.athlete_preferences,
    prior_weeks_summary: [],  // no prior weeks
    training_plan: plan,
    secondary_events: inputs.secondary_events,
    checkpoint_schedule: plan.checkpoint_schedule.filter(cp => cp.week_number === 1)
  })
  
  // Persist WeeklyPlan with sessions
  return persistWeeklyPlan(plan.id, 1, week1_intent, weekly_output.sessions)
}
```

---

### Phase 4: Adaptive Evolution

#### Regeneration Triggers

Full plan regeneration (replacing the phase arc) is reserved for major structural changes. Most disruptions are absorbed by weekly synthesis.

```typescript
type RegenerationTrigger =
  | 'new_block'
  | 'goal_date_change'        // goal_event_date moved by > 7 days
  | 'confidence_upgrade'      // twin moved from low→medium or medium→high (only if plan was at low)
  | 'secondary_event_added'   // B-race or C-race that conflicts with phase structure
  | 'secondary_event_removed' // Secondary event removed, phase arc needs restructuring
  | 'checkpoint_completed'    // Checkpoint resulted in confidence change AND replan_triggered = true

function shouldRegenerate(trigger: RegenerationTrigger, old_plan: TrainingPlan, new_twin: TwinState): boolean {
  // goal_date_change: only if abs(new_date - old_date) > 7 days
  // confidence_upgrade: only if old plan was generated at 'low' confidence
  // secondary_event changes: only if disruption cannot be accommodated within existing phase arc
  // checkpoint_completed: only if confidence_changed = true AND replan_triggered = true
}
```

#### What Does NOT Trigger Regeneration

The following disruptions are absorbed by weekly synthesis, not plan regeneration:

| Disruption | How It's Absorbed |
|---|---|
| Missed sessions (schedule changes, motivation) | Next pre-week review adjusts intent |
| Faster/slower than expected recovery | Weekly synthesis adjusts session count/intensity |
| Minor schedule disruptions (travel, work) | Weekly synthesis works with new availability |
| Adaptation yield better/worse than expected | Pre-week review adjusts intensity bias |
| Session dropout >20% | Next pre-week review reduces load; NOT full regeneration |

#### Checkpoint Completion Flow

When a checkpoint completes, the system processes the result:

```typescript
type CheckpointCompletionResult = {
  metric_updated: boolean
  confidence_changed: boolean
  new_confidence_level?: 'low' | 'medium' | 'high'
  replan_triggered: boolean
}

function processCheckpointCompletion(
  checkpoint: Checkpoint,
  session: PlannedSession,
  activity: Activity
): CheckpointCompletionResult {
  // 1. Analyse activity data against checkpoint.target_metric
  // 2. Update twin state if metric changed materially
  // 3. Check if confidence level changed
  // 4. If confidence changed significantly, trigger replanning
  // 5. Return result for event payload
}
```

#### Checkpoint Completion Flow

When a checkpoint completes, the system processes the result:

```typescript
type CheckpointCompletionResult = {
  metric_updated: boolean
  confidence_changed: boolean
  new_confidence_level?: 'low' | 'medium' | 'high'
  replan_triggered: boolean
}

function processCheckpointCompletion(
  checkpoint: Checkpoint,
  session: PlannedSession,
  activity: Activity
): CheckpointCompletionResult {
  // 1. Analyse activity data against checkpoint.target_metric
  // 2. Update twin state if metric changed materially
  // 3. Check if confidence level changed
  // 4. If confidence changed significantly, trigger replanning
  // 5. Return result for event payload
}
```

---

## Non-Race Modes: Deterministic Arcs

### Fitness Improvement Mode

```typescript
function computeFitnessImprovementArc(
  total_weeks: number,
  athlete_preferences: AthletePreferences
): PhaseDescriptor[] {
  // 8-week rolling progression with threshold emphasis
  const base_weeks = Math.min(total_weeks, 8)

  if (total_weeks >= 8) {
    return [
      { label: 'base_building', weeks: 4, ... }
    , { label: 'threshold_development', weeks: 3, ... }
    , { label: 'race_specific', weeks: 1, ... }  // repurposed: capacity building
    ]
  } else {
    return [{ label: 'rolling_block', weeks: total_weeks, primary_focus: 'Progressive development' }]
  }
}
```

### Maintenance Mode

```typescript
function computeMaintenanceArc(
  total_weeks: number,
  athlete_preferences: AthletePreferences
): PhaseDescriptor[] {
  // 4-week rolling block emphasizing consistency and form preservation
  return [{
    label: 'rolling_block',
    weeks: Math.min(total_weeks, 4),
    primary_focus: 'Consistent aerobic development with form preservation'
  }]
}
```

### Recovery Mode

```typescript
function computeRecoveryArc(
  injury_severity: InjurySeverity,
  athlete_preferences: AthletePreferences
): PhaseDescriptor[] {
  // Conservative load progression based on injury severity
  const phase_weeks = injury_severity === 'minor' ? 2 : injury_severity === 'major' ? 4 : 3

  return [{
    label: 'recovery',
    weeks: phase_weeks,
    primary_focus: 'Healing and gradual return to training'
  }]
}
```

---

## Crossover Athlete Structural Ramp

When `AthletePreferences.sport_background !== 'running_primary'`:

```typescript
// First training goal: structural load is capped regardless of stated weekly_volume_hours
// The cardiovascular system tolerates volume the tendons cannot yet handle
const MAX_STRUCTURAL_LOAD_PER_WEEK_CROSSOVER = 0.7 * POPULATION_MAX_WEEK_1

// Applied as a constraint on session count and long_run duration in weeks 1-4
// Relaxed by week 5 if no injury flags in quality_flags or skip_reason
```

---

## Intensity Allocation from Adaptation Yield

When the adaptation signature has sufficient data, the session planner adjusts hard training volume based on this athlete's demonstrated intensity yield.

### Eligibility Gate

```typescript
// Adjustment only fires when:
// 1. TwinState.confidence_level = 'high'
// 2. AdaptationSignature has ≥ 3 complete block observations
// 3. Threshold yield is below the defined threshold relative to aerobic yield
function isIntensityAdjustmentEligible(
  twin_confidence: TwinConfidenceLevel,
  adaptation_observations: AdaptationObservation[]
): boolean {
  if (twin_confidence !== 'high') return false
  if (adaptation_observations.length < 3) return false
  return true
}
```

### Adjustment Function

```typescript
type YieldByIntentState = Record<PhysiologicalIntent, number>

function computeIntensityAllocation(
  yield_by_intent: YieldByIntentState,
  default_hard_percentage: number  // from strategic framework (e.g. 0.15)
): number {
  const threshold_yield = yield_by_intent['threshold'] ?? 0
  const vo2_yield = yield_by_intent['vo2max'] ?? 0
  const aerobic_yield = yield_by_intent['low_aerobic'] ?? 1  // avoid division by zero

  // Composite intensity yield: weighted average of threshold and VO2 response
  const intensity_yield = (threshold_yield * 0.6) + (vo2_yield * 0.4)

  // Relative yield: how does this athlete's intensity response compare to their aerobic response
  const relative_yield = intensity_yield / aerobic_yield

  // Population median relative yield is approximately 0.8
  // Below 0.6: significant slow adapter → reduce hard volume substantially
  // 0.6–0.8: moderate slow adapter → reduce proportionally
  // Above 0.8: normal or fast adapter → no reduction
  const POPULATION_MEDIAN_RELATIVE_YIELD = 0.8
  const SLOW_ADAPTER_THRESHOLD = 0.6

  if (relative_yield >= POPULATION_MEDIAN_RELATIVE_YIELD) {
    return default_hard_percentage  // no adjustment
  }

  if (relative_yield <= SLOW_ADAPTER_THRESHOLD) {
    // Significant reduction: hard volume drops proportionally
    // At 0.6 relative yield → ~30% reduction (matches historical default)
    // Below 0.6 → up to 50% reduction
    const reduction_factor = 1 - ((POPULATION_MEDIAN_RELATIVE_YIELD - relative_yield) / POPULATION_MEDIAN_RELATIVE_YIELD)
    return default_hard_percentage * Math.max(0.5, reduction_factor)
  }

  // Linear interpolation between 0.6 and 0.8
  const reduction_factor = (relative_yield - SLOW_ADAPTER_THRESHOLD) / (POPULATION_MEDIAN_RELATIVE_YIELD - SLOW_ADAPTER_THRESHOLD)
  return default_hard_percentage * (0.7 + (0.3 * reduction_factor))  // range: 0.7x to 1.0x
}
```

### How It Feeds Session Planning

The computed intensity allocation replaces the `hard_percentage` in the strategic framework's intensity distribution. The session planner agent receives this adjusted allocation and distributes sessions accordingly:

```typescript
// Example:
// Default: 15% hard (threshold + VO2), 85% easy
// Slow adapter at 0.6 relative yield: ~10.5% hard, 89.5% easy
// The session planner replaces 1-2 threshold sessions with easy aerobic
```

### Invariants

- No adjustment without data: LOW or MEDIUM confidence → standard intensity allocation
- Adjustment is recalculated when adaptation signature updates (new block completed)
- Floor: hard training never drops below 5% of weekly volume — some intensity is always prescribed
- Ceiling: hard training never exceeds the strategic framework's original allocation
- The adjustment affects session count and type, not individual session intensity (targets remain threshold-based for sessions that are prescribed)

---

## Agent Invocation Flow

For `race_event` mode, the generation pipeline invokes three agents in sequence:

```
┌─────────────────────────────────────────────────────────────────┐
│  Phase 0: Training Length Gate (Python)                        │
│  Input: TrainingGoal, fitness_level, experience_level          │
│  Output: proceed / propose_intermediate / propose_shorter      │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 1: Hypothesis Agent                                     │
│  Input: TwinState, preferences, goal, race calendar            │
│  Output: 3 StrategicHypothesis objects                         │
│  Context: ~3k-5k tokens                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2: Hypothesis Selector Agent                            │
│  Input: 3 hypotheses, athlete context                          │
│  Output: StrategicFramework (with race schedule, checkpoints)   │
│  Context: ~4k-6k tokens                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 2b: Session Planner Agent                               │
│  Input: StrategicFramework, athlete preferences                │
│  Output: SessionWeek[] (full session schedule)                 │
│  Context: ~5k-7k tokens                                        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Phase 3: Validate and Persist (Python)                        │
│  Input: StrategicFramework with session_schedule               │
│  Output: TrainingPlan + PlannedSessions + Checkpoints          │
│  Validation: 7 rules (available_days, no_back_to_back, etc.)   │
└─────────────────────────────────────────────────────────────────┘
```

**Pipeline Summary:**

| Phase | Owner | Input | Output | Tokens |
|-------|-------|-------|--------|--------|
| 0 | Python | TrainingGoal | Gate result | — |
| 1 | Agent | Athlete context | 3 hypotheses | ~3k-5k |
| 2 | Agent | 3 hypotheses | StrategicFramework | ~4k-6k |
| 2b | Agent | Framework + preferences | SessionWeek[] | ~5k-7k |
| 3 | Python | Framework | Plan + Sessions + Checkpoints | — |

**For `fitness_improvement`, `maintenance`, `recovery` modes:** Skip Phases 1-2b. Phase 3 uses deterministic templates instead of agent-generated schedules.

---

```typescript
async function generateRaceEventPlan(
  inputs: PlanGenerationInputs
): Promise<{ plan: TrainingPlan; sessions: PlannedSession[]; checkpoints: Checkpoint[] }> {
  
  // Phase 0: Training Length Gate (Python)
  const gateResult = evaluateTrainingLength({
    weeks_until_goal: weeksUntilGoal(inputs.training_goal.goal_event_date, inputs.today),
    fitness_level: inputs.training_goal.fitness_level,
    goal_event_type: inputs.training_goal.goal_event_type,
    experience_level: inputs.athlete_preferences.experience_level
  })
  
  if (gateResult.action !== 'proceed') {
    return handleGateResult(gateResult, inputs)
  }
  
  // Phase 1: Generate Hypotheses (Agent)
  const hypotheses = await hypothesisAgent.generate({
    twin_state: inputs.twin_state,
    twin_context: await assembleTwinContext(inputs.twin_state),
    athlete_preferences: inputs.athlete_preferences,
    goal: {
      description: inputs.training_goal.goal_description,
      event_type: inputs.training_goal.goal_event_type,
      event_date: inputs.training_goal.goal_event_date
    },
    secondary_events: inputs.secondary_events,
    confidence_gaps: identifyConfidenceGaps(inputs.twin_state)
  })
  
  // Phase 2: Select Hypothesis and Synthesize Framework (Agent)
  const { strategic_framework } = await hypothesisSelectorAgent.select({
    hypotheses: hypotheses.hypotheses,
    twin_context: await assembleTwinContext(inputs.twin_state),
    athlete_preferences: inputs.athlete_preferences,
    goal: {
      event_type: inputs.training_goal.goal_event_type,
      event_date: inputs.training_goal.goal_event_date
    },
    secondary_events: inputs.secondary_events
  })
  
  // Phase 2b: Generate Session Schedule (Agent)
  const { session_schedule } = await sessionPlannerAgent.generate({
    strategic_framework,
    athlete_preferences: {
      available_days: inputs.athlete_preferences.available_days,
      long_workout_day: inputs.athlete_preferences.long_workout_day,
      weekly_session_count: inputs.athlete_preferences.weekly_session_count
    },
    secondary_events: inputs.secondary_events,
    twin_context: await assembleTwinContext(inputs.twin_state)
  })
  
  strategic_framework.session_schedule = session_schedule
  
  // Phase 3: Validate (Python)
  const validation = validateSchedule(strategic_framework, inputs.athlete_preferences)
  
  if (!validation.valid) {
    return handleValidationFailure(validation, inputs)
  }
  
  // Phase 3b: Persist (Python)
  return persistPlan(strategic_framework, inputs)
}
```

---

## Outputs

After validation passes, creates atomically:
- One `TrainingPlan` (status=active; old plan superseded) with `phase_arc`, `strategic_rationale`, and `checkpoint_schedule`
- First `WeeklyPlan` (synthesised from `phase_arc[0]` + current twin state) — created by PlanGenerationService, not WeeklySynthesisAgent
- `Checkpoint` records (from `checkpoint_schedule`)
- Fires `training_plan_generated` event

**Note:** The first WeeklyPlan producer is PlanGenerationService. PreWeekReviewService and WeeklySynthesisAgent handle week 2 onward.

---

## Failure Handling

```typescript
type PlanGenerationFailure = {
  phase: 'gate' | 'hypothesis' | 'selection' | 'session_planning' | 'validation' | 'persistence'
  error: string
  retry_count: number
  fallback_available: boolean
}

function handleGateResult(
  result: TrainingLengthGateResult,
  inputs: PlanGenerationInputs
): { proposal: IntermediateGoalProposal | ShorterGoalProposal } {
  // Return proposal to athlete; no plan generated yet
}

function handleValidationFailure(
  validation: ValidationResult,
  inputs: PlanGenerationInputs
): { plan: TrainingPlan; sessions: PlannedSession[]; checkpoints: Checkpoint[] } | PlanGenerationFailure {
  // Retry session planner with error feedback
  // If retry fails, fall back to simpler hypothesis or template
}

// Failure matrix:
// Gate proposes intermediate → return proposal to athlete
// Hypothesis agent fails → retry once; then fall back to template
// Selection agent fails → use highest-scored hypothesis
// Session planner fails → retry once; then fall back to simpler approach
// Validation fails → return errors to session planner for regeneration
// Persistence fails → log error; retry; alert after 3 failures
```

---

## Cross-References

- TrainingPlan entity: `01-entities/training-plan.md`
- PlannedSession entity: `01-entities/planned-session.md`
- Checkpoint entity: `01-entities/checkpoint.md`
- TrainingGoal inputs: `01-entities/training-goal.md`
- AthletePreferences (weekly_schedule, sport_background): `01-entities/athlete-preferences.md`
- Adaptation data collection rationale for structural rules: `02-computations/adaptation-signature.md`
- Confidence model: `00-foundations/confidence-model.md`
- Hypothesis agent: `03-agents/hypothesis-agent.md`
- Hypothesis selector agent: `03-agents/hypothesis-selector-agent.md`
- Session planner agent: `03-agents/session-planner-agent.md`
