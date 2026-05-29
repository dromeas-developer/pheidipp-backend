# 4a — ExecutionObservation
*FIT-derived execution analysis, session shape, compliance signals*

## Objective

Build the Python execution analysis layer that reads FIT files and produces
structured findings for the post-workout agent to narrate. This is the architectural
shift from "here is what you logged" to "here is what your data shows." The LLM
receives pre-computed findings, never raw FIT data.

## Scope

`ExecutionObservation` model. `ExecutionAnalysisService` — session shape
classification, effort compliance, key signals. Updated post-workout agent context
to consume `ExecutionObservation`. `analysis_version` tagging.

## Non-Goals

- Rep-level analysis from `PhysiologicalSegment` records — deferred to 5c
  (requires segmentation pipeline). This phase works from FIT lap data and
  raw time-series, not inferred physiological states.
- Comparable session references in the coach message — deferred to 4b
- Objectives in the coach message — deferred to 4c

## Architecture References

- `ExecutionObservation` field spec:
  `architecture/data-models.md` → Analysis Layer
- Session shape classification enum:
  `architecture/data-models.md` → ExecutionObservation
- Execution analysis principles (Python computes, LLM narrates):
  `architecture/llm-and-agents.md` → The Fundamental Rule
- Aerobic session drift resistance analysis:
  `vision/twin/execution-patterns.md` → Aerobic Session Patterns
- Threshold and interval patterns:
  `vision/twin/execution-patterns.md` → Threshold and Interval Patterns
- Recovery interval analysis (why HR zone is wrong):
  `vision/twin/execution-patterns.md` → Threshold and Interval Patterns

## Dependencies

Requires 2a (FIT files in object storage), 2b (calibration eligibility),
2c (WorkoutStep with `physiological_intent` — execution is assessed relative to intent).

## Models Introduced

**`ExecutionObservation`** — structured analysis of a session. One per Activity.
Full field spec from `architecture/data-models.md`:
`activity_id` FK (unique), `session_shape`
(enum: `steady`, `progressive_fade`, `positive_split`, `w_shape`, `strong_finish`),
`effort_compliance` (JSONB), `key_signals` (JSONB),
`coaching_observations` (JSONB), `analysis_version`.

`coaching_observations` structure (pre-computed findings the agent narrates):
```json
{
  "headline": "Held threshold pace well through the back half",
  "session_type_specific": {
    "cross_rep_trend": "even",
    "final_rep_delta_pct": -1.8,
    "recovery_quality": "good_hr_decline"
  },
  "flags": ["zone_encroachment_lap_3"]
}
```

## Services & Tasks Introduced

**`ExecutionAnalysisService`** (sync, Python) — reads FIT data and produces
`ExecutionObservation`.
- `analyse(activity, generated_workout) → ExecutionObservation`
  1. Fetches FIT file from object storage via `fit_file_key`
  2. Classifies session shape from pace/HR time-series
  3. Computes effort compliance per lap relative to `WorkoutStep.physiological_intent`
  4. Computes session-type-specific signals:
     - Easy aerobic: cardiac drift score, zone encroachment events, decoupling ratio
     - Threshold/interval: per-rep pace consistency, cross-rep trend,
       recovery quality (pace pullback rate and HR decline direction — not HR zone)
     - VO2max: controlled fade score, sandbagging flag, positive split flag
  5. Writes structured `coaching_observations` dict
  Called from `FitIngestionTask` extension for calibration-eligible sessions.

## Models Modified

**`PostWorkoutAnalysis`** — adds `execution_observation_id` FK (nullable — null
for manual entries that have no FIT file).

## Services Modified

**`PostWorkoutAgent`** (updated) — `ContextBudgetService.build_post_workout_context()`
now includes `ExecutionObservation.coaching_observations` as a pre-computed block.
Agent receives findings in structured form and narrates them — never derives them.
Context budget rises to 3k–6k tokens as the execution block is richer.

## Key Constraints

- `ExecutionAnalysisService` is pure Python. No LLM, no external API calls.
- The service reads from object storage — the FIT file must be retrievable via
  `fit_file_key`. If the fetch fails, analysis is skipped and retried.
- Recovery interval quality is assessed from pace pullback and HR decline direction —
  never from HR zone classification during the recovery. See arch reference.
- `ExecutionObservation` is only created for calibration-eligible sessions with
  a linked `GeneratedWorkout` (the prescribed intent must be known for compliance).
  Activities with no `planned_session_id` or `calibration_eligible = false`
  receive a simpler analysis without compliance signals.
- `analysis_version` is written at creation. If the analysis algorithm improves,
  the version increments and historical observations can be reprocessed from
  stored FIT files.

## Done Criteria

- After syncing a threshold session, `GET /athletes/{id}/activities/{id}/analysis`
  returns a `PostWorkoutAnalysis` with a linked `ExecutionObservation` containing
  non-null `session_shape` and `coaching_observations`.
- The post-workout coach message references a specific execution pattern
  (e.g. "you faded in the final two reps") derived from the `coaching_observations`.
- An easy aerobic session produces a `coaching_observations` block with a
  cardiac drift score and zone encroachment events if any occurred.
- A manual entry (no FIT file) produces a post-workout message without errors —
  `execution_observation_id` is null and the agent falls back to compliance-only analysis.
