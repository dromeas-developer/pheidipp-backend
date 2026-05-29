# 6c — Three-Dimensional Load & Adaptation Signature
*AdaptationObservation, Layer 3 active, 3D TwinState fields*

## Objective

Activate Twin Layers 1 (three-dimensional) and 3 (adaptation signature).
Aerobic, neuromuscular, and structural fitness/fatigue are now tracked separately.
Block-level adaptation observations begin building the yield profile that drives
plan personalisation.

## Scope

`AdaptationObservation` model. `TwinState` three-dimensional fields activated.
`AdaptationObservationService`. Plan generation updated to consume adaptation data.
Training block boundary detection.

## Architecture References

- `AdaptationObservation` full field spec:
  `architecture/data-models.md` → Adaptation Layer
- Three-dimensional TwinState schema evolution:
  `architecture/twin-state.md` → Layer 1 Three-Dimensional Evolution
- Adaptation observation triggers and recovery window measurement:
  `architecture/coaching-services.md`
- Training block as atomic unit of analysis:
  `vision/twin/adaptation-signature.md`
- Three load dimensions and their distinct accumulation curves:
  `vision/twin/load-fatigue.md`

## Dependencies

Requires 5b (`PhysiologicalSegment` records — used in adaptation yield computation).
Requires 6a (HMM segments improve the accuracy of adaptation observation).
Requires 6 weeks minimum of real training data.

## Models Modified

**`TwinState`** — three-dimensional fields now populated (previously null):
`aerobic_fitness`, `aerobic_fatigue`, `neuromuscular_fitness`,
`neuromuscular_fatigue`, `structural_fitness`, `structural_fatigue`.
Aggregate `fitness_score` and `fatigue_score` retained as sum for backward compatibility.

## Models Introduced

**`AdaptationObservation`** — block-level adaptation record. Full field spec:
`athlete_id` FK, `training_block_id` FK, `block_start_date`, `block_end_date`,
`total_aerobic_load`, `total_neuromuscular_load`, `total_structural_load`,
`fitness_delta` (float — Layer 1 aggregate change), `recovery_trajectory` (JSONB),
`yield_by_intent_state` (JSONB — fitness gain per unit load per PhysiologicalIntentState),
`analysis_version`.

## Services Introduced

**`AdaptationObservationService`** (sync, Python).
- `observe_block(athlete_id, block_start, block_end) → AdaptationObservation`
  Called at training block boundaries (defined as: 2+ quality sessions followed
  by 2+ easy/rest days, or week boundaries).
  Computes: sum of load scores across the block, TwinState fitness delta,
  recovery trajectory from `AthleteWellness` records in the recovery window,
  yield per `PhysiologicalIntentState` from segment distribution.

**`AdaptationBlockDetectionTask`** (async worker — runs nightly).
Identifies block boundaries from `PlannedSession` patterns and enqueues
`AdaptationObservationService` for each completed block.

## Services Modified

**`PlanGenerationService`** (updated) — when `AdaptationObservation` records exist:
- Recovery buffer widths are derived from the athlete's observed recovery trajectory
  rather than population defaults.
- Training emphasis weighting (threshold vs aerobic volume) shifts toward the
  emphasis with the highest observed yield for this athlete.

**`TwinRecalibrationService`** (updated) — now updates all six dimensional fields
when processing calibration-eligible sessions.

## Done Criteria

- After 2 complete hard blocks, `AdaptationObservation` records exist.
- `yield_by_intent_state` in the observation shows differentiated yield by
  session type (not all the same value).
- The plan generated after adaptation data is available has different recovery
  buffer widths than the plan generated at Phase 1 for the same athlete.
- `TwinState.aerobic_fitness` is non-null and differs from the aggregate `fitness_score`.
