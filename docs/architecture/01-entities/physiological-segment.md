# PhysiologicalSegment — Inferred Physiological State During a Session

## Purpose
- Records what physiological state the athlete was actually in at each moment during a session
- The stable interface between the segmentation pipeline and all consuming systems
- All three segmentation pipeline generations produce identically-structured records

## TypeScript Schema

```typescript
type SegmentationType = 'heuristic-v1' | 'statistical-v1' | 'hmm-v1'

// PlannedSegment — what was intended (derived from WorkoutStep)
type PlannedSegment = {
  id: string
  workout_step_id: string              // FK → WorkoutStep
  planned_start_offset_seconds: number
  planned_duration_seconds: number
  target_state: PhysiologicalIntentState
}

// DeviceSegment — what the watch recorded (from FIT lap messages)
type DeviceSegment = {
  id: string
  activity_id: string                  // FK → Activity
  lap_index: number
  start_offset_seconds: number
  duration_seconds: number
  lap_trigger: string                  // 'manual', 'distance', 'time', 'position_start', etc.
}

// PhysiologicalSegment — inferred from signal data (stable interface)
type PhysiologicalSegment = {
  id: string                           // UUID, PK
  activity_id: string                  // UUID, FK → Activity
  planned_segment_id: string | null    // FK → PlannedSegment; null if alignment failed
  start_offset_seconds: number
  duration_seconds: number
  inferred_state: PhysiologicalIntentState  // 'unknown' when confidence < 0.45
  confidence: number                   // 0.0–1.0; posterior probability of inferred_state
  state_probabilities: Record<PhysiologicalIntentState, number> | null
  // null for heuristic-v1 and statistical-v1
  // populated for hmm-v1 (full posterior distribution)
  observed_signals: {
    mean_hr_bpm: number | null
    mean_gap_sec_per_km: number | null
    mean_power_watts: number | null
    mean_cadence_rpm: number | null
    hr_variability_index: number | null
  }
  segmentation_version: SegmentationType
  superseded_at: string | null         // set when a better-version record replaces this
}
```

## Invariants
- **Stable interface.** All three segmentation pipeline generations produce `PhysiologicalSegment` records with identical schema. Only `segmentation_version` changes between generations.
- **`inferred_state = 'unknown'`** when `confidence < 0.45`. This is the correct output for ambiguous transitions — not a fallback or error state.
- **Unaligned segments** (no matching `PlannedSegment`) retain `planned_segment_id = null`. They are never discarded — they carry information about unplanned effort.
- **Superseded records** receive `superseded_at` when a higher-quality version is produced for the same activity. Old records are never deleted. Both old and new records coexist; consumers should use the most recent non-superseded record.
- **`state_probabilities`** is null for `heuristic-v1` and `statistical-v1`. Only `hmm-v1` produces full posterior distributions. Consumers must null-check.
- Segments with `confidence < 0.4` in `heuristic-v1` are not used in `per_rep_analysis` in `ExecutionObservation`. The coach makes no claims about unknown-state segments.

## Three-Way Comparison

```
PlannedSegment.target_state     → what was prescribed
DeviceSegment.lap_trigger       → how the device recorded boundaries
PhysiologicalSegment.inferred_state → what the physiology actually showed
```

The gap between `PlannedSegment.target_state` and `PhysiologicalSegment.inferred_state` is the compliance signal for all execution analysis.

## Events

### Produced
None. Segments are consumed by `ExecutionAnalysisService` and `ObjectiveUpdateService`.

### Consumed
| Event | Action | Version |
|---|---|---|
| `activity_ingested` (after cleaning) | Triggers `SegmentationTask` | v1 |

## APIs

```yaml
GET /athletes/{athlete_id}/activities/{activity_id}/segments
Response: 200
  planned_segments: PlannedSegmentResponse[]
  device_segments: DeviceSegmentResponse[]
  physiological_segments: PhysiologicalSegmentResponse[]  # latest non-superseded only
Auth: Bearer JWT, require_self
```

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `planned_segments` table | append-only | strong | indefinite |
| `device_segments` table | append-only | strong | indefinite |
| `physiological_segments` table | append-only + superseded_at | strong | indefinite |

Index: `(activity_id, segmentation_version, superseded_at NULLS FIRST)` for latest-version queries.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | Yes | No | No |
| Service | Yes | insert() only; superseded_at update only | No |
| Repository | Yes | insert(); update superseded_at | No |

## Runtime Ownership
Owns:
- Inferred physiological state records
- The segmentation version chain for an activity

Does Not Own:
- Segmentation algorithms → `02-computations/segmentation-heuristic.md`, `02-computations/segmentation-hmm.md`
- How segments feed execution analysis → `01-entities/execution-observation.md`
- Signal preprocessing → `02-computations/signal-cleaning.md`

## Failure Semantics
- Segmentation failure → no segments created for this activity; execution analysis falls back to lap data; retry scheduled
- Partial segmentation (some segments have `confidence = 0.0`) → those segments created with `inferred_state = unknown`; not a failure

## Observability
Metrics:
- `physiological_segment.created.total`: by segmentation_version
- `physiological_segment.unknown_state.rate`: percentage of segments with inferred_state=unknown
- `physiological_segment.confidence.distribution`: histogram
- `physiological_segment.segmentation.latency_ms`
