# AdaptationObservation — Block-Level Adaptation Signal

## Purpose
- Records the relationship between training load applied and fitness change produced for a training block
- The source data for the athlete's adaptation signature and yield profiles
- Drives plan personalisation in PlanGenerationService once sufficient observations accumulate

## TypeScript Schema

```typescript
type AdaptationObservation = {
  id: string                          // UUID, PK
  athlete_id: string                  // UUID, FK → Athlete
  training_block_id: string           // UUID, FK → TrainingBlock
  block_start_date: string            // YYYY-MM-DD
  block_end_date: string              // YYYY-MM-DD
  total_aerobic_load: number
  total_neuromuscular_load: number
  total_structural_load: number
  fitness_delta: number               // TwinState fitness_score change across block
  recovery_trajectory: RecoveryTrajectory
  yield_by_intent_state: Partial<Record<PhysiologicalIntentState, number>>
  analysis_version: string
}

type RecoveryTrajectory = {
  // How long (days) until Layer 4 wellness signals returned to personal baseline
  // after the hardest block in the observation window
  days_to_baseline_return: number
  hrv_suppression_depth: number | null   // peak deviation below baseline
  hr_elevation_depth: number | null      // peak elevation above baseline
}
```

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

Over multiple blocks, these values build the athlete's adaptation signature. An athlete with high threshold yield gets more threshold work in the plan; an athlete with high aerobic volume yield gets more volume. See `02-computations/adaptation-signature.md`.

## Block Boundary Detection

`AdaptationBlockDetectionTask` identifies block boundaries as:
- 2+ quality sessions (`threshold`, `vo2max_intervals`, `tempo`, `long_run`) in the preceding 5 days followed by 2+ `easy_aerobic` or `rest` sessions — the "hard block + recovery" pattern
- OR: week boundaries in the `TrainingPlan.phases` array

## Invariants
- `AdaptationObservation` is only created for athletes with ≥ 6 weeks of calibration-eligible sessions (earlier data lacks sufficient signal).
- Records are append-only. Analysis version changes increment `analysis_version` and new records are created alongside old ones (old records receive `superseded_at`).
- `yield_by_intent_state` only contains keys for states that appeared in the block's `PhysiologicalSegment` records. Missing keys mean no exposure to that state during the block.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `adaptation_observation_created` | Record inserted | v1 | `{observation_id, training_block_id, fitness_delta, days_to_baseline_return}` |

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `adaptation_observations` table | append-only | strong | indefinite |

## Runtime Ownership
Owns:
- Block-level adaptation measurements

Does Not Own:
- How yield profiles drive plan generation → `02-computations/plan-generation.md`
- Adaptation signature computation → `02-computations/adaptation-signature.md`
