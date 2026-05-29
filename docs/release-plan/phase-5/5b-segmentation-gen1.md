# 5b — Generation 1 Segmentation
*PlannedSegment, DeviceSegment, PhysiologicalSegment heuristic*

## Objective

Produce the first `PhysiologicalSegment` records using heuristic threshold-based
changepoint detection. The segmentation interface is established in its stable
form — all three segment types created, version-tagged, aligned. Generation 2
and 3 will replace the inference algorithm without touching the interface.

## Scope

`PlannedSegment`, `DeviceSegment`, `PhysiologicalSegment` models.
`HeuristicSegmentationService`. Segment alignment. `segmentation_version` tagging.
`SegmentationTask` worker.

## Non-Goals

- Statistical segmentation (Gen 2 PELT/BOCPD) — deferred to 5c upgrades
- HMM segmentation (Gen 3) — deferred to Phase 6
- Per-segment execution analysis — deferred to 5c (requires segments to exist first)

## Architecture References

- All three segment model field specs:
  `architecture/data-models.md` → Segmentation Layer
- `PhysiologicalSegment` as the stable interface across all generations:
  `architecture/segmentation-pipeline.md` → What Segmentation Does
- Gen 1 heuristic algorithm and known failure modes:
  `architecture/segmentation-pipeline.md` → Generation 1: Heuristic Segmentation
- Signal preprocessing (steps 5-7 of the 7-step pipeline):
  `architecture/segmentation-pipeline.md` → Signal Preprocessing Order
- Three segment types and their relationships:
  `architecture/segmentation-pipeline.md` → Three Segment Types

## Dependencies

Requires 5a (`RawSensorStream` must exist — segmentation runs on cleaned signal).
Requires 2c (`WorkoutStep` with `physiological_intent` — `PlannedSegment` is derived
from WorkoutStep records).

## Models Introduced

**`PlannedSegment`** — what was intended. Full field spec from arch reference:
`workout_step_id` FK, `planned_start_offset_seconds`, `planned_duration_seconds`,
`target_state: PhysiologicalIntentState`.
One record per WorkoutStep in the session's GeneratedWorkout.

**`DeviceSegment`** — what the watch recorded. From FIT lap messages.
`activity_id` FK, `lap_index`, `start_offset_seconds`, `duration_seconds`,
`lap_trigger` (str).

**`PhysiologicalSegment`** — inferred physiological state. Full field spec:
`activity_id` FK, `planned_segment_id` FK (nullable),
`start_offset_seconds`, `duration_seconds`,
`inferred_state: PhysiologicalIntentState`, `confidence` (float 0.0-1.0),
`state_probabilities` (JSONB — null in Gen 1; populated in Gen 3),
`observed_signals` (JSONB), `segmentation_version`.

## Services Introduced

**`HeuristicSegmentationService`** (sync, Python).
- `segment(cleaned_stream, workout_steps) → list[PhysiologicalSegment]`
  Steps 5-7 of the preprocessing pipeline (from arch reference):
  Step 5: Changepoint detection — identifies structural breaks in smoothed HR
  and power signals using threshold crossings.
  Step 6: State inference — assigns `PhysiologicalIntentState` to each segment
  using HR zone thresholds relative to current TwinState lt1/lt2 estimates.
  Step 7: Alignment — matches inferred segments to `PlannedSegment` records
  using temporal overlap. Unmatched segments receive null `planned_segment_id`.
  Confidence is set to 0.3 for ambiguous transitions; 0.7 for clear transitions.
  Segments with confidence < 0.4 are assigned `inferred_state = unknown`.

**`PlannedSegmentService`** (sync, Python).
- `create_from_workout(generated_workout) → list[PlannedSegment]`

**`DeviceSegmentService`** (sync, Python).
- `create_from_fit(activity, fit_data) → list[DeviceSegment]`

**`SegmentationTask`** (async worker).
- Triggered after `RawSensorStreamService.store()` completes.
- Calls `PlannedSegmentService`, `DeviceSegmentService`, `HeuristicSegmentationService`.
- Writes all three segment types.

## Key Constraints

- `PhysiologicalSegment` records are never updated — if a new pipeline version
  produces better segments, new records are inserted with a new `segmentation_version`
  and the old records receive `superseded_at`.
- Unaligned segments (no matching `PlannedSegment`) are retained with null FK —
  never discarded. They carry information about unplanned effort.
- `segmentation_version = heuristic-v1` for all records created in this sub-phase.

## Done Criteria

- After processing a structured threshold session, `PhysiologicalSegment` records
  exist for the activity with `inferred_state` values covering the session phases.
- At least one segment has `inferred_state = threshold` for a threshold workout.
- Unaligned segments exist where the athlete deviated from the planned structure.
- Low-confidence ambiguous segments have `inferred_state = unknown` and
  `confidence < 0.4`.
- `GET /athletes/{id}/activities/{id}/segments` returns all three segment types.
