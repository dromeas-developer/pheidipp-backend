# Phase 5 — Signal Processing
*Cleaning pipeline, segmentation, per-athlete GAP, rep-level analysis*

## Hypothesis

Does the coaching depth visibly improve when it is based on inferred physiological
states rather than lap-level averages? Post-workout analysis should be able to
describe what happened within intervals — not just whether the athlete completed
them but what their physiology showed.

## Twin State at Completion

Layer 5 (Execution Patterns) active with Gen 1 heuristic segmentation.
`PhysiologicalSegment` records exist for all sessions processed through the
new pipeline. Per-athlete GAP curves established for athletes with sufficient
outdoor session history.

## Sub-Phases

| Sub-phase | Title | Key deliverable |
|---|---|---|
| 5a | Cleaning Pipeline | Artifact removal, smoothing, RawSensorStream |
| 5b | Gen 1 Segmentation | PlannedSegment, DeviceSegment, PhysiologicalSegment heuristic |
| 5c | Rep-Level Execution Analysis | ExecutionObservation upgraded from lap to segment data |
| 5d | Per-Athlete GAP | Individual grade response curve, load score reprocessing |

## Done Criteria

- Post-workout analysis for a threshold session names specific rep-level patterns
  derived from `PhysiologicalSegment` records — not just lap averages.
- Recovery interval quality is assessed from pace pullback and HR decline rate,
  not HR zone classification.
- Athletes with 20+ outdoor sessions have a personal GAP curve. Their load scores
  differ measurably from the population formula.
- Historical activities can be reprocessed through the new cleaning pipeline
  using stored FIT files without touching live records.

## Go / No-Go for Phase 6

- `RawSensorStream` exists for all new sessions processed after 5a.
- `PhysiologicalSegment` confidence scores are reasonable — Gen 1 low-confidence
  segments are flagged, not silently accepted.
- Per-athlete GAP falls back gracefully to population formula for athletes below
  the 20-session threshold.
