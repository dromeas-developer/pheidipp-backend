# AthleteWellnessBaseline — Cached Rolling Wellness Reference

## Purpose
- Stores the computed rolling baseline per wellness signal per athlete
- The reference point against which daily values are compared to produce deviation scores
- Recomputed nightly; one row per athlete per signal

## TypeScript Schema

```typescript
type WellnessSignal =
  | 'avg_sleeping_hr_bpm'
  | 'min_sleeping_hr_bpm'
  | 'hrv_overnight_avg_ms'
  | 'hrv_overnight_min_ms'
  | 'total_sleep_minutes'
  | 'deep_sleep_minutes'
  | 'rem_sleep_minutes'

type AthleteWellnessBaseline = {
  athlete_id: string          // UUID, FK → Athlete
  signal: WellnessSignal      // unique per athlete per signal
  baseline_value: number      // median of last 28 days of non-null values
  baseline_variability: number // IQR of last 28 days of non-null values
  sample_count: number        // number of non-null values used
  computed_from: string       // YYYY-MM-DD (start of 28-day window)
  computed_to: string         // YYYY-MM-DD (end of 28-day window)
  computed_at: string         // ISO 8601
}
```

## Computation Formula

```typescript
// Requires minimum 14 non-null values in the past 28 days
// Uses median (not mean) to resist outlier nights (illness, travel)
// Uses IQR (not std dev) for the same reason

function computeBaseline(values: number[]): { median: number; iqr: number } {
  const sorted = [...values].sort((a, b) => a - b)
  const q1 = sorted[Math.floor(sorted.length * 0.25)]
  const q3 = sorted[Math.floor(sorted.length * 0.75)]
  const median = sorted[Math.floor(sorted.length * 0.5)]
  return { median, iqr: q3 - q1 }
}
```

If `sample_count < 14`, no baseline is written for that signal. The signal is excluded from recovery modifier computation for this athlete until sufficient data accumulates.

## Signal Weights in Recovery Modifier

These weights are defined here as the authoritative reference for `WellnessModifierService`:

| Signal | Weight | Direction of concern |
|---|---|---|
| `avg_sleeping_hr_bpm` | 0.35 | Elevated above baseline |
| `hrv_overnight_avg_ms` | 0.30 | Suppressed below baseline |
| `total_sleep_minutes` | 0.20 | Reduced below baseline |
| `min_sleeping_hr_bpm` | 0.10 | Elevated above baseline |
| `deep_sleep_minutes` | 0.05 | Reduced below baseline |

Deviation score formula:
```typescript
deviation[signal] = (rolling_avg_3night[signal] - baseline_value) / baseline_variability
// Positive deviation on HR signals = worse than baseline
// Negative deviation on HRV/sleep signals = worse than baseline
// Both directions normalised to: negative = worse
normalised_deviation[signal] = signal_is_hr ? deviation : -deviation
```

## Invariants
- Unique constraint on `(athlete_id, signal)` — one row per signal per athlete. Recomputed values **overwrite** the existing row (unlike `AthleteWellness` which is additive). The baseline is always a fresh window computation, not cumulative.
- A missing row means insufficient data for that signal. `WellnessModifierService` skips that signal gracefully.
- Baselines are always computed from the past 28 calendar days from `computed_to` date. The window does not slide mid-day.

## Events

### Produced
| Event | Trigger | Version | Payload |
|---|---|---|---|
| `wellness_baseline_updated` | Any baseline row updated | v1 | `{athlete_id, signals_updated: string[], sample_counts: Record<string, number>}` |

### Consumed
| Event | Action | Version |
|---|---|---|
| `wellness_record_ingested` | Schedules `BaselineComputationTask` (not immediate) | v1 |

## Storage Model
| Data | Strategy | Consistency | Retention |
|---|---|---|---|
| `athlete_wellness_baselines` table | upsert (overwrite on recompute) | strong | indefinite |

Index: `(athlete_id, signal)` — primary key equivalent.

## Mutation Rules
| Layer | Read | Write | Delete |
|---|---|---|---|
| API | No (internal only) | No | No |
| Service | Yes | upsert (overwrite) | No |
| Repository | Yes | upsert | No |

## Runtime Ownership
Owns:
- Rolling baseline values and variability per signal
- Minimum sample count gate (14 values)

Does Not Own:
- Recovery modifier classification → `02-computations/wellness-modifier.md`
- Raw wellness data → `01-entities/athlete-wellness.md`

## Performance Constraints
- `BaselineComputationTask` for one athlete: p95 < 500ms
- Nightly batch for all athletes: must complete within 2 hours

## Observability
Metrics:
- `wellness_baseline.athletes_with_full_coverage`: count of athletes with ≥5 signals baselined
- `wellness_baseline.computation.latency_ms`
