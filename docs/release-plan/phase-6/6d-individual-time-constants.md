# 6d — Individual Banister Time Constants
*Per-athlete fitness and fatigue decay rates, full Layer 1 personalisation*

## Objective

Replace population-default Banister time constants (fitness ~42 days, fatigue ~7 days)
with individually fitted values. Some athletes carry fatigue for 10+ days; others
clear in 5. The load model is now calibrated to this specific athlete's physiology.

## Scope

`TimeConstantFittingService`. `AthleteProfile.banister_constants` field.
`TwinRecalibrationService` updated to use individual constants.

## Architecture References

- Individual time constants, population defaults, and personalisation:
  `architecture/twin-state.md` → Individual Time Constants
- Banister model fitness/fatigue computation:
  `architecture/twin-state.md` → Layer 1 Three-Dimensional Evolution

## Dependencies

Requires 6c (three-dimensional TwinState — time constants are fitted per dimension).
Requires 12+ weeks of real training data with calibration-eligible sessions.

## Models Modified

**`AthleteProfile`** — adds `banister_constants` (JSONB, nullable):
```json
{
  "aerobic_fitness_tau": 44,
  "aerobic_fatigue_tau": 9,
  "neuromuscular_fitness_tau": 28,
  "neuromuscular_fatigue_tau": 4,
  "structural_fitness_tau": 56,
  "structural_fatigue_tau": 14,
  "fitted_from_weeks": 16,
  "fitted_at": "2026-04-01"
}
```
Population defaults: aerobic fitness 42, aerobic fatigue 7, NM fitness 21,
NM fatigue 3, structural fitness 56, structural fatigue 14.

## Services Introduced

**`TimeConstantFittingService`** (sync, Python).
- `fit(athlete_id) → BanisterConstants | None`
  Returns None if < 12 weeks of calibration-eligible sessions.
  Fits time constants by minimising the difference between Banister model predictions
  and observed TwinState fitness transitions across the historical record.
  Stores in `AthleteProfile.banister_constants`.

## Services Modified

**`TwinRecalibrationService`** (updated) — uses individual time constants when
`AthleteProfile.banister_constants` is non-null. Falls back to population defaults.

## Done Criteria

- An athlete with 14+ weeks of data has non-null `banister_constants`.
- An athlete known to recover slowly has `aerobic_fatigue_tau > 9`.
- After fitting, `TwinRecalibrationService` uses individual constants for all
  subsequent recalibrations (verifiable via TwinState history comparison).
