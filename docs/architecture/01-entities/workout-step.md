# WorkoutStep — Individual Step Within a GeneratedWorkout

## Purpose
- Stores one segment of a generated workout with its physiological intent and data-tier-appropriate targets
- Carries PhysiologicalIntentState as the primary intent signal used by all downstream analysis
- The atomic unit for execution compliance assessment

## TypeScript Schema

```typescript
type StepType = 'warmup' | 'work' | 'recovery' | 'cooldown'

type WorkoutStep = {
  id: string                             // UUID, PK
  generated_workout_id: string           // UUID, FK → GeneratedWorkout
  step_order: number                     // 1-indexed; unique within workout
  step_type: StepType
  physiological_intent: PhysiologicalIntentState  // NEVER null

  // Targets — populated based on athlete data tier
  // Tier 1-2: target_power_watts primary
  // Tier 3-4: target_gap_sec_per_km primary
  // Tier 5-6: null; description only
  target_duration_seconds: number | null
  target_hr_zone: number | null          // 1–5; supplementary
  target_power_watts: number | null      // Tier 1-2
  target_gap_sec_per_km: number | null   // ALWAYS GAP; never raw pace

  description: string  // plain English shown to athlete; always present
}
```

## Invariants
- `physiological_intent` is **never null**. Every step has an intent, including warmup and cooldown.
  - `step_type = 'warmup'` → `physiological_intent = 'warmup'`
  - `step_type = 'cooldown'` → `physiological_intent = 'cooldown'`
  - `step_type = 'recovery'` (between intervals) → `physiological_intent = 'recovery'`
  - `step_type = 'work'` → `physiological_intent` set from the session's prescribed effort state
- `step_order` is unique within a `generated_workout_id`. Enforced by unique constraint on `(generated_workout_id, step_order)`.
- `target_gap_sec_per_km` uses GAP values only. The workout generation agent prompt enforces this.
- Numeric targets are null for Tier 5-6 athletes. `description` is always non-null and always carries the intent in plain language.
- Steps are never updated after creation. A regenerated workout creates a new `GeneratedWorkout` with new steps.

## PhysiologicalIntentState Usage

`WorkoutStep.physiological_intent` is the **prescribed** state. It is compared against:
- `PhysiologicalSegment.inferred_state` (what the athlete's physiology showed) → compliance assessment
- `PlannedSegment.target_state` (derived from this step) → segment alignment

This is the mechanism by which the shared language flows from prescription through execution through analysis.

## Events

### Produced
None. WorkoutStep is a child entity; events are produced by `GeneratedWorkout`.

### Consumed
None. WorkoutStep is read by `ExecutionAnalysisService` and `SegmentationService`.

## APIs
WorkoutStep is always returned as part of its parent GeneratedWorkout:
```yaml
# Embedded in all GeneratedWorkout responses:
steps: WorkoutStepResponse[]
```

No standalone WorkoutStep endpoints.

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `workout_steps` table | append-only | strong | indefinite |

Index: `(generated_workout_id, step_order)` for ordered step retrieval.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes (via parent) | No | No |
| Service | Yes | insert() only | No |
| Repository | Yes | insert() only | No |

## Runtime Ownership
Owns:
- Step-level intent and targets
- The prescribed PhysiologicalIntentState for each workout segment

Does Not Own:
- How targets are computed → `03-agents/workout-generation-agent.md`
- Execution compliance assessment → `01-entities/execution-observation.md`
- Segmentation alignment → `01-entities/physiological-segment.md`

## Implementation Notes
- `PlannedSegment` records are derived from `WorkoutStep` records at segmentation time: one `PlannedSegment` per `WorkoutStep`, carrying the same `physiological_intent` as `target_state`
- The `WorkoutLibraryEntry.steps` JSONB uses the same structure as `WorkoutStep` but is embedded rather than FK-linked — library entries are templates, not parent-linked records
- A threshold session producing 4 × 5-minute intervals would generate: 1 warmup step + 4 work steps (physiological_intent=threshold) + 3 recovery steps (between intervals) + 1 cooldown step = 9 steps total
