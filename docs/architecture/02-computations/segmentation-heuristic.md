# Segmentation — Generation 1 Heuristic
## Purpose

- Defines the threshold-based heuristic segmentation algorithm
- Produces PhysiologicalSegment records with segmentation_version = 'heuristic-v1'
- The simplest segmentation pipeline; used when HMM model is not yet trained or when per-athlete fine-tuning is unavailable

## Algorithm

```typescript
// Generation 1: threshold-based changepoint detection using smoothed HR and power signals
// Simple and auditable — every decision is traceable to a threshold comparison

function segmentHeuristic(
  cleaned_stream: CleanedStream,
  twin_state: TwinState,
  planned_segments: PlannedSegment[]
): PhysiologicalSegment[] {
  const { lt1_estimate_bpm, lt2_estimate_bpm, max_hr_estimate_bpm } = twin_state

  // HR zone thresholds derived from twin threshold estimates
  const zones = {
    low_aerobic:  [0, lt1_estimate_bpm * 0.97],
    high_aerobic: [lt1_estimate_bpm * 0.97, lt2_estimate_bpm * 0.97],
    threshold:    [lt2_estimate_bpm * 0.97, lt2_estimate_bpm * 1.03],
    vo2:          [lt2_estimate_bpm * 1.03, max_hr_estimate_bpm]
  }

  // Identify changepoints from step 5 of cleaning pipeline
  const changepoints = detectChangepoints(cleaned_stream)

  // Classify each segment between changepoints
  return changepoints.map((cp, i) => {
    const next_cp = changepoints[i + 1] ?? cleaned_stream.time_series.length
    const segment_records = cleaned_stream.time_series.slice(cp, next_cp)
    const mean_hr = mean(segment_records.map(r => r.hr_bpm).filter(Boolean) as number[])

    const inferred_state = classifyByHR(mean_hr, zones)
    const confidence = computeHeuristicConfidence(segment_records, inferred_state, zones)

    return {
      start_offset_seconds: cp,
      duration_seconds: next_cp - cp,
      inferred_state: confidence < 0.45 ? 'unknown' : inferred_state,
      confidence,
      state_probabilities: null,  // not produced in Gen 1
      observed_signals: summariseSignals(segment_records),
      segmentation_version: 'heuristic-v1'
    }
  })
}

function computeHeuristicConfidence(
  records: TimeSeriesRecord[],
  inferred_state: PhysiologicalIntentState,
  zones: Record<string, [number, number]>
): number {
  // High confidence: HR consistently in one zone with clear transition at boundaries
  // Low confidence: HR straddling zone boundary or noisy
  const zone_range = zones[inferred_state]
  if (!zone_range) return 0.3
  const in_zone_pct = records.filter(r =>
    r.hr_bpm && r.hr_bpm >= zone_range[0] && r.hr_bpm < zone_range[1]
  ).length / records.length
  return Math.min(0.9, in_zone_pct * 1.1)  // cap at 0.9; heuristic is never fully certain
}
```

## Known Failure Modes

- **Ambiguous transitions:** Gradual HR drift that never clearly crosses a zone boundary. These segments receive low confidence and `inferred_state = 'unknown'`.
- **Noisy optical HR:** High variability in optical HR readings causes frequent zone boundary crossings. `confidence` drops; many `unknown` segments.
- **Recovery intervals:** HR during inter-interval recovery is often still in a zone that looks like threshold/VO2 because cardiovascular lag hasn't returned it to Zone 2. The heuristic cannot distinguish this from effort — this is why recovery analysis uses pace pullback and HR decline rate, not HR zone. See `01-entities/execution-observation.md`.

## segmentation_version: 'heuristic-v1'

Records are superseded (not deleted) when Generation 3 HMM processes the same activity. Old records receive `superseded_at`. Consuming systems always read the latest non-superseded version.

## Cross-References
- Cleaned stream input (steps 1-4 of preprocessing): `02-computations/signal-cleaning.md`
- HMM that supersedes this: `02-computations/segmentation-hmm.md`
- PhysiologicalSegment output schema: `01-entities/physiological-segment.md`
- Why recovery intervals must not be analysed by HR zone: `01-entities/execution-observation.md`
