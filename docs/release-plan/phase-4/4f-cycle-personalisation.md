# 4f — Cycle Personalisation
*Individual cycle length learning, personalised phase adjustments*

## Objective

Replace population-level cycle phase assumptions with individually learned patterns.
After 3 logged cycles the system knows this athlete's actual cycle length, phase
boundaries, and how strongly their wellness and execution data correlates with
each phase. Cycle phase adjustments become genuinely personal.

## Scope

`CyclePersonalisationService`. Individual cycle length computation from
`CyclePhaseLog` history. Per-athlete phase composite adjustment learning.
Personalised boundaries replacing population defaults after 3 complete cycles.

## Non-Goals

- Hormone-specific modelling beyond cycle phase — outside scope
- Predictive cycle day inference without logging — requires more data

## Architecture References

- Population vs personalised phase boundaries and adjustment learning:
  `architecture/wellness-and-modifiers.md` → Menstrual Cycle Integration
- Individual variation principle (model learns per-athlete phase sensitivity):
  `vision/twin/womens-cycle.md` → Individual Variation

## Dependencies

Requires 3c (`CyclePhaseLog` model exists and has ≥ 3 entries for the athlete).

## Services Introduced

**`CyclePersonalisationService`** (sync, Python).
- `compute_individual_model(athlete_id) → CyclePersonalModel | None`
  Returns None if < 3 complete cycles logged.
  Computes: average cycle length, average phase durations from log intervals,
  per-phase wellness deviation correlations (does this athlete's HRV/sleeping HR
  actually vary with phase?), per-phase execution signal correlations.
  Stores result as a JSONB field on `AthleteProfile`: `cycle_personal_model`.
- `should_personalise(athlete_id) → bool`
  Returns True if ≥ 3 complete cycles and `CyclePersonalisationService` has not
  run since the most recent log.

**`CyclePhaseService`** (updated) — when `cycle_personal_model` exists on
`AthleteProfile`, uses individual phase boundaries and adjustment weights instead
of population defaults. Falls back to population defaults otherwise.

**`CyclePersonalisationTask`** (async worker — triggered after each new
`CyclePhaseLog` entry when `should_personalise = True`).

## Models Modified

**`AthleteProfile`** — adds `cycle_personal_model` (JSONB, nullable). Populated
by `CyclePersonalisationService`. Structure:
```json
{
  "avg_cycle_length_days": 27,
  "phase_boundaries": {"menstrual_end": 4, "follicular_end": 12, ...},
  "phase_sensitivity": {"menstrual": 0.8, "follicular": 0.2, "luteal": 0.9},
  "computed_at": "2026-01-15"
}
```
`phase_sensitivity` values replace the population composite adjustments in
`WellnessModifierService` for this athlete.

## Key Constraints

- Personalisation triggers only after 3 complete cycles — the minimum for a
  meaningful average. Fewer cycles keep population defaults.
- `phase_sensitivity` of 0.0 means this athlete shows no measurable phase
  correlation in their data — the cycle modifier is effectively zeroed for them.
  This is a valid outcome, not a data problem.
- The population model is always the fallback if `cycle_personal_model` is null.

## Done Criteria

- After logging 3 cycle starts, `AthleteProfile.cycle_personal_model` is populated.
- An athlete whose data shows no phase correlation has near-zero `phase_sensitivity`
  values and receives minimal cycle phase adjustment.
- An athlete whose data shows strong luteal phase HRV suppression has a high
  `phase_sensitivity` for the luteal phase and receives proportionally larger
  adjusted target reductions.
