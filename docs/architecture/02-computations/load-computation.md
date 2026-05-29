# Load Computation — Three Load Dimension Formulas

## Purpose
- Defines the exact formulas for computing aerobic, neuromuscular, and structural load scores from FIT data
- These scores are written to Activity and drive TwinState Layer 1 fitness/fatigue via Banister model

## Inputs

```typescript
type LoadComputationInputs = {
  fit_data: FitData           // from FitParserService; raw records (not averages)
  twin_state: TwinState       // for threshold references (used from Phase 2d onward)
  data_tier: DataTier
  ingestion_pipeline_version: string
}

type LoadScores = {
  aerobic_load: number | null
  neuromuscular_load: number | null
  structural_load: number | null
}
```

## Aerobic Load Formula

Measures cardiovascular and metabolic stress from sustained aerobic effort.

**Phase 2b (heuristic — no threshold reference):**
```typescript
// HR reserve integration: each second weighted by exponential function of HR reserve %
function computeAerobicLoadHeuristic(
  hr_records: number[],          // bpm per second
  max_hr_estimate: number,       // from TwinState
  resting_hr: number             // AthleteWellness.min_sleeping_hr_bpm or population default
): number {
  const hrr = max_hr_estimate - resting_hr  // HR reserve range
  return hr_records.reduce((acc, hr) => {
    const hrr_pct = (hr - resting_hr) / hrr
    const weight = Math.exp(1.92 * hrr_pct) - 1  // exponential; effort above threshold costs more
    return acc + weight
  }, 0) / 3600  // normalise: 1 hour at LT1 ≈ 100 units
}
```

**Phase 2d onward (threshold-referenced):** Same formula; uses real `lt1_estimate_bpm` and `lt2_estimate_bpm` from TwinState instead of population estimates. `ingestion_pipeline_version` incremented.

**Tier 1-2 (power available):** Power-based computation replaces HR-based:
```typescript
function computeAerobicLoadPower(
  power_records: number[],       // watts per second
  ftp_estimate: number           // from TwinState
): number {
  return power_records.reduce((acc, w) => {
    const intensity_factor = w / ftp_estimate
    return acc + Math.pow(intensity_factor, 4)  // fourth-power; standard NP/IF approach
  }, 0) / 3600
}
```

**Tier 5 (pace + GPS only):** Estimated from GAP relative to estimated threshold pace. Low confidence flagged. Tier 6: null.

## Neuromuscular Load Formula

Measures fast-twitch demand, explosive stress, and high-intensity neuromuscular recruitment.

```typescript
function computeNeuromuscularLoad(
  gap_records: number[],         // sec/km per second; from effort normalisation
  ftp_estimate: number | null,   // watts; null for non-power athletes
  power_records: number[] | null // null if no power meter
): number {
  // Variability index: coefficient of variation of pace/power over session
  const values = power_records ?? gap_records
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const variance = values.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / values.length
  const variability_index = Math.sqrt(variance) / mean

  // Time above VO2max threshold (95% of LT2 intensity)
  const vo2_threshold = ftp_estimate ? ftp_estimate * 1.05 : null
  const time_above_vo2 = vo2_threshold
    ? power_records!.filter(w => w > vo2_threshold).length
    : gap_records.filter(g => g < /* estimated VO2 pace */ 0).length  // simplified

  return (variability_index * (gap_records.length / 3600)) + (time_above_vo2 / 3600 * 2.5)
}
```

Requires Tier 4 minimum (pace + GPS). Tier 5/6: null.

## Structural Load Formula

Measures mechanical, tendon, and connective tissue stress from impact and loading.

```typescript
type StructuralLoadInputs = {
  distance_m: number
  elevation_gain_m: number
  surface_type: 'trail' | 'road' | 'track' | 'treadmill' | 'unknown'
  recent_structural_load_72h: number  // sum of structural loads in past 72 hours
}

const SURFACE_MODIFIERS = {
  trail: 1.15,      // higher impact + proprioceptive demand
  road: 1.00,       // baseline
  track: 0.90,      // reduced impact
  treadmill: 0.85,  // lowest impact
  unknown: 1.00
}

const GRADIENT_COST_FACTOR = 0.18  // per 100m elevation gain per km

function computeStructuralLoad(inputs: StructuralLoadInputs): number {
  const { distance_m, elevation_gain_m, surface_type, recent_structural_load_72h } = inputs
  const surface_modifier = SURFACE_MODIFIERS[surface_type]
  const base = (distance_m / 1000) * surface_modifier
  const gradient_cost = (elevation_gain_m / 100) * GRADIENT_COST_FACTOR * (distance_m / 1000)
  const density_penalty = recent_structural_load_72h * 0.12  // accumulated fatigue amplifies stress
  return base + gradient_cost + density_penalty
}
```

Requires GPS (distance + elevation). Available from Tier 3 onward. Tier 6: null.

## Calibration Eligibility Gate

`CalibrationEligibilityService` applies this gate before load scores are used for twin recalibration:

```typescript
function isCalibrationEligible(activity: Activity, fit_data: FitData): boolean {
  return (
    activity.has_hr &&
    activity.source !== 'manual_entry' &&
    fit_data.moving_duration_seconds >= 1200 &&  // 20 minutes minimum
    !activity.quality_flags.hr_dropout_pct ||
    activity.quality_flags.hr_dropout_pct! <= 0.20 &&
    !activity.quality_flags.gps_loss &&
    !activity.quality_flags.sensor_malfunction &&
    isUsableSessionType(activity.session_type)   // excludes < 4 min interval sessions
  )
}
```

## Outputs → TwinState Layer 1

The three load scores feed the Banister impulse-response model in `TwinRecalibrationService`:

```typescript
// Banister update (simplified):
fitness_score(t) = fitness_score(t-1) * exp(-1/τ_fitness) + aerobic_load
fatigue_score(t) = fatigue_score(t-1) * exp(-1/τ_fatigue) + aerobic_load

// τ values: population defaults until Phase 6d individual fitting
// τ_aerobic_fitness = 42 days; τ_aerobic_fatigue = 7 days
```

See `01-entities/twin-state.md` for the full TwinState schema.

## Version History
| Version | Change |
|---|---|
| `v1-heuristic` | Population norm threshold references |
| `v2-threshold-referenced` | Real lt1/lt2 from TwinState (Phase 2d) |
| `v2-per-athlete-gap` | Per-athlete GAP curve in structural load (Phase 5d) |
| `v3-personalised` | Generation 3 effort model (Phase 6e) |

## Cross-References
- Effort normalisation (GAP input to formulas): `02-computations/effort-normalisation.md`
- TwinState Layer 1 Banister model: `01-entities/twin-state.md`
- Data tier capabilities: `00-foundations/data-tiers.md`
- Calibration eligibility rules (full detail): `01-entities/activity.md`
