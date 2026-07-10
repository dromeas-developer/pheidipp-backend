# Signal Cleaning — 7-Step Preprocessing Pipeline

## Purpose
- Defines the fixed 7-step preprocessing pipeline that transforms raw FIT data into clean sensor streams
- All segmentation, HMM inference, and Generation 2+ threshold detection depend on this pipeline
- Steps must run in fixed order; later steps depend on earlier steps being complete

## The 7-Step Pipeline

```typescript
type CleanedStream = {
  time_series: {
    t: number          // seconds from session start
    hr_bpm: number | null
    rr_ms: number | null
    power_w: number | null
    gap_sec_per_km: number | null  // always GAP; never raw pace
    cadence_rpm: number | null
    elevation_m: number | null
    grade_pct: number | null
    variability_index: number | null  // computed in step 3
    // Rolling features (step 4):
    hr_30s_mean: number | null
    hr_60s_mean: number | null
    hr_120s_mean: number | null
    power_30s_mean: number | null
    gap_30s_mean: number | null
  }[]
  sampling_rate_hz: number  // after resampling; target: 1 Hz
  available_channels: AvailableChannels
}
```

### Step 1 — Artifact Removal

Remove physiologically impossible values before any other processing.

```typescript
function removeArtifacts(records: FitRecord[]): FitRecord[] {
  return records.map(r => ({
    ...r,
    hr_bpm:     (r.hr_bpm > 220 || r.hr_bpm < 30) ? null : r.hr_bpm,
    power_w:    r.power_w > (3 * rollingMedian(records, 'power_w', 30)) ? null : r.power_w,
    speed_ms:   r.speed_ms > 25 ? null : r.speed_ms,  // > 90 km/h = GPS spike
    rr_ms:      r.rr_ms < 200 || r.rr_ms > 2500 ? null : r.rr_ms  // HR 24–300 range
  }))
}
```

**RR deviation check (follow-on to the hard bound):** RR values that survive the
200–2500 ms hard bound are then subjected to a rolling-median deviation filter.
For each RR sample, compute the rolling median over a trailing window of
non-null RR samples (window of 30 seconds / 30 samples at the 1 Hz rate after
resampling) and null any sample that deviates more than ±20% from that rolling
median. This two-stage RR artifact removal — hard bound then deviation filter —
is what produces the cleaned RR series that the downstream
`ThresholdDetectionService` HRV-inflection algorithm (`02-computations/threshold-detection.md`,
Algorithm 2 step 1: "values outside ±20% of rolling median removed") consumes.
The hard bound alone is sufficient to reject physiologically impossible RR
values; the deviation filter rejects physiologically plausible-but-erroneous
samples (sensor misreads, ectopic beats recorded as intervals) that would
corrupt per-window RMSSD computation downstream. Nulls propagate through the
rolling window: a window with fewer than 2 non-null RR samples contributes
the median of the available non-null samples, and a window with zero non-null
samples leaves the candidate sample unchanged.

### Step 2 — Smoothing / Filtering

Reduce noise while preserving physiologically real transitions.

```typescript
// HR: exponential moving average (α=0.1; strong smoothing for noisy optical HR)
function smoothHR(hr_series: (number | null)[]): (number | null)[] {
  const α = 0.1
  return hr_series.reduce((acc, v, i) => {
    if (v === null) return [...acc, acc[i - 1] ?? null]
    const prev = acc[i - 1] ?? v
    return [...acc, α * v + (1 - α) * prev]
  }, [] as (number | null)[])
}

// Power and pace: Savitzky-Golay filter (window=7, polynomial=3)
// Preserves peak shapes better than moving average
```

### Step 3 — Derived Metrics

Compute the metrics that downstream algorithms need.

```typescript
function computeDerivedMetrics(record: FitRecord, effort_normalisation: EffortNormalisationFn): DerivedRecord {
  return {
    gap_sec_per_km: effort_normalisation(record.pace_sec_per_km_raw, record.grade_pct),
    power_to_hr_ratio: record.power_w && record.hr_bpm ? record.power_w / record.hr_bpm : null,
    // Variability index: computed per 30-second window in step 4; placeholder here
    variability_index: null
  }
}
```

### Step 4 — Rolling Features

Compute window-based statistics used by segmentation and HMM.

```typescript
const WINDOWS_SECONDS = [30, 60, 120]

function computeRollingFeatures(stream: DerivedRecord[]): void {
  for (const window of WINDOWS_SECONDS) {
    // For each position t, compute: mean, std, trend_slope over the preceding window_seconds
    // Applied to: hr_bpm, power_w, gap_sec_per_km, cadence_rpm
  }
  // Variability index: coefficient of variation of pace/power over 30s window
  // Written to variability_index field on each record
}
```

### Step 5 — Changepoint Detection

Identify structural breaks in the feature time-series. Used by Generation 1 and 2 segmentation. Generation 3 (HMM) uses the rolling features directly.

```typescript
// Identifies timestamps where the signal distribution changes significantly
// Algorithm: PELT (Pruned Exact Linear Time) on rolling feature vectors
// Output: array of changepoint timestamps in seconds from session start
```

### Step 6 — State Inference

**Generation 1 (heuristic-v1):** Threshold-based classification using HR zones relative to TwinState lt1/lt2.

**Generation 2 (statistical-v1):** PELT/BOCPD on feature vectors from step 4. More robust to noise.

**Generation 3 (hmm-v1):** HMM inference using feature vectors. Produces posterior distributions.

See `02-computations/segmentation-heuristic.md` and `02-computations/segmentation-hmm.md`.

### Step 7 — Segment Alignment

Match inferred segments to PlannedSegment records using temporal overlap.

```typescript
function alignToPlan(
  inferred_segments: InferredSegment[],
  planned_segments: PlannedSegment[]
): PhysiologicalSegment[] {
  return inferred_segments.map(seg => {
    const overlap = planned_segments.find(p =>
      rangesOverlap(
        [seg.start_offset_s, seg.start_offset_s + seg.duration_s],
        [p.planned_start_offset_seconds, p.planned_start_offset_seconds + p.planned_duration_seconds]
      )
    )
    return { ...seg, planned_segment_id: overlap?.id ?? null }
  })
}
// Unaligned segments → planned_segment_id = null; never discarded
```

## Pipeline Invariants
- Steps run in fixed order 1→7. No step may be skipped or reordered.
- Null propagation: artifact-removed nulls propagate through smoothing. A channel with > 80% null values after artifact removal is marked unavailable in `AvailableChannels`.
- Resampling: FIT files vary in recording rate (1 Hz typical; some devices record at 0.5 Hz). The pipeline resamples to a uniform 1 Hz time series before step 1.
- If the pipeline produces a stream shorter than 5 minutes of non-null HR data, `RawSensorStream` is not created and segmentation is skipped.

## Cross-References
- Cleaned stream storage: `01-entities/raw-sensor-stream.md`
- GAP computation used in step 3: `02-computations/effort-normalisation.md`
- Heuristic segmentation (steps 5-7 for Gen 1): `02-computations/segmentation-heuristic.md`
- HMM segmentation (steps 5-7 for Gen 3): `02-computations/segmentation-hmm.md`
- PhysiologicalSegment output schema: `01-entities/physiological-segment.md`
