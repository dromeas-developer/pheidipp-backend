# 2c — Structured Workout Generation
*PhysiologicalIntentState, WorkoutStep, two-column targets*

## Objective

Replace the JSON blob workout structure with first-class `WorkoutStep` models
carrying `physiological_intent`. This is the architectural foundation for all
downstream session analysis — every comparison between prescribed and executed
intent depends on `WorkoutStep.physiological_intent` existing as structured data.
Also triggers plan regeneration now that real threshold data is available.

## Scope

`PhysiologicalIntentState` enum. `WorkoutStep` model. Migration of
`GeneratedWorkout` from JSON blob to FK-linked steps. Updated workout generation
agent that produces `WorkoutStep` records. Plan regeneration on confidence upgrade.

## Non-Goals

- Segmentation pipeline (PlannedSegment, PhysiologicalSegment) — deferred to 5b
- Recovery modifier on `adjusted_targets` — deferred to 3b
- Weather modifier on `adjusted_targets` — deferred to 3d
  (`adjusted_targets` still equals `theoretical_targets` in this sub-phase)

## Architecture References

- `PhysiologicalIntentState` enum values and end-to-end usage:
  `architecture/shared-language.md`
- `WorkoutStep` full field spec: `architecture/data-models.md` → Workout Layer
- `GeneratedWorkout` two-column structure: `architecture/data-models.md` → Workout Layer
- How TwinState confidence feeds workout target precision:
  `architecture/twin-state.md` → How the Twin Feeds LLM Agents
- Vision-level two-column display rationale:
  `vision/twin/training-zones.md` → Two-Column Target Display

## Dependencies

Requires 1e (WorkoutGenerationAgent exists), 2b (TwinState now has real threshold
data; confidence may have upgraded to MEDIUM for some athletes).

## Models Introduced

**`PhysiologicalIntentState`** enum (added to `app/models/enums.py`):
`warmup`, `low_aerobic`, `high_aerobic`, `threshold`, `vo2`, `recovery`,
`cooldown`, `unknown`.
This is the most important enum in the codebase. See `architecture/shared-language.md`.

**`WorkoutStep`** — individual step within a GeneratedWorkout. Full field spec
from `architecture/data-models.md`:
`generated_workout_id` FK, `step_order`, `step_type` (enum: `warmup`, `work`,
`recovery`, `cooldown`), `physiological_intent: PhysiologicalIntentState`,
`target_duration_seconds` (nullable), `target_hr_zone` (nullable),
`target_power_watts` (nullable), `target_gap_sec_per_km` (nullable),
`description` (plain English shown to athlete).

## Models Modified

**`GeneratedWorkout`** — `workout_structure` JSONB column removed.
`WorkoutStep` records replace it via FK relationship. All other fields unchanged.
Existing GeneratedWorkout records (Phase 1 JSON blobs) are migrated: each JSON
structure is parsed and WorkoutStep records are created from it.

## Services & Tasks Modified

**`WorkoutGenerationAgent`** (updated) — now produces `WorkoutStep` records instead
of JSON blob.
- LLM output is parsed into a structured response that maps to WorkoutStep fields.
- Each step carries `physiological_intent` as the primary intent signal.
- Targets are expressed in units appropriate to the athlete's data tier:
  - Tier 1-2: `target_power_watts` primary; `target_gap_sec_per_km` secondary
  - Tier 3-4: `target_gap_sec_per_km` primary; `target_hr_zone` secondary
  - Tier 5-6: `description` only; numeric targets null
- `theoretical_targets` on GeneratedWorkout stores the zone-based targets derived
  from current TwinState threshold estimates.
- `adjusted_targets` = `theoretical_targets` in this sub-phase
  (modifiers added in 3b and 3d).

**`PlanGenerationService`** (updated) — plan regeneration now triggered when
TwinState confidence upgrades from `low` to `medium` for the first time.
Rationale: the plan generated at Phase 1 used population norm threshold estimates;
a MEDIUM confidence TwinState allows more precisely calibrated session targets.

## Key Constraints

- `WorkoutStep.physiological_intent` is never null — every step has an intent,
  even warmup and cooldown. `warmup` and `cooldown` states exist for this purpose.
- `WorkoutStep.step_order` must be unique within a `GeneratedWorkout` (no two steps
  at the same position). Enforced by unique constraint on `(generated_workout_id, step_order)`.
- The migration from JSON blob to WorkoutStep records must be reversible. The old
  `workout_structure` column is renamed `workout_structure_deprecated` and retained
  for one phase before permanent removal in 2d.
- `target_gap_sec_per_km` values use grade-adjusted pace throughout — never raw pace.
  The workout generation agent prompt must enforce this.

## Done Criteria

- `GET /athletes/{athlete_id}/today` returns a GeneratedWorkout with linked
  WorkoutStep records, each carrying a non-null `physiological_intent`.
- A threshold session produces WorkoutStep records with appropriate states:
  warmup → low_aerobic → threshold (per rep) → recovery (between reps) → cooldown.
- Tier 3-4 athletes receive `target_gap_sec_per_km` targets; Tier 5-6 athletes
  receive description-only steps with null numeric targets.
- After a confidence upgrade to MEDIUM, the plan is regenerated with updated targets.
