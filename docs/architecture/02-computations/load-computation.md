# Load Computation — Three Load Dimension Formulas

## Purpose
- Defines the exact formulas for computing aerobic, neuromuscular, and structural load scores from FIT data
- These scores are written to Activity and drive TwinState Layer 1 fitness/fatigue via Banister model

> **Vision rationale:** The three-dimensional approach implements the physiological principle that different training stresses (cardiovascular, neuromuscular, structural) accumulate and recover on different timelines. A single fitness number cannot distinguish between states where aerobic system is recovered but structural load is excessive — the "heavy legs" phenomenon. The three dimensions are not independent: high structural fatigue degrades neuromuscular output even when the aerobic system is fully recovered. See `docs/vision/twin/load-fatigue.md` for the full physiological rationale.

## Inputs

> **GAP invariant:** Grade-adjusted pace is always used as the mechanical work proxy. Raw pace without grade adjustment systematically misrepresents effort on varied terrain and corrupts load calculations and historical comparisons. This is an invariant, not a preference. See `docs/vision/twin/load-fatigue.md#grade-adjusted-pace--always-never-raw-pace`.

```typescript
type LoadComputationInputs = {
  fit_data: FitData           // from FitParserService; raw records (not averages)
  twin_state: TwinState       // for threshold references
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

**Heuristic (no threshold reference):**
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

**Threshold-referenced:** Same formula; uses real `lt1_estimate_bpm` and `lt2_estimate_bpm` from TwinState instead of population estimates.

**Tier 1-2 (power available):** Power-based computation replaces HR-based:
```typescript
function computeAerobicLoadPower(
  power_records: number[],       // watts per second
  cp_estimate: number            // from AthletePhysiology
): number {
  return power_records.reduce((acc, w) => {
    const intensity_factor = w / ftp_estimate
    return acc + Math.pow(intensity_factor, 4)  // fourth-power; standard NP/IF approach
  }, 0) / 3600
}
```

**Tier 5 (pace + GPS only):** Estimated from GAP relative to estimated threshold pace. Low confidence flagged. Tier 6: null.

> **Note on optical HR:** Tier 4 (optical HR + GAP + GPS) is the realistic baseline for the core athlete audience. Optical HR is adequate for zone-based load calculation; its limitation versus chest strap is specifically the absence of RR intervals for threshold detection, not HR accuracy for sustained aerobic efforts. See `docs/vision/twin/load-fatigue.md#data-quality-and-load-computation`.

## Neuromuscular Load Formula

Measures fast-twitch demand, explosive stress, and high-intensity neuromuscular recruitment.

```typescript
function computeNeuromuscularLoad(
  gap_records: number[],         // sec/km per second; from effort normalisation
  cp_estimate: number | null,    // watts; null for non-power athletes
  power_records: number[] | null // null if no power meter
): number {
  // Variability index: coefficient of variation of pace/power over session
  const values = power_records ?? gap_records
  const mean = values.reduce((a, b) => a + b, 0) / values.length
  const variance = values.reduce((a, v) => a + Math.pow(v - mean, 2), 0) / values.length
  const variability_index = Math.sqrt(variance) / mean

  // Time above VO2max threshold (95% of LT2 intensity)
  const vo2_threshold = cp_estimate ? cp_estimate * 1.05 : null
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
const DENSITY_PENALTY_COEFFICIENT = 0.12
const MAX_DENSITY_PENALTY = 15  // Cap to prevent runaway feedback loop

function computeStructuralLoad(inputs: StructuralLoadInputs): number {
  const { distance_m, elevation_gain_m, surface_type, recent_structural_load_72h } = inputs
  const surface_modifier = SURFACE_MODIFIERS[surface_type]
  const base = (distance_m / 1000) * surface_modifier
  const gradient_cost = (elevation_gain_m / 100) * GRADIENT_COST_FACTOR * (distance_m / 1000)
  const density_penalty = Math.min(
    recent_structural_load_72h * DENSITY_PENALTY_COEFFICIENT,
    MAX_DENSITY_PENALTY
  )
  return base + gradient_cost + density_penalty
}
```

Requires GPS (distance + elevation). Available from Tier 3 onward. Tier 6: null.

> **Crossover athlete profile:** The density penalty (`recent_structural_load_72h * 0.12`) is specifically designed to catch athletes transitioning from swimming or cycling who carry high aerobic load tolerance but low structural load tolerance. Without this, a cardiovascular-only model would miss structural stress accumulating at a rate cardiovascular fitness masks. This profile is identified at onboarding and structural capacity development is incorporated as an explicit objective. See `docs/vision/twin/load-fatigue.md#the-crossover-athlete-profile`.

> **Crossover Athlete Structural Load Adjustment:**
> 
> The density penalty coefficient is conditioned on the crossover athlete profile:
> 
> ```typescript
> const DENSITY_PENALTY_COEFFICIENT = athlete.structural_risk_flag ? 0.08 : 0.12
> // Lower penalty for athletes with predicted structural resilience (non-running primary background)
> ```
> 
> `AthleteProfile.structural_risk_flag` is set at onboarding from `AthletePreferences.sport_background`. Marathoners (high structural tolerance relative to aerobic) receive a lower density penalty. Swimmers/cyclists transitioning to running (low structural tolerance) receive the population default.
> 
> **Current boundary:** `sport_background` not `running_primary` activates the crossover athlete structural capacity *ramp in plan generation* (what sessions are prescribed). The `structural_risk_flag` additionally adjusts *how load is measured*. These are separate layers — both activated by the same onboarding signal.

> **Feedback Loop Bound:**
> 
> The density penalty creates a positive feedback loop: structural load feeds into `recent_structural_load_72h` for future sessions, causing the penalty to compound over consecutive high-load days.
> 
> A 100km week at 1.0 base load/day produces a day 4 density penalty of ~0.36 (acceptable). Extreme cases (ultra blocks) could produce runaway without a bound.
> 
> `MAX_DENSITY_PENALTY = 15` caps the feedback loop, equivalent to ~125km of recent structural load. This preserves the physiological intent (accumulated structural fatigue amplifies stress) while preventing unbounded growth.

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

**Note**: Easy runs are calibration-eligible (they meet the five-rule gate) and contribute to fitness/fatigue scores. However, they do NOT provide threshold detection evidence because they lack the intensity variation required for HR deflection/RR inflection algorithms (which need ≥3 distinct intensity steps and ≥8 minutes at each level). Easy runs build fitness, not threshold confidence.

## Outputs → TwinState Layer 1

The three load scores feed the Banister impulse-response model. The full Banister update formula and time constant semantics are defined in `02-computations/banister-update.md`.

```typescript
// Banister update (summary):
// fitness_score(t) = fitness_score(t-1) * exp(-1/τ_fitness) + aerobic_load
// fatigue_score(t) = fatigue_score(t-1) * exp(-1/τ_fatigue) + aerobic_load
// See 02-computations/banister-update.md for full formula, time constants, and individual fitting.
```
## Version History

| Version | Change |
|---|---|
| `v1-heuristic` | Population norm threshold references |
| `v2-threshold-referenced` | Real lt1/lt2 from TwinState |
| `v2-per-athlete-gap` | Per-athlete GAP curve in structural load |
| `v3-personalised` | Personalised effort model |

## Cross-References
- Effort normalisation (GAP input to formulas): `02-computations/effort-normalisation.md`
- AthleteFitness Banister model (where load scores are applied): `01-entities/athlete-fitness.md`
- Data tier capabilities: `00-foundations/data-tiers.md`
- Calibration eligibility rules (full detail): `01-entities/activity.md`
- **Vision — load fatigue rationale (three dimensions, data quality tiers, crossover athlete, individual time constants, GAP invariant):** `docs/vision/twin/load-fatigue.md`
- **Vision — cold start and onboarding tier definitions:** `docs/vision/twin/cold-start.md`
