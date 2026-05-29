# 5c — Rep-Level Execution Analysis
*ExecutionObservation upgraded from lap to segment data*

## Objective

Upgrade post-workout analysis from lap-level averages to segment-level inference.
The coach can now describe what happened within intervals — per-rep intensity
holding, drift patterns, recovery quality from pace pullback not HR zone. This is
the most visible coaching quality improvement in Phase 5.

## Scope

`ExecutionAnalysisService` updated to consume `PhysiologicalSegment` records.
`ExecutionObservation.analysis_version` incremented. Updated coaching observations
structure with per-segment findings. `PostWorkoutAgent` prompt updated for richer context.

## Non-Goals

- Gen 2 (statistical) segmentation — deferred to 6a; this phase uses Gen 1 output
- HMM confidence-weighted analysis — deferred to 6a

## Architecture References

- How `PhysiologicalSegment` feeds execution analysis:
  `architecture/coaching-services.md` → ComparableSessionService (context structure)
- Recovery interval analysis rules (pace pullback, HR decline rate — not HR zone):
  `vision/twin/execution-patterns.md` → Threshold and Interval Patterns
- Sandbagging and positive splitting signals:
  `vision/twin/execution-patterns.md` → VO2max Session Patterns
- Session shape classification:
  `vision/twin/execution-patterns.md` → Session Shape Classification

## Dependencies

Requires 5b (`PhysiologicalSegment` records exist for calibration-eligible sessions).

## Services Modified

**`ExecutionAnalysisService`** (updated) — replaces lap-level analysis with segment-level.
- For sessions with `PhysiologicalSegment` records: uses segment data as primary
  source for `coaching_observations`.
- Falls back to lap data for sessions without `PhysiologicalSegment` (activities
  processed before 5b, or sessions where segmentation produced no results).
- New segment-level signals added to `coaching_observations`:
  - `per_rep_analysis`: array of per-rep objects (for threshold/VO2 sessions):
    `{rep_index, inferred_state, confidence, mean_gap, mean_hr, drift_pct, vs_target_pct}`
  - `recovery_analysis`: per-recovery segment:
    `{rep_index, pace_pullback_to_target, hr_decline_direction, hr_decline_rate_bpm_per_min}`
    Note: `hr_zone_during_recovery` is NOT included — see arch reference for why.
  - `sandbagging_flag`: bool (VO2 sessions — all reps at < 90% of target intensity
    with no degradation)
  - `positive_split_flag`: bool (reps 1-2 vs reps 3+ show > 5% degradation in pace)
- `analysis_version` incremented to `segment-v1`.

**`ComparableSessionService`** (updated) — `build_summary()` output now includes
`per_rep_analysis` from the updated `coaching_observations`.

## Key Constraints

- Segments with `confidence < 0.4` (`inferred_state = unknown`) are excluded from
  per-rep analysis. The coach does not make claims about unknown-state segments.
- Recovery interval quality is assessed from `pace_pullback_to_target` and
  `hr_decline_direction` — never from the HR zone the athlete was in during recovery.
- The `PostWorkoutAgent` prompt is updated to use `per_rep_analysis` and
  `recovery_analysis` from `coaching_observations`. The prompt change increments
  `GenerationEvent.prompt_version`.

## Done Criteria

- Post-workout message for a threshold session names specific rep outcomes
  (e.g. "reps 1-3 were on target; rep 4 drifted 6% above pace").
- Recovery quality references pace pullback, not HR zone.
- A sandbagged VO2max session produces a message noting the athlete had more to give.
- Sessions without `PhysiologicalSegment` (pre-5b activities) continue to produce
  valid post-workout messages from lap data — no regressions.
