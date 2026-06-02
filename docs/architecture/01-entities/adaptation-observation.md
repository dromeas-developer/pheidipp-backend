# AdaptationObservation Entity

## Purpose

- Records the relationship between training load applied and fitness change produced for an **adaptation observation window** (2-3 quality sessions followed by recovery)
- The source data for the athlete's adaptation signature and yield profiles
- Drives plan personalisation in PlanGenerationService once sufficient observations accumulate

---

## TypeScript Schema

```typescript
type AdaptationObservation = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete
  adaptation_window_id: string          // UUID, identifies the adaptation observation window (2-3 quality sessions + recovery)
  window_start_date: string           // YYYY-MM-DD
  window_end_date: string               // YYYY-MM-DD
  total_aerobic_load: number
  total_neuromuscular_load: number
  total_structural_load: number
  fitness_delta: number               // TwinState fitness_score change across window
  recovery_trajectory: RecoveryTrajectory
  yield_by_intent_state: Partial<Record<PhysiologicalIntentState, number>>
  analysis_version: string
}
```

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

Over multiple adaptation windows, these values build the athlete's adaptation signature. An athlete with high threshold yield gets more threshold work in the plan; an athlete with high aerobic volume yield gets more volume. See `02-computations/adaptation-signature.md`.

---

## Block Boundary Detection

`AdaptationBlockDetectionTask` identifies adaptation window boundaries as:
- 2+ quality sessions (`threshold`, `vo2max`, `tempo`, `hill_repeats`, `fartlek`, `long_run`) in the preceding 5 days followed by 2+ `easy_run` or `rest` sessions — the "hard adaptation window + recovery" pattern
- OR: week boundaries in the `TrainingPlan.phases` array

In planned training, `block_id` groups on `PlannedSession` records are the primary input for this detection. The weekly synthesis agent creates `block_id` groups precisely to generate the pattern that `AdaptationBlockDetectionTask` later identifies as adaptation windows. The `block_id` is the planning mechanism; the adaptation window is the observation purpose.

---

## Invariants

- `AdaptationObservation` is only created for athletes with ≥ 6 weeks of calibration-eligible sessions (earlier data lacks sufficient signal).
- Records are append-only. Analysis version changes increment `analysis_version` and new records are created alongside old ones (old records receive `superseded_at`).
- `yield_by_intent_state` only contains keys for states that appeared in the adaptation window's `PhysiologicalSegment` records. Missing keys mean no exposure to that state during the adaptation window.

---

## Events

### Produced

| Event | Trigger | Version | Payload |
|---|---|---|---|
| `adaptation_observation_created` | Record inserted | v1 | `{observation_id, adaptation_window_id, fitness_delta, days_to_baseline_return}` |

---

## Storage Model

| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `adaptation_observations` table | append-only | strong | indefinite |

---

## Runtime Ownership

Owns:
- Adaptation window-level adaptation measurements

Does Not Own:
- How yield profiles drive plan generation → `02-computations/plan-generation.md`
- Adaptation signature computation → `02-computations/adaptation-signature.md`

---

## Cross-References

- Adaptation signature entity: `02-computations/adaptation-signature.md`
- Plan generation consuming adaptation constraints: `02-computations/plan-generation.md`
- PhysiologicalSegment yield computation (what state was the athlete in): `01-entities/physiological-segment.md`
- Vision-level description of adaptation learning: `vision/twin/adaptation-signature.md`