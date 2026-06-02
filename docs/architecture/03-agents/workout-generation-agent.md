# WorkoutGenerationAgent — Day-of Workout

## Purpose
- Generates the specific structured workout for a PlannedSession on the day it is due
- Produces WorkoutStep records with physiological_intent — not a JSON blob
- Target generation is calibrated to the athlete's data tier and current twin state

## Context Budget: ~2k–3k tokens

```typescript
type WorkoutGenerationContext = {
  // Session intent
  session: {
    session_type: SessionType
    phase_label: PhaseLabel
    week_number: number
    intent_description: string
    approximate_duration_minutes: number
  }

  // TwinState digest (via TwinContextAssemblerService)
  readiness: {
    recovery_modifier_level: RecoveryModifierLevel
    recovery_modifier_reason: string  // structured; plain language
    confidence_level: TwinConfidenceLevel
    fitness_form_descriptor: string
    // Threshold targets at confidence-appropriate precision:
    // LOW: effort descriptions ("easy aerobic effort", "comfortably hard")
    // MEDIUM: ranges ("5:30–5:50/km")
    // HIGH: point estimates ("5:38/km")
    threshold_target_description: string
    lt2_pace_sec_per_km: number | null  // null if LOW confidence
  }

  // Data tier — determines which target type to produce
  data_tier: DataTier
  target_type: 'power' | 'pace' | 'effort_description'

  // Objectives relevant to this session (max 2; filtered by session_types_relevant)
  relevant_objectives: {
    category: ObjectiveCategory
    title: string
    direction: ObjectiveDirection
  }[]
}
```

## Output Contract

```typescript
type WorkoutGenerationOutput = {
  steps: {
    step_order: number
    step_type: StepType
    physiological_intent: PhysiologicalIntent  // never null
    target_duration_seconds: number | null
    target_hr_zone: number | null
    target_power_watts: number | null
    target_gap_sec_per_km: number | null  // always GAP; never raw pace
    description: string                   // plain English; always present
  }[]
  // Number of steps: warmup + main set steps + recovery steps + cooldown
  // e.g. threshold session: 1 warmup + 4×(work + recovery) + 1 cooldown = 10 steps
}
```

## Target Type Rules by Data Tier

```typescript
const TARGET_RULES_BY_TIER: Record<DataTier, TargetTypeRule> = {
  1: { primary: 'power',    secondary: 'gap' },
  2: { primary: 'power',    secondary: 'gap' },
  3: { primary: 'gap',      secondary: 'hr' },
  4: { primary: 'gap',      secondary: 'hr' },
  5: { primary: 'description_only',      secondary: null },
  6: { primary: 'description_only',      secondary: null }
}
// Tier 5-6: all numeric targets null; description carries all intent
```

## PhysiologicalIntentState by Step Type

```typescript
// Invariant: physiological_intent is NEVER null
const INTENT_BY_STEP_TYPE: Record<StepType, PhysiologicalIntent | 'from_session_type'> = {
  warmup:   'recovery',
  cooldown: 'recovery',
  recovery: 'recovery',   // between intervals
  work:     'from_session_type'  // derived from session_type via SESSION_INTENT_MAP
}

const WORK_INTENT_BY_SESSION_TYPE: Record<SessionType, PhysiologicalIntent> = {
  easy_run:         'low_aerobic',
  long_run:         'high_aerobic',
  medium_long_run:  'high_aerobic',
  steady_state:     'high_aerobic',
  threshold:        'threshold',
  tempo:            'threshold',
  vo2max:           'vo2max',
  hill_repeats:     'vo2max',
  fartlek:          'vo2max',
  strides:          'neuromuscular',
  drills_mobility:  'neuromuscular',
  recovery_run:     'recovery',
  optional_run:     'recovery',
  cross_training:   'low_aerobic',
  test_session:     'vo2max',  // default; depends on test protocol
  // rest: no WorkoutStep records generated
}
```

## Modifier Application Sequence

Before the agent runs, Python services compute the full modifier chain:

```
TwinState threshold estimates
  → TwinContextAssemblerService → readiness digest (theoretical targets)
    → WellnessModifierService → recovery_modifier_level + scale factor
    → CyclePhaseService → luteal temperature offset (female athletes)
    → WeatherAdjustmentService → pace_adjustment_factor
    → adjusted_targets = theoretical_targets × combined factor
```

The agent receives the pre-computed `readiness` digest. It does not apply modifiers itself. The modifier output is stored on `GeneratedWorkout.adjusted_targets` by the service layer, not by the agent.

## Idempotency

Generating a workout for a `planned_session_id` that already has a `GeneratedWorkout` → returns existing workout (200), does not call the LLM.

## Prompt Location
`app/core/prompts/workout_gen_v1.md`

## Failure Semantics
- LLM failure → writes `GenerationEvent` with `success=false`; returns 503; no `GeneratedWorkout` created
- Weather fetch failure → proceeds with `adjusted_targets = theoretical_targets`; noted in `recovery_modifier_reason`

## Performance Constraints
- p95 < 5s (LLM latency)
- Pre-generated workout retrieval: p95 < 50ms

## Cross-References
- WorkoutStep schema: `01-entities/workout-step.md`
- GeneratedWorkout schema: `01-entities/generated-workout.md`
- Modifier computation chain: `02-computations/wellness-modifier.md`
- TwinState context assembly: `01-entities/twin-state.md` → Context Assembly
- PhysiologicalIntent values: `00-foundations/terminology.md`
