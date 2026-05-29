# Effort Normalisation — GAP to Personalised Physiological Cost

## Purpose
- Defines the three generations of effort normalisation, from static GAP to per-athlete physiological cost model
- All pace-based computations throughout the system use the output of this computation — never raw pace

## Core Invariant

**Raw pace is never used anywhere in the system.** Every pace-based computation — load scores, threshold targets, workout targets, comparable session matching, race prediction — uses grade-adjusted pace from whichever generation is active for the athlete.

## Generation 1 — Static Population GAP

**Active for:** All athletes until 20+ outdoor sessions with elevation data exist.

```typescript
const GAP_COEFFICIENTS_POPULATION = { a: 0.033, b: 0.00012 }

function computeGAP_v1(
  raw_pace_sec_per_km: number,
  grade_pct: number,           // positive = uphill; negative = downhill
  coefficients = GAP_COEFFICIENTS_POPULATION
): number {
  const correction_factor = 1 + (coefficients.a * grade_pct) + (coefficients.b * Math.pow(grade_pct, 2))
  return raw_pace_sec_per_km / correction_factor
  // Result: normalised pace as if running on flat terrain
}
```

**Limitations:** Applies the same correction to every athlete regardless of individual terrain response, fatigue state, or biomechanics. A systematic approximation acknowledged throughout the system.

## Generation 2 — Per-Athlete Grade Response Curve

**Active for:** Athletes with ≥ 20 outdoor activities with meaningful elevation data AND `AthleteProfile.gap_curve_model.r_squared >= 0.70`.
**Fallback:** Population coefficients when threshold not met.

```typescript
// Fitting process (GapCurveFittingService):
// 1. Collect (grade, observed_pace, hr) triples from calibration-eligible outdoor sessions
// 2. Filter to aerobic-zone efforts (avoid anaerobic confounding)
// 3. Fit: correction_factor = 1 + a*grade + b*grade² using least-squares regression
// 4. Store fitted {a, b} in AthleteProfile.gap_curve_model if R² >= 0.70

function computeGAP_v2(
  raw_pace_sec_per_km: number,
  grade_pct: number,
  athlete_coefficients: { a: number; b: number }
): number {
  const correction_factor = 1 + (athlete_coefficients.a * grade_pct)
    + (athlete_coefficients.b * Math.pow(grade_pct, 2))
  return raw_pace_sec_per_km / correction_factor
}
```

## Generation 3 — Personalised Physiological Cost Model

**Active for:** Athletes with ≥ 40 outdoor activities with varied terrain AND `AthleteProfile.effort_model_version = 'personalised-v1'`.
**Fallback:** Generation 2 (or Generation 1 if Gen 2 not fitted).

Generation 3 replaces the GAP concept with a learned physiological cost model. It answers: "What is the metabolic and mechanical cost of this effort for this athlete under these conditions?"

```typescript
type EffortCostInputs = {
  grade_pct: number
  surface_type: 'trail' | 'road' | 'track' | 'treadmill' | 'unknown'
  current_structural_fatigue: number   // from TwinState.structural_fatigue
  recent_terrain_history: TerrainProfile  // accumulated from past sessions
}

type EffortCostOutput = {
  normalised_cost: number              // replaces GAP as the primary mechanical work proxy
  confidence_interval: [number, number]  // tighter near observed training envelope
}

// Model is trained from accumulated {grade, surface, fatigue, HR, pace} records
// Uses a Gaussian Process or similar non-parametric regressor
// Confidence interval is wider for conditions the athlete has not trained in
```

**Key difference from Gen 1-2:** Downhill cost is personalised. Some athletes have efficient downhill mechanics (low eccentric cost); others degrade significantly. Structural fatigue modulates the cost — an athlete with accumulated structural load pays more for the same downhill km.

## Active Generation Selection

```typescript
function selectGeneration(profile: AthleteProfile): EffortNormalisationGeneration {
  if (profile.effort_model_version === 'personalised-v1') return 3
  if (profile.gap_curve_model?.r_squared >= 0.70) return 2
  return 1
}
```

## Downstream Consumers

Every computation that touches pace uses the output of this service:

| Consumer | Uses |
|---|---|
| `LoadComputationService` | GAP per record for aerobic and neuromuscular load |
| `ThresholdDetectionService` | GAP time-series for HR deflection analysis |
| `WorkoutGenerationAgent` | `target_gap_sec_per_km` on WorkoutStep |
| `ComparableSessionService` | Normalised pace for similarity scoring |
| `RacePredictionService` | `observed_pace_at_lt2_sec_per_km` computation |
| `CourseAdjustmentService` | Elevation-adjusted predicted pace for race prediction |

## Version History

| Version | Active when | ingestion_pipeline_version |
|---|---|---|
| Gen 1 static | Default | `v1-heuristic`, `v2-threshold-referenced` |
| Gen 2 per-athlete | ≥20 outdoor sessions, R²≥0.70 | `v2-per-athlete-gap` |
| Gen 3 personalised | ≥40 varied terrain sessions | `v3-personalised` |

## Cross-References
- Load computation that uses GAP: `02-computations/load-computation.md`
- Per-athlete curve storage: `01-entities/athlete-profile.md` → `gap_curve_model`
- Personalised model storage: `01-entities/athlete-profile.md` → `effort_model_version`
- Versioning and reprocessing when generation upgrades: `04-platform/versioning-and-reprocessing.md`
