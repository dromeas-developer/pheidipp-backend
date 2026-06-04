# Adaptation Signature

## Purpose

Once sufficient `AdaptationObservation` records exist (≥ 3 complete adaptation windows), the adaptation signature feeds personalised constraints to the weekly synthesis layer.

---

## The Adaptation Window as Atomic Unit

Individual sessions are not the unit of analysis for adaptation learning. The adaptation window is.

A hard adaptation window is 2-3 quality sessions in close succession, treated as a single compound stimulus. The twin does not decompose individual session contributions within an adaptation window. One compound stimulus → one clean recovery observation window → one readable response.

```typescript
type AdaptationWindowDefinition = {
  // Detected when:
  quality_sessions_in_5_days: number >= 2,  // threshold, vo2max, tempo, long_run
  total_quality_load: number,               // sum of aerobic + neuromuscular load
  block_intensity_profile: 'interval_dominant' | 'threshold_dominant' | 'volume_dominant'
}

type RecoveryWindowDefinition = {
  // Starts after last quality session in the adaptation window
  // Ends when Layer 4 wellness signals return to personal baseline
  // Measured by: avg_sleeping_hr_bpm and hrv_overnight_avg_ms trends
}
```

Note: `PlannedSession.block_id` (session grouping) and adaptation windows are related but distinct concepts:
- `block_id` groups consecutive quality sessions within a single week's schedule
- An adaptation window is a physiological construct spanning 2-3 quality sessions plus recovery time for adaptation measurement

---

## Yield Profiles

`yield_by_intent_state` maps `PhysiologicalIntentState` → `fitness_change_per_unit_load`:

```typescript
// Example observation:
{
  threshold: 0.042,     // 0.042 fitness points gained per unit of threshold load
  low_aerobic: 0.018,   // lower yield from easy aerobic
  vo2: 0.031
}
```

Over multiple adaptation windows, these values build the athlete's adaptation signature. An athlete with high threshold yield gets more threshold work in the plan; an athlete with high aerobic volume yield gets more volume. See `01-entities/adaptation-observation.md`.

---

## Plan Personalisation from Adaptation Signature

Once sufficient `AdaptationObservation` records exist (≥ 3 complete adaptation windows), the adaptation signature feeds personalised constraints to the weekly synthesis layer:

- **Pre-week review service** (Python) uses `yield_by_intent_state` to decide if intensity allocation should be adjusted
- **Weekly synthesis agent** uses `recovery_trajectory` to set appropriate recovery spacing
- **Plan generation** uses aggregate patterns to inform the phase arc methodology

```typescript
function computePersonalisedPlanConstraints(
  observations: AdaptationObservation[]
): PersonalisedConstraints {
  const avg_recovery_days = mean(observations.map(o => o.recovery_trajectory.days_to_baseline_return))

  return {
    // Recovery buffer between hard adaptation windows (default 2 easy days)
    min_recovery_days_between_blocks: Math.max(2, Math.ceil(avg_recovery_days)),

    // Training emphasis (which state type to prioritise in sessions)
    dominant_yield_state: argmax(computeYieldByState(observations, /* each state */)),

    // Structural sensitivity
    structural_sensitivity: mean(observations.map(o => o.recovery_trajectory.hrv_suppression_depth))
  }
}
```

---

## Plan Structure as Data Collection Strategy

The session distribution structural rules in `02-computations/plan-generation.md` are not just coaching best practice — they create the clean experimental conditions needed for adaptation learning:

- Long run followed by rest → clean 24-48h observation window for structural fatigue response
- Threshold sandwiched between easy days → pre-session baseline established; post-session recovery window clean
- Hard adaptation windows deliberate and periodic → one compound stimulus, one recovery window, one response

These structural rules serve adaptation data collection without any additional overhead.

---

## Cross-References

- AdaptationObservation entity: `01-entities/adaptation-observation.md`
- Plan generation consuming adaptation constraints: `02-computations/plan-generation.md` (shared types and regeneration triggers)
- Plan generation fitness improvement mode: `02-computations/plan-generation-fitness-improvement.md` (volume/intensity progression uses yield data)
- PhysiologicalSegment yield computation (what state was the athlete in): `01-entities/physiological-segment.md`
- Vision-level description of adaptation learning: `vision/twin/adaptation-signature.md`