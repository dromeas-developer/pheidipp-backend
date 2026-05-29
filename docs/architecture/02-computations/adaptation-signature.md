# Adaptation Signature — Block-Level Yield Profiles

## Purpose
- Defines how the system learns per-athlete adaptation patterns from block-level observations
- The output drives plan personalisation: recovery buffers, training emphasis, session spacing

## The Training Block as Atomic Unit

Individual sessions are not the unit of analysis for adaptation learning. The training block is.

A hard block is 2-3 quality sessions in close succession, treated as a single compound stimulus. The twin does not decompose individual session contributions within a block. One compound stimulus → one clean recovery observation window → one readable response.

```typescript
type HardBlockDefinition = {
  // Detected when:
  quality_sessions_in_5_days: number >= 2,  // threshold, vo2max, tempo, long_run
  total_quality_load: number,               // sum of aerobic + neuromuscular load
  block_intensity_profile: 'interval_dominant' | 'threshold_dominant' | 'volume_dominant'
}

type RecoveryWindowDefinition = {
  // Starts after last quality session in the block
  // Ends when Layer 4 wellness signals return to personal baseline
  // Measured by: avg_sleeping_hr_bpm and hrv_overnight_avg_ms trends
}
```

## What Gets Measured After Each Block

```typescript
type AdaptationSignal = {
  // 1. Short-term fatigue depth
  hrv_suppression_depth: number  // peak deviation below baseline (units of IQR)
  hr_elevation_depth: number     // peak elevation above baseline
  // Measured 24h after last quality session

  // 2. Recovery trajectory
  days_to_baseline_return: number
  // The number of days until both HRV and sleeping HR return to within 0.5 IQR of baseline
  // This directly determines recovery buffer width in plan generation

  // 3. Execution quality at next quality session
  post_recovery_execution_quality: number  // 0.0–1.0; vs_target_pct from ExecutionObservation
  // Confirms whether the recovery window was adequate
}
```

## Yield Profile Computation

```typescript
// Per PhysiologicalIntentState: how much fitness change per unit of load?
// Accumulated across blocks over time → adaptation signature

function computeYieldByState(
  block_observations: AdaptationObservation[],
  state: PhysiologicalIntentState
): number | null {
  const relevant = block_observations.filter(o =>
    o.yield_by_intent_state[state] !== undefined
  )
  if (relevant.length < 3) return null  // insufficient data
  // Weighted average: more recent observations weighted higher
  return weightedMean(relevant.map(o => o.yield_by_intent_state[state]!), relevant.map(o => recencyWeight(o)))
}
```

## Plan Personalisation from Adaptation Signature

Once sufficient `AdaptationObservation` records exist (≥ 3 complete blocks), `PlanGenerationService` uses these patterns:

```typescript
function computePersonalisedPlanConstraints(
  observations: AdaptationObservation[]
): PersonalisedConstraints {
  const avg_recovery_days = mean(observations.map(o => o.recovery_trajectory.days_to_baseline_return))

  return {
    // Recovery buffer between hard blocks (default 2 easy days)
    min_recovery_days_between_blocks: Math.max(2, Math.ceil(avg_recovery_days)),

    // Training emphasis (which state type to prioritise in sessions)
    dominant_yield_state: argmax(computeYieldByState(observations, /* each state */)),

    // Structural sensitivity
    structural_sensitivity: mean(observations.map(o => o.recovery_trajectory.hrv_suppression_depth))
  }
}
```

## Plan Structure as Data Collection Strategy

The session distribution structural rules in `02-computations/plan-generation.md` are not just coaching best practice — they create the clean experimental conditions needed for adaptation learning:

- Long run followed by rest → clean 24-48h observation window for structural fatigue response
- Threshold sandwiched between easy days → pre-session baseline established; post-session recovery window clean
- Hard blocks deliberate and periodic → one compound stimulus, one recovery window, one response

These structural rules serve adaptation data collection without any additional overhead.

## Cross-References
- AdaptationObservation entity: `01-entities/adaptation-observation.md`
- Plan generation consuming adaptation constraints: `02-computations/plan-generation.md`
- PhysiologicalSegment yield computation (what state was the athlete in): `01-entities/physiological-segment.md`
- Vision-level description of adaptation learning: `vision/twin/adaptation-signature.md`
