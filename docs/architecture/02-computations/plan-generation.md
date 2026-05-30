# Plan Generation — Computation
*Converts TrainingBlock + TwinState into TrainingPlan + PlannedSessions via training length gate, hypothesis generation, validation, synthesis, and instantiation.*

---

## Purpose
- Defines the multi-phase algorithm that produces a training plan from athlete context
- For `race_event` mode: LLM-driven hypothesis generation with constraint-first validation
- For `fitness_improvement`, `maintenance`, `recovery` modes: deterministic phase arc formulas (unchanged)

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
// - race_event: LLM-driven hypothesis generation → validation → synthesis → instantiation
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
type TrainingLengthGateResult = {
  action: 'proceed' | 'propose_intermediate' | 'propose_shorter_goal'
  message: string
  intermediate_objectives?: string[]
}

function evaluateTrainingLength(
  weeks_until_goal: number,
  fitness_level: number,
  goal_event_type: GoalEventType
): TrainingLengthGateResult {
  // Goal is too far away — propose intermediate goal
  if (weeks_until_goal > 24) {
    return {
      action: 'propose_intermediate',
      message: `Your ${goal_event_type} is ${weeks_until_goal} weeks away. That's too far ` +
               `to plan in detail — too much will change in your fitness and life. ` +
               `Let's focus on a 12-week block targeting the physiological foundations ` +
               `you'll need most: aerobic base, threshold development, and structural ` +
               `resilience. We'll reassess and plan the next phase after that.`,
      intermediate_objectives: [
        'aerobic_fitness',
        'threshold_power',
        'structural_resilience'
      ]
    }
  }
  
  // Goal is too close for a beginner
  if (weeks_until_goal < 8 && fitness_level <= 2) {
    return {
      action: 'propose_shorter_goal',
      message: `With ${weeks_until_goal} weeks to your ${goal_event_type} and your current ` +
               `fitness level, a 10K or half-marathon would be a more realistic target. ` +
               `This builds race experience and confidence for the full distance later.`
    }
  }
  
  // Goal is appropriate
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
    zone1_2: number  // percentage
    zone3: number
    zone4_5: number
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
    check: (h, inputs) => /* no back-to-back Zone 4–5 sessions */
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
  selected_hypothesis: StrategicHypothesis
  
  macrocycle_structure: string    // plain English description
  
  race_schedule: RaceScheduleEntry[]
  checkpoint_schedule: CheckpointDescriptor[]
  phase_adjustments: PhaseAdjustment[]
  
  intensity_distribution: {
    zone1_2: number
    zone3: number
    zone4_5: number
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

### Phase 3: Instantiate Executable Plan

The strategic framework is converted into PlannedSession records.

```typescript
function instantiatePlan(
  framework: StrategicFramework,
  inputs: PlanGenerationInputs
): { plan: TrainingPlan; sessions: PlannedSession[] } {
  // 1. Compute phase arc from framework.macrocycle_structure
  // 2. Distribute sessions within each phase following structural rules
  // 3. Place checkpoint sessions at framework.checkpoint_schedule positions
  // 4. Apply race disruption windows from framework.race_schedule
  // 5. Apply risk mitigations from framework.risk_mitigations
  // 6. Return TrainingPlan + PlannedSession records
}
```

**Session Distribution Rules** (unchanged from existing):
- Long run on a day with `long_workout = true`
- Long run always followed by rest or recovery_run
- Quality sessions sandwiched between easy or rest days
- No two quality sessions on consecutive dates
- Session count respects `weekly_session_count` from phase

**Checkpoint Session Flagging:**
Sessions that are checkpoints have `checkpoint_type` and `checkpoint_metric` fields set on the PlannedSession record.

---

### Phase 4: Adaptive Evolution

#### Regeneration Triggers

```typescript
type RegenerationTrigger =
  | 'new_block'
  | 'goal_date_change'        // goal_event_date moved by > 7 days
  | 'confidence_upgrade'      // twin moved from low→medium or medium→high
  | 'session_dropout'         // > 20% of sessions in 3-week window skipped or missed
  | 'secondary_event_added'   // B-race or C-race added within active plan date range
  | 'secondary_event_removed' // Secondary event removed, sessions restored
  | 'checkpoint_completed'    // Checkpoint resulted in confidence change or metric update

function shouldRegenerate(trigger: RegenerationTrigger, old_plan: TrainingPlan, new_twin: TwinState): boolean {
  // goal_date_change: only if abs(new_date - old_date) > 7 days
  // confidence_upgrade: only if old plan was generated at 'low' confidence
  // session_dropout: checked by nightly monitoring task
  // secondary_event changes: triggers redistribution, not full regeneration unless
  //   the disruption window cannot be accommodated within existing phase structure
  // checkpoint_completed: only if confidence_changed = true AND replan_triggered = true
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
// First training block: structural load is capped regardless of stated weekly_volume_hours
// The cardiovascular system tolerates volume the tendons cannot yet handle
const MAX_STRUCTURAL_LOAD_PER_WEEK_CROSSOVER = 0.7 * POPULATION_MAX_WEEK_1

// Applied as a constraint on session count and long_run duration in weeks 1-4
// Relaxed by week 5 if no injury flags in quality_flags or skip_reason
```

---

## Outputs

Creates atomically:
- One `TrainingPlan` (status=active; old plan superseded)
- N `PlannedSession` records covering the full plan duration
- M `Checkpoint` records for sessions flagged as checkpoints
- Fires `training_plan_generated` event

---

## Cross-References

- TrainingPlan entity: `01-entities/training-plan.md`
- PlannedSession entity: `01-entities/planned-session.md`
- Checkpoint entity: `01-entities/checkpoint.md`
- TrainingBlock inputs: `01-entities/training-block.md`
- AthletePreferences (weekly_schedule, sport_background): `01-entities/athlete-preferences.md`
- Adaptation data collection rationale for structural rules: `02-computations/adaptation-signature.md`
- Confidence model: `00-foundations/confidence-model.md`
